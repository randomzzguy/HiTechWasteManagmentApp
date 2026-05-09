# =============================================================
# Hi-Tech Waste Management — Database Layer
# SQLAlchemy 2.0 async engine (asyncpg) + sync engine (psycopg2)
# =============================================================

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Generator

from config import get_settings
from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import NullPool, QueuePool

logger = logging.getLogger(__name__)

settings = get_settings()


# =============================================================
# Declarative Base
# All ORM models inherit from this class.
# =============================================================


class Base(DeclarativeBase):
    """
    Shared declarative base for all SQLAlchemy ORM models.

    Subclasses automatically gain:
    - __tablename__ (must be defined per model)
    - Metadata shared across the entire schema
    - Type annotation support via mapped_column / Mapped
    """

    pass


# =============================================================
# Async Engine (FastAPI / asyncpg)
# Used by all async request handlers and background lifespan tasks.
# =============================================================

async_engine = create_async_engine(
    url=settings.async_database_url,
    echo=settings.DEBUG,  # Log all SQL in debug mode
    pool_size=settings.DB_POOL_SIZE,  # Number of persistent connections
    max_overflow=settings.DB_MAX_OVERFLOW,  # Extra connections above pool_size
    pool_pre_ping=settings.DB_POOL_PRE_PING,  # Verify connections before checkout
    pool_recycle=settings.DB_POOL_RECYCLE,  # Recycle stale connections
    pool_timeout=settings.DB_POOL_TIMEOUT,  # Wait for a connection slot
    connect_args={
        "server_settings": {
            "application_name": "hitech_waste_backend",
            "jit": "off",  # Disable JIT for faster small queries
        },
        "command_timeout": 60,  # Statement timeout in seconds
    },
)

# Async session factory — do NOT use Session directly, always call AsyncSessionLocal()
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Keep objects usable after commit
    autocommit=False,
    autoflush=False,
)


# =============================================================
# Sync Engine (Celery tasks / Alembic migrations / scripts)
# Uses psycopg2 driver which is required by Celery workers.
# =============================================================

sync_engine = create_engine(
    url=settings.sync_database_url,
    echo=settings.DEBUG,
    poolclass=QueuePool,
    pool_size=settings.DB_SYNC_POOL_SIZE,
    max_overflow=settings.DB_SYNC_MAX_OVERFLOW,
    pool_pre_ping=settings.DB_POOL_PRE_PING,
    pool_recycle=settings.DB_POOL_RECYCLE,
    connect_args={
        "application_name": "hitech_waste_celery",
        "connect_timeout": 10,
    },
)

SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


# =============================================================
# FastAPI Dependency — Async DB Session
# Yields an AsyncSession and guarantees cleanup on exit.
# =============================================================


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides a scoped async database session.

    Commits the transaction automatically on success; rolls back on any
    exception to prevent partial writes leaking across requests.

    Usage:
        @router.get("/items")
        async def list_items(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(Item))
            return result.scalars().all()
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# =============================================================
# Celery / Script Dependency — Sync DB Session
# Yields a standard synchronous Session for use in Celery tasks,
# management scripts, and Alembic env.py.
# =============================================================


def get_sync_db() -> Generator[Session, None, None]:
    """
    Synchronous database session generator for Celery tasks and scripts.

    Usage in a Celery task:
        from database import get_sync_db

        @celery_app.task
        def my_task():
            with next(get_sync_db()) as db:
                results = db.execute(text("SELECT 1")).fetchall()

    Usage as a context manager (preferred):
        with SyncSessionLocal() as db:
            ...
    """
    db: Session = SyncSessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# =============================================================
# Async Context Manager Helper
# Useful in lifespan hooks and background tasks that do not use
# FastAPI's dependency injection system.
# =============================================================


@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager that provides an AsyncSession outside of the
    FastAPI dependency injection system.

    Usage:
        async with get_async_session() as session:
            result = await session.execute(select(User))
            users = result.scalars().all()
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# =============================================================
# Database Lifecycle Helpers
# Called from FastAPI lifespan context manager in main.py
# =============================================================


async def create_all_tables() -> None:
    """
    Creates all tables defined in the ORM metadata if they do not already
    exist. This is a lightweight alternative to running Alembic migrations
    during development or initial container startup.

    NOTE: In production, prefer running Alembic migrations explicitly:
        alembic upgrade head
    """
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables verified / created successfully.")


async def drop_all_tables() -> None:
    """
    Drops all ORM-managed tables. Use with extreme caution — intended only
    for test teardown or a complete environment reset.
    """
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        logger.warning("All database tables dropped.")


async def check_database_connection() -> bool:
    """
    Performs a lightweight connectivity check against the database.
    Returns True if the connection is healthy, False otherwise.
    Used by the health-check endpoint in main.py.
    """
    try:
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.error("Database connectivity check failed: %s", exc)
        return False


async def close_db_connections() -> None:
    """
    Gracefully disposes of all connection pool resources.
    Called during FastAPI shutdown lifespan to ensure clean teardown.
    """
    await async_engine.dispose()
    sync_engine.dispose()
    logger.info("Database connection pools disposed.")
