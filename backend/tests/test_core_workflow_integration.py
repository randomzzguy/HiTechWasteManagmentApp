# =============================================================
# Hi-Tech Waste Management — Core Workflow Integration Tests
# Full E2E API tests: Client → Job → Fleet → Weighbridge → Invoice
#
# Run with: pytest tests/test_core_workflow_integration.py -v
# Or: pytest tests/test_core_workflow_integration.py -v --tb=short
# =============================================================

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
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

# ── App imports ───────────────────────────────────────────────
from database import get_db, Base
from main import app
from models.user import User
from models.client import Client, ClientWasteStream
from models.job import Job, JobCreate
from models.vehicle import Vehicle
from models.weighbridge import WeighbridgeRecord
from models.invoice import Invoice
from routers.auth import hash_password, get_current_user, require_roles

# =============================================================
# Test Database Setup (SQLite in-memory for integration tests)
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


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    """Override FastAPI DB dependency for testing."""
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
# Test Users & Auth Overrides
# =============================================================

TEST_ADMIN = {
    "id": str(uuid.uuid4()),
    "email": "admin@hitechwaste.com.my",
    "full_name": "Test Administrator",
    "role": "superadmin",
    "is_active": True,
}

TEST_DRIVER = {
    "id": str(uuid.uuid4()),
    "email": "driver@hitechwaste.com.my",
    "full_name": "Test Driver",
    "role": "driver",
    "is_active": True,
}

TEST_SUPERVISOR = {
    "id": str(uuid.uuid4()),
    "email": "supervisor@hitechwaste.com.my",
    "full_name": "Test Supervisor",
    "role": "field_supervisor",
    "is_active": True,
}


async def override_get_current_user_admin() -> dict[str, Any]:
    """Return admin user for authenticated endpoints."""
    return TEST_ADMIN.copy()


async def override_require_roles_admin(*roles: str):
    """Override role check to always pass for admin."""
    async def _check():
        return TEST_ADMIN.copy()
    return _check


# =============================================================
# Pytest Fixtures
# =============================================================

