# =============================================================
# Hi-Tech Waste Management — Authentication Router
# JWT login / refresh / logout + role-based access control
# =============================================================

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import redis.asyncio as aioredis
from config import get_settings
from database import get_db
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()

# =============================================================
# Security helpers
# =============================================================

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(plain: str) -> str:
    """Return a bcrypt hash of the plain-text password."""
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain-text password against a bcrypt hash."""
    return pwd_context.verify(plain, hashed)


# =============================================================
# Token helpers
# =============================================================

# Valid user roles defined in the system
VALID_ROLES = {
    # New role taxonomy (from project plan)
    "superadmin",
    "management",
    "operations_manager",
    "field_supervisor",
    "driver",
    "compliance_officer",
    "client",
    # Legacy aliases kept for backward compatibility with existing auth tokens
    "admin",
    "supervisor",
    "weighbridge_operator",
    "finance",
    "client_portal",
    "viewer",
}

TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"


def _create_token(
    subject: str,
    token_type: str,
    extra_claims: dict[str, Any],
    expires_delta: timedelta,
) -> str:
    """
    Build and sign a JWT with standard + custom claims.

    Parameters
    ----------
    subject     : str   — typically the user's email address (``sub`` claim)
    token_type  : str   — ``"access"`` or ``"refresh"``
    extra_claims: dict  — additional data embedded in the payload (role, user_id, etc.)
    expires_delta: timedelta — how long until the token expires
    """
    now = datetime.now(tz=timezone.utc)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + expires_delta,
        "jti": str(uuid.uuid4()),  # Unique token ID — used for blacklisting
        "type": token_type,
        **extra_claims,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_access_token(subject: str, extra_claims: dict[str, Any]) -> str:
    """Issue a short-lived access token."""
    return _create_token(
        subject=subject,
        token_type=TOKEN_TYPE_ACCESS,
        extra_claims=extra_claims,
        expires_delta=timedelta(minutes=settings.JWT_EXPIRE_MINUTES),
    )


def create_refresh_token(subject: str, extra_claims: dict[str, Any]) -> str:
    """Issue a long-lived refresh token."""
    return _create_token(
        subject=subject,
        token_type=TOKEN_TYPE_REFRESH,
        extra_claims=extra_claims,
        expires_delta=timedelta(days=settings.JWT_REFRESH_EXPIRE_DAYS),
    )


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT.

    Raises
    ------
    JWTError  — if the token is malformed, expired, or the signature is invalid.
    """
    return jwt.decode(
        token,
        settings.JWT_SECRET,
        algorithms=[settings.JWT_ALGORITHM],
    )


# =============================================================
# Redis token-blacklist helpers
# =============================================================


async def _get_redis() -> aioredis.Redis:
    """Return a connected Redis client."""
    return aioredis.from_url(settings.REDIS_URL, decode_responses=True)


async def _blacklist_token(jti: str, exp: datetime) -> None:
    """
    Add a token JTI to the Redis blacklist.

    The key expires automatically when the token would have expired anyway,
    keeping the blacklist lean without a separate cleanup job.
    """
    try:
        r = await _get_redis()
        now = datetime.now(tz=timezone.utc)
        ttl_seconds = max(int((exp - now).total_seconds()), 1)
        await r.setex(f"token_blacklist:{jti}", ttl_seconds, "1")
        await r.aclose()
    except Exception as exc:
        # Non-fatal — log and continue; worst case a logged-out token
        # remains usable until it naturally expires.
        logger.error("Failed to blacklist token jti=%s: %s", jti, exc)


async def _is_token_blacklisted(jti: str) -> bool:
    """Return True if the token JTI is in the Redis blacklist."""
    try:
        r = await _get_redis()
        result = await r.exists(f"token_blacklist:{jti}")
        await r.aclose()
        return bool(result)
    except Exception as exc:
        logger.error("Redis blacklist check failed for jti=%s: %s", jti, exc)
        # Fail open — allow the token if Redis is unavailable
        return False


# =============================================================
# Pydantic request / response schemas
# =============================================================


class LoginRequest(BaseModel):
    username: EmailStr = Field(
        ...,
        description="User's email address used as the login identifier.",
        examples=["admin@hitechwaste.com.my"],
    )
    password: str = Field(
        ...,
        min_length=6,
        description="Account password (plain text — transmitted over HTTPS only).",
    )


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access token lifetime in seconds.")
    user: "UserInfo"


