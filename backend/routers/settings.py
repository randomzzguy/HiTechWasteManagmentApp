# =============================================================
# Hi-Tech Waste Management — Settings Router
# User management and system configuration endpoints
# =============================================================

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.user import User, UserCreate, UserRead, UserUpdate, VALID_ROLES
from routers.auth import get_current_user, hash_password, require_roles

router = APIRouter()


# =============================================================
# Notification endpoints
# =============================================================


@router.post("/test-email")
async def test_email_endpoint(
    payload: dict,
    current_user: Any = Depends(get_current_user),
) -> dict:
    """Send a test email to verify SMTP configuration."""
    from services.notification_service import send_test_email

    to = payload.get("to") or current_user.get("email", "")
    if not to:
        raise HTTPException(status_code=400, detail="Email address required")

    success = await send_test_email(to=to)
    return {
        "success": success,
        "message": "Test email sent" if success else "SMTP not configured or failed",
    }


# =============================================================
# User management endpoints
# =============================================================


@router.get("/users/")
async def list_users(
    skip: int = 0,
    limit: int = 50,
    role: str | None = None,
    is_active: bool | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> dict:
    """List platform users."""
    from sqlalchemy import text

    conditions = ["1=1"]
    params: dict[str, Any] = {"skip": skip, "limit": limit}

    if role:
        conditions.append("role = :role")
        params["role"] = role
    if is_active is not None:
        conditions.append("is_active = :is_active")
        params["is_active"] = is_active

    where = " AND ".join(conditions)

    rows = (
        await db.execute(
            text(
                f"""
                SELECT id::text, email, full_name, role, is_active, created_at
                FROM users
                WHERE {where}
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :skip
                """
            ),
            params,
        )
    ).mappings().all()

    total_row = await db.execute(
        text(f"SELECT COUNT(*) FROM users WHERE {where}"),
        {k: v for k, v in params.items() if k not in ("skip", "limit")},
    )
    total = total_row.scalar() or 0

    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/config/")
async def get_system_config(
    current_user: Any = Depends(get_current_user),
) -> dict:
    """Return non-sensitive system configuration status."""
    from config import get_settings

    s = get_settings()
    return {
        "smtp_configured": bool(s.SMTP_USER and s.SMTP_PASSWORD),
        "smtp_host": s.SMTP_HOST,
        "smtp_from_name": s.SMTP_FROM_NAME,
        "whatsapp_configured": bool(s.WHATSAPP_API_URL and s.WHATSAPP_API_TOKEN),
        "app_env": s.APP_ENV,
        "app_version": s.APP_VERSION,
        "ollama_model": s.OLLAMA_MODEL,
    }


# =============================================================
# User management — create / update / deactivate
# =============================================================


@router.post(
    "/users/",
    status_code=status.HTTP_201_CREATED,
    response_model=UserRead,
)
async def create_user(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(require_roles("superadmin", "management")),
) -> UserRead:
    """Create a new platform user (admin only)."""
    try:
        payload.validate_role()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    # Check email uniqueness
    existing = await db.execute(
        select(User).where(User.email == payload.email)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A user with email '{payload.email}' already exists.",
        )

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,
        is_active=payload.is_active,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return UserRead.model_validate(user)


@router.patch(
    "/users/{user_id}/",
    response_model=UserRead,
)
async def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(require_roles("superadmin", "management")),
) -> UserRead:
    """Partially update a platform user (admin only)."""
    try:
        payload.validate_role()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{user_id}' not found.",
        )

    update_data = payload.model_dump(exclude_none=True)

    # Handle password separately — hash before storing
    if "password" in update_data:
        user.hashed_password = hash_password(update_data.pop("password"))

    for field, value in update_data.items():
        setattr(user, field, value)

    await db.commit()
    await db.refresh(user)
    return UserRead.model_validate(user)


@router.post(
    "/users/{user_id}/deactivate/",
    response_model=UserRead,
)
async def deactivate_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(require_roles("superadmin", "management")),
) -> UserRead:
    """Deactivate a platform user (idempotent, admin only)."""
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{user_id}' not found.",
        )

    user.is_active = False
    await db.commit()
    await db.refresh(user)
    return UserRead.model_validate(user)