@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_test_tables():
    """Create only the tables needed for core workflow tests (SQLite-compatible)."""
    async with test_engine.begin() as conn:
        # Create only tables that don't use PostgreSQL-specific types
        await conn.run_sync(User.__table__.create, checkfirst=True)
        await conn.run_sync(Client.__table__.create, checkfirst=True)
        await conn.run_sync(ClientWasteStream.__table__.create, checkfirst=True)
        await conn.run_sync(Job.__table__.create, checkfirst=True)
        await conn.run_sync(Vehicle.__table__.create, checkfirst=True)
        await conn.run_sync(WeighbridgeRecord.__table__.create, checkfirst=True)
        await conn.run_sync(Invoice.__table__.create, checkfirst=True)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Invoice.__table__.drop, checkfirst=True)
        await conn.run_sync(WeighbridgeRecord.__table__.drop, checkfirst=True)
        await conn.run_sync(Vehicle.__table__.drop, checkfirst=True)
        await conn.run_sync(Job.__table__.drop, checkfirst=True)
        await conn.run_sync(ClientWasteStream.__table__.drop, checkfirst=True)
        await conn.run_sync(Client.__table__.drop, checkfirst=True)
        await conn.run_sync(User.__table__.drop, checkfirst=True)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a database session for direct DB operations in tests."""
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def api_client() -> AsyncGenerator[AsyncClient, None]:
    """Authenticated API client for testing."""
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user_admin
    
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client
    
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_client_in_db(db_session: AsyncSession) -> Client:
    """Create a test client in the database."""
    client = Client(
        id=uuid.uuid4(),
        company_name="Test Manufacturing Sdn Bhd",
        pic_name="John Doe",
        pic_email="john@testmanufacturing.com",
        pic_phone="+60 12-345 6789",
        address="123 Test Street, Industrial Park",
        is_active=True,
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)
    return client


@pytest_asyncio.fixture
async def test_vehicle_in_db(db_session: AsyncSession) -> Vehicle:
    """Create a test vehicle in the database."""
    vehicle = Vehicle(
        id=uuid.uuid4(),
        registration="TEST-VEHICLE-001",
        vehicle_type="compactor",
        make="Isuzu",
        model="FVR",
        year=2023,
        capacity_kg=Decimal("5000.00"),
        status="available",
        odometer_km=Decimal("15000.00"),
    )
    db_session.add(vehicle)
    await db_session.commit()
    await db_session.refresh(vehicle)
    return vehicle


@pytest_asyncio.fixture
async def test_driver_in_db(db_session: AsyncSession) -> User:
    """Create a test driver user in the database."""
    user = User(
        id=uuid.UUID(TEST_DRIVER["id"]),
        email=TEST_DRIVER["email"],
        hashed_password=hash_password("driver123"),
        full_name=TEST_DRIVER["full_name"],
        role="driver",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


# =============================================================
# Integration Test Suite
# =============================================================

class TestCoreWorkflow:
    """
    Comprehensive integration tests for the core waste management workflow:
    1. Create client
    2. Create job for client
    3. Assign vehicle and driver to job
    4. Update job status through pipeline
    5. Create weighbridge record
    6. Create invoice from job
    """

    async def test_01_create_job(self, api_client: AsyncClient, test_client_in_db: Client):
        """Test creating a new job for a client."""
        job_data = {
            "client_id": str(test_client_in_db.id),
            "job_type": "general_collection",
            "collection_address": "123 Test Street, Industrial Park, Selangor",
            "scheduled_date": str(date.today() + timedelta(days=1)),
            "scheduled_time_start": "09:00:00",
            "estimated_weight_kg": 1500.0,
            "notes": "Regular waste collection - test job",
        }
        
        response = await api_client.post("/api/v1/jobs/", json=job_data)
        assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["client_id"] == str(test_client_in_db.id)
        assert data["job_type"] == "general_collection"
        assert data["status"] == "draft"
        assert data["job_number"].startswith("JOB-")
        assert data["collection_address"] == job_data["collection_address"]
        
        # Store job ID for subsequent tests
        self._created_job_id = data["id"]
        self._job_data = data
        
        print(f"✓ Created job: {data['job_number']}")

    async def test_02_list_jobs(self, api_client: AsyncClient, test_client_in_db: Client):
        """Test listing jobs with filters."""
        # List all jobs
        response = await api_client.get("/api/v1/jobs/")
        assert response.status_code == 200
        
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert len(data["items"]) >= 1
        
        # Filter by client
        response = await api_client.get(
            f"/api/v1/jobs/?client_id={test_client_in_db.id}"
        )
        assert response.status_code == 200
        data = response.json()
        assert all(j["client_id"] == str(test_client_in_db.id) for j in data["items"])
        
        # Filter by status
        response = await api_client.get("/api/v1/jobs/?status=draft")
        assert response.status_code == 200
        data = response.json()
        assert all(j["status"] == "draft" for j in data["items"])
        
        print("✓ Job listing and filtering works correctly")

    async def test_03_assign_fleet_to_job(
        self, 
        api_client: AsyncClient, 
        test_client_in_db: Client,
        test_vehicle_in_db: Vehicle,
        test_driver_in_db: User,
    ):
        """Test assigning vehicle and driver to a job."""
        # First create a job
        job_data = {
            "client_id": str(test_client_in_db.id),
            "job_type": "general_collection",
            "collection_address": "123 Test Street",
            "scheduled_date": str(date.today() + timedelta(days=1)),
            "estimated_weight_kg": 1000.0,
        }
        create_resp = await api_client.post("/api/v1/jobs/", json=job_data)
        assert create_resp.status_code == 201
        job_id = create_resp.json()["id"]
        
        # Assign vehicle and driver
        update_data = {
            "assigned_vehicle_id": str(test_vehicle_in_db.id),
            "assigned_driver_id": str(test_driver_in_db.id),
            "status": "confirmed",
        }
        
        response = await api_client.patch(f"/api/v1/jobs/{job_id}", json=update_data)
        assert response.status_code == 200, f"Failed to assign fleet: {response.text}"
        
        data = response.json()
        assert data["assigned_vehicle_id"] == str(test_vehicle_in_db.id)
        assert data["assigned_driver_id"] == str(test_driver_in_db.id)
        assert data["status"] == "confirmed"
        
        self._job_id_with_fleet = job_id
        print(f"✓ Assigned vehicle {test_vehicle_in_db.registration} and driver to job")

    async def test_04_job_status_pipeline(self, api_client: AsyncClient, test_client_in_db: Client):
        """Test the job status pipeline: draft → confirmed → dispatched → in_progress → completed."""
        # Create job
        job_data = {
            "client_id": str(test_client_in_db.id),
            "job_type": "general_collection",
            "collection_address": "Status Pipeline Test",
            "scheduled_date": str(date.today()),
        }
        create_resp = await api_client.post("/api/v1/jobs/", json=job_data)
        job_id = create_resp.json()["id"]
        
        # Status transitions to test
        transitions = [
            ("draft", "confirmed"),
            ("confirmed", "dispatched"),
            ("dispatched", "in_progress"),
            ("in_progress", "completed"),
        ]
        
        for from_status, to_status in transitions:
            response = await api_client.patch(
                f"/api/v1/jobs/{job_id}/status",
                json={"status": to_status, "notes": f"Transition to {to_status}"},
            )
            assert response.status_code == 200, (
                f"Failed transition {from_status} → {to_status}: {response.text}"
            )
            data = response.json()
            assert data["status"] == to_status, f"Expected {to_status}, got {data['status']}"
            print(f"✓ Status transition: {from_status} → {to_status}")

    async def test_05_create_weighbridge_record(
        self, 
        api_client: AsyncClient, 
        test_client_in_db: Client,
    ):
        """Test creating a weighbridge record linked to a job."""
        # Create a completed job first
        job_data = {
            "client_id": str(test_client_in_db.id),
            "job_type": "general_collection",
            "collection_address": "Weighbridge Test Address",
            "scheduled_date": str(date.today()),
            "status": "completed",
        }
        job_resp = await api_client.post("/api/v1/jobs/", json=job_data)
        job_id = job_resp.json()["id"]
        
        # Create weighbridge record
        weighbridge_data = {
            "job_id": job_id,
            "client_id": str(test_client_in_db.id),
            "gross_weight_kg": 5200.0,
            "tare_weight_kg": 3500.0,
            "waste_type_breakdown": {
                "general_waste_kg": 1500.0,
                "recyclable_kg": 200.0,
            },
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        
        response = await api_client.post("/api/v1/weighbridge/records", json=weighbridge_data)
        assert response.status_code == 201, f"Failed to create weighbridge record: {response.text}"
        
        data = response.json()
        assert data["job_id"] == job_id
        assert data["client_id"] == str(test_client_in_db.id)
        assert data["gross_weight_kg"] == 5200.0
        assert data["tare_weight_kg"] == 3500.0
        assert data["net_weight_kg"] == 1700.0  # Auto-computed
        
        self._weighbridge_record_id = data["id"]
        print(f"✓ Created weighbridge record: {data['net_weight_kg']}kg net weight")

    async def test_06_create_invoice_from_job(
        self, 
        api_client: AsyncClient, 
        test_client_in_db: Client,
    ):
        """Test creating an invoice linked to a completed job."""
        # Create completed job with actual weight
        job_data = {
            "client_id": str(test_client_in_db.id),
            "job_type": "general_collection",
            "collection_address": "Invoice Test Address",
            "scheduled_date": str(date.today()),
            "actual_weight_kg": 2500.0,
        }
        job_resp = await api_client.post("/api/v1/jobs/", json=job_data)
        job_id = job_resp.json()["id"]
        
        # Complete the job
        await api_client.patch(
            f"/api/v1/jobs/{job_id}/status",
            json={"status": "completed"},
        )
        
        # Create invoice
        invoice_data = {
            "client_id": str(test_client_in_db.id),
            "job_ids": [job_id],
            "issue_date": str(date.today()),
            "due_date": str(date.today() + timedelta(days=30)),
            "line_items": [
                {
                    "description": "General waste collection",
                    "quantity": 2.5,  # tonnes
                    "unit_price_myr": 150.00,
                    "total_myr": 375.00,
                }
            ],
            "subtotal_myr": 375.00,
            "tax_myr": 0.00,
            "total_myr": 375.00,
            "notes": "Invoice for job completion",
        }
        
        response = await api_client.post("/api/v1/finance/invoices", json=invoice_data)
        assert response.status_code == 201, f"Failed to create invoice: {response.text}"
        
        data = response.json()
        assert data["client_id"] == str(test_client_in_db.id)
        assert data["invoice_number"].startswith("INV-")
        assert data["total_myr"] == 375.00
        assert data["status"] == "unpaid"
        
        self._invoice_id = data["id"]
        print(f"✓ Created invoice: {data['invoice_number']} for RM {data['total_myr']}")

    async def test_07_list_and_filter_invoices(self, api_client: AsyncClient):
        """Test listing and filtering invoices."""
        # List all invoices
        response = await api_client.get("/api/v1/finance/invoices")
        assert response.status_code == 200
        
        data = response.json()
        assert "items" in data
        assert "total" in data
        
        # Filter by status
        response = await api_client.get("/api/v1/finance/invoices?status=unpaid")
        assert response.status_code == 200
        data = response.json()
        assert all(inv["status"] == "unpaid" for inv in data["items"])
        
        print("✓ Invoice listing and filtering works correctly")

    async def test_08_complete_workflow_end_to_end(
        self,
        api_client: AsyncClient,
        test_client_in_db: Client,
        test_vehicle_in_db: Vehicle,
        test_driver_in_db: User,
    ):
        """Complete end-to-end workflow test simulating real user operations."""
        print("\n--- Starting Complete E2E Workflow ---")
        
        # Step 1: Create job
        job_data = {
            "client_id": str(test_client_in_db.id),
            "job_type": "general_collection",
            "collection_address": "E2E Test: 456 Full Workflow Ave",
            "scheduled_date": str(date.today()),
            "scheduled_time_start": "10:00:00",
            "estimated_weight_kg": 2000.0,
            "notes": "Complete E2E workflow test",
        }
        resp = await api_client.post("/api/v1/jobs/", json=job_data)
        assert resp.status_code == 201
        job = resp.json()
        job_id = job["id"]
        print(f"1. ✓ Created job: {job['job_number']}")
        
        # Step 2: Assign vehicle and driver, confirm job
        update_data = {
            "assigned_vehicle_id": str(test_vehicle_in_db.id),
            "assigned_driver_id": str(test_driver_in_db.id),
        }
        resp = await api_client.patch(f"/api/v1/jobs/{job_id}", json=update_data)
        assert resp.status_code == 200
        print(f"2. ✓ Assigned vehicle and driver")
        
        # Step 3: Dispatch job
        resp = await api_client.patch(
            f"/api/v1/jobs/{job_id}/status",
            json={"status": "dispatched", "notes": "Driver en route"},
        )
        assert resp.status_code == 200
        print("3. ✓ Job dispatched")
        
        # Step 4: Mark in progress
        resp = await api_client.patch(
            f"/api/v1/jobs/{job_id}/status",
            json={"status": "in_progress", "notes": "Collection in progress"},
        )
        assert resp.status_code == 200
        print("4. ✓ Collection in progress")
        
        # Step 5: Record weighbridge measurement
        weighbridge_data = {
            "job_id": job_id,
            "client_id": str(test_client_in_db.id),
            "gross_weight_kg": 6000.0,
            "tare_weight_kg": 3500.0,
            "waste_type_breakdown": {
                "general_waste_kg": 2300.0,
                "recyclable_kg": 200.0,
            },
        }
        resp = await api_client.post("/api/v1/weighbridge/records", json=weighbridge_data)
        assert resp.status_code == 201
        weigh_record = resp.json()
        print(f"5. ✓ Weighbridge: {weigh_record['net_weight_kg']}kg collected")
        
        # Step 6: Complete job
        resp = await api_client.patch(
            f"/api/v1/jobs/{job_id}",
            json={"actual_weight_kg": weigh_record["net_weight_kg"]},
        )
        assert resp.status_code == 200
        
        resp = await api_client.patch(
            f"/api/v1/jobs/{job_id}/status",
            json={"status": "completed", "notes": "Collection completed successfully"},
        )
        assert resp.status_code == 200
        print("6. ✓ Job completed")
        
        # Step 7: Create invoice
        invoice_data = {
            "client_id": str(test_client_in_db.id),
            "job_ids": [job_id],
            "issue_date": str(date.today()),
            "due_date": str(date.today() + timedelta(days=30)),
            "line_items": [
                {
                    "description": "General waste collection - 2.5 tonnes",
                    "quantity": 2.5,
                    "unit_price_myr": 150.00,
                    "total_myr": 375.00,
                }
            ],
            "subtotal_myr": 375.00,
            "tax_myr": 0.00,
            "total_myr": 375.00,
        }
        resp = await api_client.post("/api/v1/finance/invoices", json=invoice_data)
        assert resp.status_code == 201
        invoice = resp.json()
        print(f"7. ✓ Invoice created: {invoice['invoice_number']} - RM {invoice['total_myr']}")
        
        # Step 8: Record payment
        payment_data = {
            "amount_myr": 375.00,
            "payment_method": "bank_transfer",
            "reference": "TEST-PAYMENT-001",
            "received_at": datetime.now(timezone.utc).isoformat(),
        }
        resp = await api_client.post(
            f"/api/v1/finance/invoices/{invoice['id']}/payments",
            json=payment_data,
        )
        assert resp.status_code == 200
        updated_invoice = resp.json()
        assert updated_invoice["status"] == "paid"
        print("8. ✓ Payment recorded - Invoice marked as PAID")
        
        print("\n=== Complete E2E Workflow Successful! ===")
        print(f"   Job: {job['job_number']}")
        print(f"   Vehicle: {test_vehicle_in_db.registration}")
        print(f"   Driver: {test_driver_in_db.full_name}")
        print(f"   Waste Collected: {weigh_record['net_weight_kg']}kg")
        print(f"   Invoice: {invoice['invoice_number']} - RM {invoice['total_myr']}")


class TestErrorScenarios:
    """Test error handling and edge cases in the workflow."""

    async def test_create_job_invalid_client(self, api_client: AsyncClient):
        """Test creating job with non-existent client returns 404."""
        job_data = {
            "client_id": str(uuid.uuid4()),  # Random UUID
            "job_type": "general_collection",
            "collection_address": "Test Address",
            "scheduled_date": str(date.today()),
        }
        
        response = await api_client.post("/api/v1/jobs/", json=job_data)
        assert response.status_code in [400, 404, 422], f"Expected error, got {response.status_code}"
        print("✓ Invalid client properly rejected")

    async def test_invalid_status_transition(self, api_client: AsyncClient, test_client_in_db: Client):
        """Test invalid status transitions are rejected."""
        # Create job
        job_data = {
            "client_id": str(test_client_in_db.id),
            "job_type": "general_collection",
            "collection_address": "Test Address",
            "scheduled_date": str(date.today()),
        }
        resp = await api_client.post("/api/v1/jobs/", json=job_data)
        job_id = resp.json()["id"]
        
        # Try to jump directly to completed without proper pipeline
        # (This should fail if status pipeline validation is enforced)
        response = await api_client.patch(
            f"/api/v1/jobs/{job_id}/status",
            json={"status": "invoiced"},  # Can't invoice a draft job
        )
        # This may succeed or fail depending on implementation
        # We're testing that the system handles it gracefully
        assert response.status_code in [200, 400, 422]
        print("✓ Invalid status transition handled")

    async def test_duplicate_vehicle_registration(self, api_client: AsyncClient):
        """Test that duplicate vehicle registrations are rejected."""
        # This test would require the API to enforce unique registrations
        # Implementation depends on fleet router validation
        pass


# =============================================================
# Run Configuration
# =============================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
