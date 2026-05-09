# =============================================================
# Hi-Tech Waste Management — Settings User Management Tests
# pytest + pytest-asyncio + httpx.AsyncClient + hypothesis
#
# Tests cover:
#   - Task 6.1: Fixtures (async client, admin token, seeded user)
#   - Task 6.2: Property 7 — backend create stores hashed password
#   - Task 6.3: Property 8 — backend partial update applies only provided fields
#   - Task 6.4: Property 9 — backend password update stores new bcrypt hash
#   - Task 6.5: Property 10 — deactivation is idempotent
#   - Task 6.6: Integration tests for error cases
#
# Architecture notes:
#   - Uses SQLite in-memory DB (aiosqlite) — only the users table is created
#   - get_current_user is overridden to avoid PostgreSQL-specific raw SQL
#     (id::text cast) in auth.py that SQLite cannot parse
#   - require_roles dependency is overridden per test class to simulate
#     admin vs non-admin callers
# =============================================================

from __future__ import annotations

import uuid
from typing import Any, AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

# ── Import app and dependencies ───────────────────────────────
from database import get_db
from main import app
from models.user import VALID_ROLES, User, UserRead, UserUpdate
from routers.auth import (
    hash_password,
    require_roles,
    verify_password,
)

# =============================================================
# SQLite in-memory engine for tests
# =============================================================

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False,
)


@event.listens_for(test_engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# =============================================================
# Override get_db dependency to use the test SQLite DB
# =============================================================


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# =============================================================
# Mock user dicts returned by auth dependencies
# =============================================================

ADMIN_USER_DICT: dict[str, Any] = {
    "id": str(uuid.uuid4()),
    "email": "admin@test.com",
    "full_name": "Admin User",
    "role": "superadmin",
    "is_active": True,
}

NON_ADMIN_USER_DICT: dict[str, Any] = {
    "id": str(uuid.uuid4()),
    "email": "driver@test.com",
    "full_name": "Driver User",
    "role": "driver",
    "is_active": True,
}


async def override_get_current_user_admin() -> dict[str, Any]:
    """Dependency override: always returns a superadmin user."""
    return ADMIN_USER_DICT


async def override_get_current_user_non_admin() -> dict[str, Any]:
    """Dependency override: always returns a non-admin (driver) user."""
    return NON_ADMIN_USER_DICT


def make_admin_require_roles_override():
    """Returns a dependency override for require_roles that passes as admin."""
    async def _override() -> dict[str, Any]:
        return ADMIN_USER_DICT
    return _override


def make_non_admin_require_roles_override():
    """Returns a dependency override for require_roles that raises 403."""
    from fastapi import HTTPException, status

    async def _override() -> dict[str, Any]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Required role(s): ['management', 'superadmin']. Your role: driver.",
        )
    return _override


# =============================================================
# Pytest session-scoped fixture: create only the users table
# We cannot use Base.metadata.create_all because other models
# use PostgreSQL-specific types (ARRAY, etc.) that SQLite cannot
# compile. We create only the users table directly.
# =============================================================


@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_test_tables():
    """Create only the users table in the in-memory SQLite DB."""
    async with test_engine.begin() as conn:
        await conn.run_sync(User.__table__.create, checkfirst=True)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(User.__table__.drop, checkfirst=True)


# =============================================================
# Async HTTP client fixture — admin context
# =============================================================


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """
    Async test client with admin auth overrides and SQLite DB.
    The require_roles dependency is overridden to return an admin user.
    """
    # Override get_db
    app.dependency_overrides[get_db] = override_get_db

    # Override require_roles for the settings endpoints
    # require_roles returns a new callable each time it's called, so we
    # override get_current_user which is the base dependency
    from routers.auth import get_current_user
    app.dependency_overrides[get_current_user] = override_get_current_user_admin

    # Also override the require_roles dependency used by settings endpoints
    # by patching the inner _role_checker via get_current_user override
    # (require_roles wraps get_current_user, so overriding get_current_user
    # is sufficient for the role check to pass for admin)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def non_admin_client() -> AsyncGenerator[AsyncClient, None]:
    """
    Async test client with non-admin auth overrides.
    The require_roles dependency raises 403 for non-admin users.
    """
    app.dependency_overrides[get_db] = override_get_db

    from routers.auth import get_current_user
    app.dependency_overrides[get_current_user] = override_get_current_user_non_admin

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# =============================================================
# Fixture: seeded regular test user in the test DB
# =============================================================


