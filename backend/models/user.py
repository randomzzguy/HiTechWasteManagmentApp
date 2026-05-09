# =============================================================
# Hi-Tech Waste Management — User Model
# SQLAlchemy 2.0 async ORM + Pydantic v2 schemas
# =============================================================

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from database import Base
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

# =============================================================
# SQLAlchemy ORM Model
# =============================================================


class User(Base):
    """
    Represents a platform user.

    Roles:
        superadmin          — Full system access
        management          — Read/write across all modules
        operations_manager  — Manage jobs, fleet, compliance
        field_supervisor    — Oversee field operations and drivers
        driver              — Mobile app access, job updates
        compliance_officer  — Scheduled waste and regulatory access
        client              — Client portal read access
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="client",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} role={self.role}>"


# =============================================================
# Pydantic Schemas
# =============================================================

VALID_ROLES = {
    "superadmin",
    "management",
    "operations_manager",
    "field_supervisor",
    "driver",
    "compliance_officer",
    "client",
}


class UserCreate(BaseModel):
    """Schema for creating a new user (admin use)."""

    email: EmailStr
    password: str = Field(
        ...,
        min_length=8,
        description="Plain-text password — will be hashed before storage",
    )
    full_name: str = Field(..., min_length=1, max_length=255)
    role: str = Field(default="client")
    is_active: bool = Field(default=True)

    model_config = {"str_strip_whitespace": True}

    def validate_role(self) -> "UserCreate":
        if self.role not in VALID_ROLES:
            raise ValueError(f"role must be one of {sorted(VALID_ROLES)}")
        return self


class UserRead(BaseModel):
    """Schema returned to API consumers — never exposes hashed_password."""

    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    """Schema for partial updates to a user record."""

    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(
        default=None,
        min_length=8,
        description="New plain-text password — will be hashed",
    )

    model_config = {"str_strip_whitespace": True}

    def validate_role(self) -> "UserUpdate":
        if self.role is not None and self.role not in VALID_ROLES:
            raise ValueError(f"role must be one of {sorted(VALID_ROLES)}")
        return self


# =============================================================
# JWT / Auth Schemas
# =============================================================


class Token(BaseModel):
    """Returned after successful login."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access token lifetime in seconds")


class TokenData(BaseModel):
    """Decoded payload carried inside a JWT access token."""

    sub: str = Field(description="User UUID as string")
    email: str
    role: str
    exp: Optional[int] = None
    iat: Optional[int] = None
    jti: Optional[str] = Field(default=None, description="JWT ID for blacklisting")
