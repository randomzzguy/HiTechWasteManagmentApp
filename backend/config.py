# =============================================================
# Hi-Tech Waste Management — Application Configuration
# Pydantic BaseSettings with environment variable binding
# =============================================================

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central application configuration loaded from environment variables.
    All values can be overridden via a .env file or real environment variables.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ----------------------------------------------------------
    # Database
    # ----------------------------------------------------------
    DATABASE_URL: str = Field(
        default="postgresql://hitech:password@localhost:5432/hitech_waste",
        description="Async-compatible PostgreSQL DSN (asyncpg driver).",
    )
    REDIS_URL: str = Field(
        default="redis://localhost:6379",
        description="Redis connection URL used for caching and Celery broker.",
    )

    # Connection Pool Settings (Async Engine)
    DB_POOL_SIZE: int = Field(
        default=10,
        description="Number of persistent database connections in the pool.",
    )
    DB_MAX_OVERFLOW: int = Field(
        default=20,
        description="Maximum overflow connections beyond pool_size.",
    )
    DB_POOL_TIMEOUT: int = Field(
        default=30,
        description="Seconds to wait for a connection before raising an error.",
    )
    DB_POOL_RECYCLE: int = Field(
        default=3600,
        description="Seconds before recycling a connection (default: 1 hour).",
    )
    DB_POOL_PRE_PING: bool = Field(
        default=True,
        description="Test connection liveness before checkout.",
    )

    # Connection Pool Settings (Sync Engine - Celery)
    DB_SYNC_POOL_SIZE: int = Field(
        default=5,
        description="Sync engine pool size for Celery tasks.",
    )
    DB_SYNC_MAX_OVERFLOW: int = Field(
        default=10,
        description="Sync engine max overflow for Celery tasks.",
    )

    # ----------------------------------------------------------
    # Milvus Vector Database
    # ----------------------------------------------------------
    MILVUS_HOST: str = Field(default="localhost", description="Milvus gRPC host.")
    MILVUS_PORT: int = Field(default=19530, description="Milvus gRPC port.")

    # ----------------------------------------------------------
    # Ollama LLM
    # ----------------------------------------------------------
    OLLAMA_BASE_URL: str = Field(
        default="http://localhost:11434",
        description="Base URL for the Ollama HTTP API.",
    )
    OLLAMA_MODEL: str = Field(
        default="llama3.1:8b",
        description="Default chat/completion model served by Ollama.",
    )
    OLLAMA_EMBED_MODEL: str = Field(
        default="nomic-embed-text:latest",
        description="Embedding model served by Ollama for RAG ingestion.",
    )

    # ----------------------------------------------------------
    # MQTT Broker
    # ----------------------------------------------------------
    MQTT_BROKER_HOST: str = Field(
        default="localhost",
        description="Hostname of the Eclipse Mosquitto broker.",
    )
    MQTT_BROKER_PORT: int = Field(
        default=1883,
        description="MQTT broker port (1883 = plain TCP, 8883 = TLS).",
    )
    MQTT_TOPIC_GPS: str = Field(
        default="fleet/gps/#",
        description="MQTT topic filter for vehicle GPS telemetry.",
    )

    # ----------------------------------------------------------
    # Authentication & Security
    # ----------------------------------------------------------
    JWT_SECRET: str = Field(
        default="change-this-secret-key-in-production",
        description="HMAC secret used to sign JWT access/refresh tokens.",
    )
    JWT_ALGORITHM: str = Field(
        default="HS256",
        description="Algorithm used to sign JWTs.",
    )
    JWT_EXPIRE_MINUTES: int = Field(
        default=60,
        description="Access token lifetime in minutes.",
    )
    JWT_REFRESH_EXPIRE_DAYS: int = Field(
        default=7,
        description="Refresh token lifetime in days.",
    )
    NEXTAUTH_SECRET: str = Field(
        default="change-this-nextauth-secret",
        description="Secret shared with NextAuth.js for session signing.",
    )
    NEXTAUTH_URL: str = Field(
        default="http://localhost:3000",
        description="Public URL of the Next.js frontend (used by NextAuth).",
    )

    # ----------------------------------------------------------
    # CORS
    # ----------------------------------------------------------
    ALLOWED_ORIGINS: str = Field(
        default="*",
        description=(
            "Comma-separated list of allowed CORS origins. "
            "Use '*' for development only. "
            "Example: https://app.hitechwaste.com.my,https://admin.hitechwaste.com.my"
        ),
    )

    @property
    def cors_origins(self) -> list[str]:
        """Parse ALLOWED_ORIGINS into a list for CORSMiddleware."""
        raw = self.ALLOWED_ORIGINS.strip()
        if raw == "*":
            return ["*"]
        return [o.strip() for o in raw.split(",") if o.strip()]

    # ----------------------------------------------------------
    # Application URLs
    # ----------------------------------------------------------
    BACKEND_URL: str = Field(
        default="http://localhost:8000",
        description="Internal URL used by services to reach the backend API.",
    )
    NEXT_PUBLIC_API_URL: str = Field(
        default="http://localhost:8000",
        description="Browser-accessible REST API base URL.",
    )
    NEXT_PUBLIC_WS_URL: str = Field(
        default="ws://localhost:8000",
        description="Browser-accessible WebSocket base URL.",
    )

    # ----------------------------------------------------------
    # PDF / Reports
    # ----------------------------------------------------------
    REPORT_OUTPUT_DIR: str = Field(
        default="/app/generated_reports",
        description="Filesystem path where generated PDF reports are stored.",
    )
    CERTIFICATE_TEMPLATE_DIR: str = Field(
        default="/app/templates/certificates",
        description="Directory containing Jinja2 HTML certificate templates.",
    )

    # ----------------------------------------------------------
    # Email Notifications (optional)
    # ----------------------------------------------------------
    SMTP_HOST: str = Field(
        default="smtp.gmail.com",
        description="SMTP server hostname.",
    )
    SMTP_PORT: int = Field(
        default=587,
        description="SMTP server port (587 = STARTTLS, 465 = SSL).",
    )
    SMTP_USER: str = Field(
        default="",
        description="SMTP authentication username / sender address.",
    )
    SMTP_PASSWORD: str = Field(
        default="",
        description="SMTP authentication password or app-specific password.",
    )
    SMTP_FROM_NAME: str = Field(
        default="Hi-Tech Waste Management",
        description="Display name used in the From header of outgoing emails.",
    )

    # ----------------------------------------------------------
    # WhatsApp Notifications (optional)
    # ----------------------------------------------------------
    WHATSAPP_API_URL: Optional[str] = Field(
        default=None,
        description="WhatsApp Business API endpoint for sending notifications.",
    )
    WHATSAPP_API_TOKEN: Optional[str] = Field(
        default=None,
        description="Bearer token for the WhatsApp Business API.",
    )

    # ----------------------------------------------------------
    # MinIO / Object Storage
    # ----------------------------------------------------------
    MINIO_ENDPOINT: str = Field(
        default="localhost:9000",
        description="MinIO endpoint (used by Milvus and direct file uploads).",
    )
    MINIO_ACCESS_KEY: str = Field(default="minioadmin")
    MINIO_SECRET_KEY: str = Field(default="minioadmin")

    # ----------------------------------------------------------
    # App Meta
    # ----------------------------------------------------------
    APP_TITLE: str = "Hi-Tech Waste Management API"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = Field(
        default="development",
        description="Deployment environment: development | staging | production.",
    )
    DEBUG: bool = Field(
        default=False,
        description="Enable debug mode (verbose logging, reload, etc.).",
    )
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Python logging level: DEBUG | INFO | WARNING | ERROR | CRITICAL.",
    )

    # ----------------------------------------------------------
    # Sentry Error Tracking (optional)
    # ----------------------------------------------------------
    SENTRY_DSN: Optional[str] = Field(
        default=None,
        description="Sentry DSN for error tracking. Leave empty to disable.",
    )
    SENTRY_ENVIRONMENT: str = Field(
        default="development",
        description="Environment name for Sentry (e.g., production, staging).",
    )
    SENTRY_TRACES_SAMPLE_RATE: float = Field(
        default=0.1,
        description="Fraction of transactions to sample for performance monitoring (0.0-1.0).",
    )

    # ----------------------------------------------------------
    # Rate Limiting
    # ----------------------------------------------------------
    RATE_LIMIT_ENABLED: bool = Field(
        default=True,
        description="Enable API rate limiting.",
    )
    RATE_LIMIT_MAX_REQUESTS: int = Field(
        default=100,
        description="Maximum requests per time window.",
    )
    RATE_LIMIT_WINDOW_SECONDS: int = Field(
        default=60,
        description="Time window in seconds for rate limiting.",
    )
    RATE_LIMIT_EXCLUDE_PATHS: str = Field(
        default="/health,/metrics,/docs,/openapi.json",
        description="Comma-separated paths to exclude from rate limiting.",
    )

    # ----------------------------------------------------------
    # Derived / computed helpers
    # ----------------------------------------------------------
    @property
    def async_database_url(self) -> str:
        """
        Returns an asyncpg-compatible DSN.
        Replaces 'postgresql://' with 'postgresql+asyncpg://' so SQLAlchemy
        uses the async driver automatically.
        """
        url = self.DATABASE_URL
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if url.startswith("postgres://"):
            # Heroku-style DSN
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
        return url

    @property
    def sync_database_url(self) -> str:
        """
        Returns a psycopg2-compatible sync DSN for Celery tasks and Alembic.
        """
        url = self.DATABASE_URL
        if url.startswith("postgresql+asyncpg://"):
            return url.replace("postgresql+asyncpg://", "postgresql://", 1)
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql://", 1)
        return url

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() == "production"

    @property
    def is_development(self) -> bool:
        return self.APP_ENV.lower() == "development"

    @field_validator("JWT_SECRET")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        if v == "change-this-secret-key-in-production":
            import warnings

            warnings.warn(
                "JWT_SECRET is set to the default insecure value. "
                "Please set a strong random secret before deploying to production.",
                UserWarning,
                stacklevel=2,
            )
        if len(v) < 32:
            raise ValueError(
                "JWT_SECRET must be at least 32 characters long for security."
            )
        return v

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in valid_levels:
            raise ValueError(f"LOG_LEVEL must be one of {valid_levels}, got '{v}'.")
        return upper


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Returns the singleton Settings instance.

    Using @lru_cache ensures the .env file is only parsed once per process
    lifetime, which is critical for performance in async contexts.

    Usage:
        from config import get_settings
        settings = get_settings()
        print(settings.DATABASE_URL)

    In FastAPI dependency injection:
        from fastapi import Depends
        from config import Settings, get_settings

        @router.get("/info")
        def info(settings: Settings = Depends(get_settings)):
            return {"env": settings.APP_ENV}
    """
    return Settings()