@pytest_asyncio.fixture
async def seeded_test_user() -> AsyncGenerator[dict[str, Any], None]:
    """
    Insert a regular 'driver' user into the test DB and return its data.
    Cleaned up after each test.
    """
    user_id = uuid.uuid4()
    async with TestSessionLocal() as session:
        user = User(
            id=user_id,
            email=f"driver-{user_id}@test.com",
            hashed_password=hash_password("driverpassword123"),
            full_name="Driver User",
            role="driver",
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        data = {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "is_active": user.is_active,
            "hashed_password": user.hashed_password,
        }

    yield data

    # Cleanup
    async with TestSessionLocal() as session:
        u = await session.get(User, user_id)
        if u:
            await session.delete(u)
            await session.commit()


# =============================================================
# Helper: create a user via the API
# =============================================================


async def api_create_user(
    ac: AsyncClient,
    *,
    email: str | None = None,
    password: str = "testpassword123",
    full_name: str = "Test Person",
    role: str = "driver",
    is_active: bool = True,
) -> Any:
    if email is None:
        email = f"user-{uuid.uuid4()}@test.com"
    return await ac.post(
        "/api/v1/settings/users/",
        json={
            "email": email,
            "password": password,
            "full_name": full_name,
            "role": role,
            "is_active": is_active,
        },
    )


# =============================================================
# Task 6.2 — Property 7: Backend create stores hashed password
#             and returns safe UserRead
# Validates: Requirements 5.1, 5.2
# =============================================================

try:
    from hypothesis import HealthCheck
    from hypothesis import given
    from hypothesis import settings as h_settings
    from hypothesis import strategies as st

    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False


if HYPOTHESIS_AVAILABLE:

    @pytest.mark.asyncio
    @given(
        full_name=st.text(min_size=1, max_size=80).filter(lambda s: s.strip()),
        password=st.text(
            min_size=8,
            max_size=40,
            alphabet=st.characters(
                whitelist_categories=("Lu", "Ll", "Nd"),
                whitelist_characters="!@#$%",
            ),
        ),
        role=st.sampled_from(sorted(VALID_ROLES)),
        is_active=st.booleans(),
    )
    @h_settings(
        max_examples=15,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
        deadline=None,
    )
    async def test_property7_create_stores_hashed_password_returns_safe_userread(
        full_name: str,
        password: str,
        role: str,
        is_active: bool,
    ):
        """
        **Property 7: Backend create stores hashed password and returns safe UserRead**

        For any valid UserCreate payload, POST /users/ should:
        - Store a hashed_password that differs from the plain-text password
        - Return a response body that does NOT contain hashed_password
        - Return a response body with id, email, full_name, role, is_active, created_at
        - The stored hash must verify correctly against the plain-text password

        **Validates: Requirements 5.1, 5.2**
        """
        from routers.auth import get_current_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user_admin

        test_email = f"prop7-{uuid.uuid4()}@test.com"
        created_id = None

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                response = await ac.post(
                    "/api/v1/settings/users/",
                    json={
                        "email": test_email,
                        "password": password,
                        "full_name": full_name,
                        "role": role,
                        "is_active": is_active,
                    },
                )

            # Assert 201 Created
            assert response.status_code == 201, (
                f"Expected 201, got {response.status_code}: {response.text}"
            )

            body = response.json()

            # Assert hashed_password is NOT in the response body (Req 5.2)
            assert "hashed_password" not in body, "hashed_password must not be in response"

            # Assert required fields are present (Req 5.2)
            for field in ("id", "email", "full_name", "role", "is_active", "created_at"):
                assert field in body, f"Field '{field}' missing from response"

            # Assert the stored hash verifies against the plain-text password (Req 5.1)
            created_id = uuid.UUID(body["id"])
            async with TestSessionLocal() as session:
                stored_user = await session.get(User, created_id)
                assert stored_user is not None
                assert stored_user.hashed_password != password, "Password must be hashed"
                assert verify_password(password, stored_user.hashed_password), (
                    "Stored hash must verify against plain-text password"
                )

        finally:
            # Cleanup created user
            if created_id:
                async with TestSessionLocal() as session:
                    u = await session.get(User, created_id)
                    if u:
                        await session.delete(u)
                        await session.commit()
            app.dependency_overrides.clear()


# =============================================================
# Task 6.3 — Property 8: Backend partial update applies only
#             provided fields
# Validates: Requirements 6.1
# =============================================================

if HYPOTHESIS_AVAILABLE:

    @pytest.mark.asyncio
    @given(
        new_full_name=st.text(min_size=1, max_size=80).filter(lambda s: s.strip()),
        new_role=st.sampled_from(sorted(VALID_ROLES)),
        new_is_active=st.booleans(),
        update_name=st.booleans(),
        update_role=st.booleans(),
        update_active=st.booleans(),
    )
    @h_settings(
        max_examples=15,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
        deadline=None,
    )
    async def test_property8_partial_update_applies_only_provided_fields(
        new_full_name: str,
        new_role: str,
        new_is_active: bool,
        update_name: bool,
        update_role: bool,
        update_active: bool,
    ):
        """
        **Property 8: Backend partial update applies only provided fields**

        For any existing user and any UserUpdate payload with a non-empty subset
        of fields, PATCH /users/{id}/ should update exactly those fields and
        leave all other fields unchanged.

        **Validates: Requirements 6.1**
        """
        # Skip if no fields are being updated (empty payload is a no-op)
        if not update_name and not update_role and not update_active:
            return

        from routers.auth import get_current_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user_admin

        target_id = uuid.uuid4()
        original_email = f"prop8-target-{target_id}@test.com"
        original_name = "Original Name"
        original_role = "driver"
        original_active = True

        try:
            async with TestSessionLocal() as session:
                target = User(
                    id=target_id,
                    email=original_email,
                    hashed_password=hash_password("originalpassword123"),
                    full_name=original_name,
                    role=original_role,
                    is_active=original_active,
                )
                session.add(target)
                await session.commit()

            # Build partial update payload
            patch_payload: dict[str, Any] = {}
            if update_name:
                patch_payload["full_name"] = new_full_name
            if update_role:
                patch_payload["role"] = new_role
            if update_active:
                patch_payload["is_active"] = new_is_active

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                response = await ac.patch(
                    f"/api/v1/settings/users/{target_id}/",
                    json=patch_payload,
                )

            assert response.status_code == 200, (
                f"Expected 200, got {response.status_code}: {response.text}"
            )

            # Verify DB state
            async with TestSessionLocal() as session:
                updated = await session.get(User, target_id)
                assert updated is not None

                if update_name:
                    assert updated.full_name == new_full_name
                else:
                    assert updated.full_name == original_name

                if update_role:
                    assert updated.role == new_role
                else:
                    assert updated.role == original_role

                if update_active:
                    assert updated.is_active == new_is_active
                else:
                    assert updated.is_active == original_active

                # Email should never change (not in payload)
                assert updated.email == original_email

        finally:
            async with TestSessionLocal() as session:
                u = await session.get(User, target_id)
                if u:
                    await session.delete(u)
                    await session.commit()
            app.dependency_overrides.clear()


# =============================================================
# Task 6.4 — Property 9: Backend password update stores new
#             bcrypt hash
# Validates: Requirements 6.2
# =============================================================

if HYPOTHESIS_AVAILABLE:

    @pytest.mark.asyncio
    @given(
        new_password=st.text(
            min_size=8,
            max_size=40,
            alphabet=st.characters(
                whitelist_categories=("Lu", "Ll", "Nd"),
                whitelist_characters="!@#$%",
            ),
        )
    )
    @h_settings(
        max_examples=10,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
        deadline=None,
    )
    async def test_property9_password_update_stores_new_bcrypt_hash(
        new_password: str,
    ):
        """
        **Property 9: Backend password update stores new bcrypt hash**

        For any UserUpdate payload that includes a password field, the stored
        hashed_password after PATCH should verify correctly against the new
        plain-text password and should differ from the previous hashed_password.

        **Validates: Requirements 6.2**
        """
        from routers.auth import get_current_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user_admin

        target_id = uuid.uuid4()
        original_plain = "originalpassword123"
        original_hash = hash_password(original_plain)

        try:
            async with TestSessionLocal() as session:
                target = User(
                    id=target_id,
                    email=f"prop9-target-{target_id}@test.com",
                    hashed_password=original_hash,
                    full_name="Target User",
                    role="driver",
                    is_active=True,
                )
                session.add(target)
                await session.commit()

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                response = await ac.patch(
                    f"/api/v1/settings/users/{target_id}/",
                    json={"password": new_password},
                )

            assert response.status_code == 200, (
                f"Expected 200, got {response.status_code}: {response.text}"
            )

            # Verify the new hash is stored and verifies correctly
            async with TestSessionLocal() as session:
                updated = await session.get(User, target_id)
                assert updated is not None
                assert updated.hashed_password != new_password, "Password must be hashed"
                assert verify_password(new_password, updated.hashed_password), (
                    "New hash must verify against new plain-text password"
                )
                # Hash should differ from original (bcrypt salts ensure this)
                assert updated.hashed_password != original_hash, (
                    "New hash should differ from original hash"
                )

        finally:
            async with TestSessionLocal() as session:
                u = await session.get(User, target_id)
                if u:
                    await session.delete(u)
                    await session.commit()
            app.dependency_overrides.clear()


# =============================================================
# Task 6.5 — Property 10: Deactivation is idempotent
# Validates: Requirements 7.1, 7.5
# =============================================================

if HYPOTHESIS_AVAILABLE:

    @pytest.mark.asyncio
    @given(initially_active=st.booleans())
    @h_settings(
        max_examples=8,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
        deadline=None,
    )
    async def test_property10_deactivation_is_idempotent(initially_active: bool):
        """
        **Property 10: Deactivation is idempotent**

        For any user record (whether currently active or inactive), calling
        POST /users/{id}/deactivate/ should always result in is_active=false
        and return 200 OK — calling it a second time should produce the same
        outcome as calling it once.

        **Validates: Requirements 7.1, 7.5**
        """
        from routers.auth import get_current_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user_admin

        target_id = uuid.uuid4()

        try:
            async with TestSessionLocal() as session:
                target = User(
                    id=target_id,
                    email=f"prop10-target-{target_id}@test.com",
                    hashed_password=hash_password("targetpassword123"),
                    full_name="Target User",
                    role="driver",
                    is_active=initially_active,
                )
                session.add(target)
                await session.commit()

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                # First deactivation call
                resp1 = await ac.post(
                    f"/api/v1/settings/users/{target_id}/deactivate/",
                )
                # Second deactivation call (idempotent)
                resp2 = await ac.post(
                    f"/api/v1/settings/users/{target_id}/deactivate/",
                )

            # Both calls must return 200 OK
            assert resp1.status_code == 200, (
                f"First call: expected 200, got {resp1.status_code}"
            )
            assert resp2.status_code == 200, (
                f"Second call: expected 200, got {resp2.status_code}"
            )

            # Both responses must have is_active=false
            assert resp1.json()["is_active"] is False
            assert resp2.json()["is_active"] is False

            # DB state must be is_active=false
            async with TestSessionLocal() as session:
                updated = await session.get(User, target_id)
                assert updated is not None
                assert updated.is_active is False

        finally:
            async with TestSessionLocal() as session:
                u = await session.get(User, target_id)
                if u:
                    await session.delete(u)
                    await session.commit()
            app.dependency_overrides.clear()


# =============================================================
# Task 6.6 — Integration tests for error cases
# Validates: Requirements 5.3, 5.4, 5.5, 6.4, 6.6, 7.3, 7.4
# =============================================================


class TestCreateUserErrors:
    """Integration tests for POST /api/v1/settings/users/ error cases."""

    @pytest.mark.asyncio
    async def test_duplicate_email_returns_409(
        self, client: AsyncClient, seeded_test_user: dict
    ):
        """
        POST /users/ with an email that already exists in the DB
        must return 409 Conflict.

        Validates: Requirement 5.3
        """
        response = await client.post(
            "/api/v1/settings/users/",
            json={
                "email": seeded_test_user["email"],  # already exists
                "password": "newpassword123",
                "full_name": "Duplicate User",
                "role": "driver",
                "is_active": True,
            },
        )
        assert response.status_code == 409
        body = response.json()
        # Our custom error envelope: {"error": {"code": 409, "detail": "..."}}
        detail = body.get("error", {}).get("detail", body.get("detail", ""))
        assert (
            seeded_test_user["email"] in str(detail)
            or "already exists" in str(detail).lower()
        )

    @pytest.mark.asyncio
    async def test_invalid_role_returns_422(self, client: AsyncClient):
        """
        POST /users/ with a role value not in VALID_ROLES must return 422.

        Validates: Requirement 5.4
        """
        response = await client.post(
            "/api/v1/settings/users/",
            json={
                "email": f"invalid-role-{uuid.uuid4()}@test.com",
                "password": "testpassword123",
                "full_name": "Invalid Role User",
                "role": "not_a_real_role",
                "is_active": True,
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_non_admin_create_returns_403(
        self, non_admin_client: AsyncClient
    ):
        """
        POST /users/ with a non-admin JWT must return 403 Forbidden.

        Validates: Requirement 5.5
        """
        response = await non_admin_client.post(
            "/api/v1/settings/users/",
            json={
                "email": f"forbidden-{uuid.uuid4()}@test.com",
                "password": "testpassword123",
                "full_name": "Forbidden User",
                "role": "driver",
                "is_active": True,
            },
        )
        assert response.status_code == 403


class TestUpdateUserErrors:
    """Integration tests for PATCH /api/v1/settings/users/{id}/ error cases."""

    @pytest.mark.asyncio
    async def test_unknown_uuid_returns_404(self, client: AsyncClient):
        """
        PATCH /users/{id}/ with a UUID that doesn't exist must return 404.

        Validates: Requirement 6.4
        """
        unknown_id = uuid.uuid4()
        response = await client.patch(
            f"/api/v1/settings/users/{unknown_id}/",
            json={"full_name": "Ghost User"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_invalid_role_in_update_returns_422(
        self, client: AsyncClient, seeded_test_user: dict
    ):
        """
        PATCH /users/{id}/ with an invalid role must return 422.

        Validates: Requirement 6.5
        """
        response = await client.patch(
            f"/api/v1/settings/users/{seeded_test_user['id']}/",
            json={"role": "not_a_real_role"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_non_admin_update_returns_403(
        self, non_admin_client: AsyncClient, seeded_test_user: dict
    ):
        """
        PATCH /users/{id}/ with a non-admin JWT must return 403 Forbidden.

        Validates: Requirement 6.6
        """
        response = await non_admin_client.patch(
            f"/api/v1/settings/users/{seeded_test_user['id']}/",
            json={"full_name": "Hacked Name"},
        )
        assert response.status_code == 403


class TestDeactivateUserErrors:
    """Integration tests for POST /api/v1/settings/users/{id}/deactivate/ error cases."""

    @pytest.mark.asyncio
    async def test_unknown_uuid_returns_404(self, client: AsyncClient):
        """
        POST /users/{id}/deactivate/ with a UUID that doesn't exist must return 404.

        Validates: Requirement 7.3
        """
        unknown_id = uuid.uuid4()
        response = await client.post(
            f"/api/v1/settings/users/{unknown_id}/deactivate/",
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_non_admin_deactivate_returns_403(
        self, non_admin_client: AsyncClient, seeded_test_user: dict
    ):
        """
        POST /users/{id}/deactivate/ with a non-admin JWT must return 403 Forbidden.

        Validates: Requirement 7.4
        """
        response = await non_admin_client.post(
            f"/api/v1/settings/users/{seeded_test_user['id']}/deactivate/",
        )
        assert response.status_code == 403


# =============================================================
# Happy-path integration tests (smoke tests)
# =============================================================


class TestCreateUserHappyPath:
    """Smoke tests for the create user endpoint happy path."""

    @pytest.mark.asyncio
    async def test_create_user_returns_201_and_userread(self, client: AsyncClient):
        """
        POST /users/ with valid payload returns 201 and a UserRead body
        without hashed_password.

        Validates: Requirements 5.1, 5.2
        """
        email = f"happy-{uuid.uuid4()}@test.com"
        response = await client.post(
            "/api/v1/settings/users/",
            json={
                "email": email,
                "password": "securepassword123",
                "full_name": "Happy Path User",
                "role": "compliance_officer",
                "is_active": True,
            },
        )
        assert response.status_code == 201
        body = response.json()
        assert body["email"] == email
        assert body["full_name"] == "Happy Path User"
        assert body["role"] == "compliance_officer"
        assert body["is_active"] is True
        assert "hashed_password" not in body
        assert "id" in body
        assert "created_at" in body

        # Cleanup
        created_id = uuid.UUID(body["id"])
        async with TestSessionLocal() as session:
            u = await session.get(User, created_id)
            if u:
                await session.delete(u)
                await session.commit()

    @pytest.mark.asyncio
    async def test_create_user_password_is_hashed_in_db(self, client: AsyncClient):
        """
        POST /users/ stores a bcrypt hash, not the plain-text password.

        Validates: Requirement 5.1
        """
        plain_password = "plaintextpassword123"
        email = f"hashcheck-{uuid.uuid4()}@test.com"
        response = await client.post(
            "/api/v1/settings/users/",
            json={
                "email": email,
                "password": plain_password,
                "full_name": "Hash Check User",
                "role": "driver",
                "is_active": True,
            },
        )
        assert response.status_code == 201
        created_id = uuid.UUID(response.json()["id"])

        async with TestSessionLocal() as session:
            user = await session.get(User, created_id)
            assert user is not None
            assert user.hashed_password != plain_password
            assert verify_password(plain_password, user.hashed_password)

        # Cleanup
        async with TestSessionLocal() as session:
            u = await session.get(User, created_id)
            if u:
                await session.delete(u)
                await session.commit()


class TestUpdateUserHappyPath:
    """Smoke tests for the update user endpoint happy path."""

    @pytest.mark.asyncio
    async def test_patch_user_returns_200_and_updated_fields(
        self, client: AsyncClient, seeded_test_user: dict
    ):
        """
        PATCH /users/{id}/ with valid payload returns 200 and updated UserRead.

        Validates: Requirements 6.1, 6.3
        """
        response = await client.patch(
            f"/api/v1/settings/users/{seeded_test_user['id']}/",
            json={"full_name": "Updated Name", "role": "field_supervisor"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["full_name"] == "Updated Name"
        assert body["role"] == "field_supervisor"
        assert body["email"] == seeded_test_user["email"]
        assert "hashed_password" not in body

    @pytest.mark.asyncio
    async def test_patch_password_updates_hash(
        self, client: AsyncClient, seeded_test_user: dict
    ):
        """
        PATCH /users/{id}/ with a new password stores a new bcrypt hash.

        Validates: Requirements 6.2
        """
        new_password = "brandnewpassword456"
        response = await client.patch(
            f"/api/v1/settings/users/{seeded_test_user['id']}/",
            json={"password": new_password},
        )
        assert response.status_code == 200

        # Verify the new hash in the DB
        async with TestSessionLocal() as session:
            user = await session.get(User, seeded_test_user["id"])
            assert user is not None
            assert verify_password(new_password, user.hashed_password)
            assert not verify_password("driverpassword123", user.hashed_password)

    @pytest.mark.asyncio
    async def test_patch_only_provided_fields_change(
        self, client: AsyncClient, seeded_test_user: dict
    ):
        """
        PATCH /users/{id}/ with only full_name should not change email or role.

        Validates: Requirement 6.1
        """
        response = await client.patch(
            f"/api/v1/settings/users/{seeded_test_user['id']}/",
            json={"full_name": "Only Name Changed"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["full_name"] == "Only Name Changed"
        assert body["email"] == seeded_test_user["email"]
        assert body["role"] == seeded_test_user["role"]


class TestDeactivateUserHappyPath:
    """Smoke tests for the deactivate user endpoint happy path."""

    @pytest.mark.asyncio
    async def test_deactivate_active_user_returns_200(
        self, client: AsyncClient, seeded_test_user: dict
    ):
        """
        POST /users/{id}/deactivate/ on an active user returns 200 with is_active=false.

        Validates: Requirements 7.1, 7.2
        """
        response = await client.post(
            f"/api/v1/settings/users/{seeded_test_user['id']}/deactivate/",
        )
        assert response.status_code == 200
        body = response.json()
        assert body["is_active"] is False
        assert body["id"] == str(seeded_test_user["id"])
        assert "hashed_password" not in body

    @pytest.mark.asyncio
    async def test_deactivate_already_inactive_user_returns_200(
        self, client: AsyncClient
    ):
        """
        POST /users/{id}/deactivate/ on an already-inactive user returns 200 (idempotent).

        Validates: Requirement 7.5
        """
        # Create an already-inactive user
        inactive_id = uuid.uuid4()
        async with TestSessionLocal() as session:
            user = User(
                id=inactive_id,
                email=f"inactive-{inactive_id}@test.com",
                hashed_password=hash_password("somepassword123"),
                full_name="Inactive User",
                role="driver",
                is_active=False,  # already inactive
            )
            session.add(user)
            await session.commit()

        response = await client.post(
            f"/api/v1/settings/users/{inactive_id}/deactivate/",
        )
        assert response.status_code == 200
        assert response.json()["is_active"] is False

        # Cleanup
        async with TestSessionLocal() as session:
            u = await session.get(User, inactive_id)
            if u:
                await session.delete(u)
                await session.commit()

    @pytest.mark.asyncio
    async def test_deactivate_twice_both_return_200(
        self, client: AsyncClient, seeded_test_user: dict
    ):
        """
        Calling deactivate twice on the same user both return 200.

        Validates: Requirement 7.5
        """
        url = f"/api/v1/settings/users/{seeded_test_user['id']}/deactivate/"
        resp1 = await client.post(url)
        resp2 = await client.post(url)
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp1.json()["is_active"] is False
        assert resp2.json()["is_active"] is False