class UserInfo(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    is_active: bool


class RefreshRequest(BaseModel):
    refresh_token: str = Field(
        ...,
        description="A valid, non-expired, non-blacklisted refresh token.",
    )


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class LogoutRequest(BaseModel):
    refresh_token: Optional[str] = Field(
        default=None,
        description="If provided, the refresh token is also blacklisted.",
    )


class MessageResponse(BaseModel):
    message: str


# Rebuild so UserInfo is resolved inside TokenResponse
TokenResponse.model_rebuild()


# =============================================================
# Database helpers
# =============================================================


async def _get_user_by_email(email: str, db: AsyncSession) -> Optional[dict[str, Any]]:
    """
    Fetch a user row by email address.

    Returns a plain dict (column → value) or None if not found.
    Uses raw SQL to avoid importing the User ORM model here, keeping
    the auth module self-contained.
    """
    result = await db.execute(
        text(
            """
            SELECT
                id::text,
                email,
                hashed_password,
                full_name,
                role,
                is_active,
                created_at
            FROM users
            WHERE email = :email
            LIMIT 1
            """
        ),
        {"email": email.lower().strip()},
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def _get_user_by_id(user_id: str, db: AsyncSession) -> Optional[dict[str, Any]]:
    """Fetch a user row by UUID string."""
    result = await db.execute(
        text(
            """
            SELECT
                id::text,
                email,
                hashed_password,
                full_name,
                role,
                is_active,
                created_at
            FROM users
            WHERE id = :user_id
            LIMIT 1
            """
        ),
        {"user_id": user_id},
    )
    row = result.mappings().first()
    return dict(row) if row else None


# =============================================================
# Core FastAPI dependencies
# =============================================================


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    FastAPI dependency that decodes the Bearer JWT, checks the blacklist,
    and returns the authenticated user dict.

    Raises HTTP 401 if the token is missing, malformed, expired, or blacklisted.
    Raises HTTP 403 if the user account is inactive.

    Usage
    -----
    ::

        @router.get("/protected")
        async def protected(user: dict = Depends(get_current_user)):
            return {"hello": user["email"]}
    """
    _unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise _unauthorized

    token = credentials.credentials

    # Decode and validate the JWT signature + expiry
    try:
        payload = decode_token(token)
    except JWTError as exc:
        logger.debug("JWT decode failed: %s", exc)
        raise _unauthorized from exc

    # Ensure this is an access token, not a refresh token
    if payload.get("type") != TOKEN_TYPE_ACCESS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh tokens cannot be used for API access.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check blacklist (handles logout)
    jti = payload.get("jti", "")
    if await _is_token_blacklisted(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Load the user from the database to get fresh role + active status
    user_id: Optional[str] = payload.get("user_id")
    if not user_id:
        raise _unauthorized

    user = await _get_user_by_id(user_id, db)
    if not user:
        raise _unauthorized

    if not user.get("is_active", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated. Contact an administrator.",
        )

    # Attach the decoded payload for downstream use (e.g. jti, exp)
    user["_jwt_payload"] = payload
    # Add 'sub' for compatibility with code expecting JWT-style claims
    user["sub"] = user.get("id")
    return user


def require_roles(*roles: str):
    """
    Dependency factory that restricts an endpoint to users whose role
    is included in the provided list.

    Usage
    -----
    ::

        @router.delete("/clients/{id}")
        async def delete_client(
            user: dict = Depends(require_roles("admin", "supervisor")),
        ):
            ...

    Parameters
    ----------
    *roles : str
        One or more role names (must be members of ``VALID_ROLES``).

    Returns
    -------
    A FastAPI dependency callable that returns the authenticated user dict
    on success, or raises HTTP 403 if the user's role is not in ``roles``.
    """
    # Validate role names at definition time to catch typos early
    invalid = set(roles) - VALID_ROLES
    if invalid:
        raise ValueError(
            f"require_roles() received unknown role(s): {invalid}. "
            f"Valid roles are: {VALID_ROLES}"
        )

    allowed = frozenset(roles)

    async def _role_checker(
        current_user: dict[str, Any] = Depends(get_current_user),
    ) -> dict[str, Any]:
        if current_user.get("role") not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Access denied. Required role(s): {sorted(allowed)}. "
                    f"Your role: {current_user.get('role', 'unknown')}."
                ),
            )
        return current_user

    return _role_checker


# =============================================================
# POST /login
# =============================================================


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and obtain JWT tokens",
    responses={
        200: {"description": "Login successful — returns access + refresh tokens."},
        401: {"description": "Invalid email or password."},
        403: {"description": "Account is deactivated."},
        422: {
            "description": "Validation error — check email format / password length."
        },
    },
)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Authenticate a user with their email and password.

    On success, returns a short-lived **access token** (used as a Bearer token
    on all subsequent API calls) and a long-lived **refresh token** (stored
    securely by the frontend and used only to obtain new access tokens).

    Both tokens are signed JWTs containing the user's ID, email, role, and
    a unique ``jti`` claim used for revocation.
    """
    _invalid_creds = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email address or password.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Fetch user — normalise email to lowercase
    user = await _get_user_by_email(body.username, db)

    if user is None:
        # Perform a dummy verify to prevent timing-based user enumeration
        pwd_context.dummy_verify()
        raise _invalid_creds

    # Verify password
    if not verify_password(body.password, user["hashed_password"]):
        logger.warning("Failed login attempt for email=%s", body.username)
        raise _invalid_creds

    # Reject inactive accounts
    if not user.get("is_active", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated. Please contact an administrator.",
        )

    # Build token claims
    common_claims = {
        "user_id": user["id"],
        "email": user["email"],
        "role": user["role"],
        "full_name": user["full_name"],
    }

    access_token = create_access_token(
        subject=user["email"], extra_claims=common_claims
    )
    refresh_token = create_refresh_token(
        subject=user["email"], extra_claims=common_claims
    )

    logger.info("Successful login | user=%s | role=%s", user["email"], user["role"])

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.JWT_EXPIRE_MINUTES * 60,
        user=UserInfo(
            id=user["id"],
            email=user["email"],
            full_name=user["full_name"],
            role=user["role"],
            is_active=user["is_active"],
        ),
    )


# =============================================================
# POST /refresh
# =============================================================


@router.post(
    "/refresh",
    response_model=AccessTokenResponse,
    summary="Exchange a refresh token for a new access token",
    responses={
        200: {"description": "New access token issued."},
        401: {"description": "Refresh token is invalid, expired, or revoked."},
        403: {"description": "Account is deactivated."},
    },
)
async def refresh_access_token(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> AccessTokenResponse:
    """
    Issue a new **access token** in exchange for a valid refresh token.

    The refresh token is validated (signature, expiry, blacklist) and the
    user's current role and active status are re-fetched from the database
    so that permission changes take effect immediately on the next refresh.

    The refresh token itself is **not** rotated — the same refresh token
    remains valid until it expires or is explicitly revoked via ``/logout``.
    """
    _invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Decode
    try:
        payload = decode_token(body.refresh_token)
    except JWTError as exc:
        logger.debug("Refresh token decode failed: %s", exc)
        raise _invalid from exc

    # Must be a refresh token
    if payload.get("type") != TOKEN_TYPE_REFRESH:
        raise _invalid

    # Check blacklist
    jti = payload.get("jti", "")
    if await _is_token_blacklisted(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Re-fetch the user to pick up any role / active status changes
    user_id: Optional[str] = payload.get("user_id")
    if not user_id:
        raise _invalid

    user = await _get_user_by_id(user_id, db)
    if not user:
        raise _invalid

    if not user.get("is_active", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated.",
        )

    # Issue a fresh access token with up-to-date claims
    new_access_token = create_access_token(
        subject=user["email"],
        extra_claims={
            "user_id": user["id"],
            "email": user["email"],
            "role": user["role"],
            "full_name": user["full_name"],
        },
    )

    logger.info("Access token refreshed | user=%s", user["email"])

    return AccessTokenResponse(
        access_token=new_access_token,
        token_type="bearer",
        expires_in=settings.JWT_EXPIRE_MINUTES * 60,
    )


# =============================================================
# POST /logout
# =============================================================


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Revoke the current session tokens",
    responses={
        200: {"description": "Tokens successfully revoked."},
        401: {"description": "Not authenticated."},
    },
)
async def logout(
    body: LogoutRequest,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> MessageResponse:
    """
    Revoke the current access token (and optionally the refresh token).

    Both token JTIs are written to the Redis blacklist with TTLs matching
    their remaining validity windows, so the blacklist remains bounded in size.

    The client should discard both tokens from local storage after calling
    this endpoint.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No authentication token provided.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    revoked: list[str] = []

    # Blacklist the access token
    try:
        access_payload = decode_token(credentials.credentials)
        jti = access_payload.get("jti", "")
        exp_ts = access_payload.get("exp")
        exp_dt = (
            datetime.fromtimestamp(exp_ts, tz=timezone.utc)
            if exp_ts
            else (
                datetime.now(tz=timezone.utc)
                + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
            )
        )
        if jti:
            await _blacklist_token(jti, exp_dt)
            revoked.append("access_token")
    except JWTError:
        # Token already expired — nothing to revoke
        pass

    # Blacklist the refresh token if provided
    if body.refresh_token:
        try:
            refresh_payload = decode_token(body.refresh_token)
            jti = refresh_payload.get("jti", "")
            exp_ts = refresh_payload.get("exp")
            exp_dt = (
                datetime.fromtimestamp(exp_ts, tz=timezone.utc)
                if exp_ts
                else (
                    datetime.now(tz=timezone.utc)
                    + timedelta(days=settings.JWT_REFRESH_EXPIRE_DAYS)
                )
            )
            if jti:
                await _blacklist_token(jti, exp_dt)
                revoked.append("refresh_token")
        except JWTError:
            pass

    user_sub = "unknown"
    try:
        user_sub = decode_token(credentials.credentials).get("sub", "unknown")
    except Exception:
        pass

    logger.info("Logout | user=%s | revoked=%s", user_sub, revoked)

    return MessageResponse(message="Successfully logged out. Tokens have been revoked.")


# =============================================================
# GET /me
# =============================================================


@router.get(
    "/me",
    response_model=UserInfo,
    summary="Return the currently authenticated user's profile",
    responses={
        200: {"description": "Authenticated user info."},
        401: {"description": "Not authenticated or token expired."},
    },
)
async def get_me(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> UserInfo:
    """
    Return the profile of the currently authenticated user.

    Useful for the frontend to hydrate the user context on page load
    without decoding the JWT client-side.
    """
    return UserInfo(
        id=current_user["id"],
        email=current_user["email"],
        full_name=current_user["full_name"],
        role=current_user["role"],
        is_active=current_user["is_active"],
    )
