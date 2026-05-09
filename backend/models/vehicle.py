# =============================================================
# Hi-Tech Waste Management — Vehicle & Trip Models
# SQLAlchemy 2.0 async ORM + Pydantic v2 schemas
# =============================================================

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from models.job import Job
    from models.user import User

from database import Base
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

# =============================================================
# SQLAlchemy ORM Models
# =============================================================


class Vehicle(Base):
    """
    Represents a fleet vehicle owned or operated by Hi-Tech Waste Management.

    vehicle_type choices:
        compactor | hook_loader | open_lorry | skip_truck | van

    status choices:
        available | on_trip | maintenance | retired
    """

    __tablename__ = "vehicles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    registration: Mapped[str] = mapped_column(
        String(30),
        unique=True,
        nullable=False,
        index=True,
        comment="Vehicle registration / plate number",
    )
    vehicle_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="compactor | hook_loader | open_lorry | skip_truck | van",
    )
    make: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    year: Mapped[Optional[int]] = mapped_column(nullable=True)
    capacity_kg: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Payload capacity in kilograms",
    )
    gps_device_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Hardware GPS tracker device identifier",
    )
    assigned_driver_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    last_service_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    next_service_date: Mapped[Optional[date]] = mapped_column(
        Date, nullable=True, index=True
    )
    odometer_km: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
        comment="Current odometer reading in kilometres",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="available",
        index=True,
        comment="available | on_trip | maintenance | retired",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    # ── Relationships ─────────────────────────────────────────
    assigned_driver: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[assigned_driver_id],
        lazy="selectin",
    )
    trips: Mapped[List["Trip"]] = relationship(
        "Trip",
        back_populates="vehicle",
        lazy="select",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Vehicle id={self.id} registration='{self.registration}' "
            f"type={self.vehicle_type} status={self.status}>"
        )


class Trip(Base):
    """
    Records a single trip made by a vehicle for a specific job.
    Captures odometer readings, fuel consumption, timing, and optional GPS track.
    """

    __tablename__ = "trips"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    job_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    vehicle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vehicles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    driver_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    start_odometer: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2), nullable=True, comment="Odometer reading at trip start (km)"
    )
    end_odometer: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2), nullable=True, comment="Odometer reading at trip end (km)"
    )
    distance_km: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Computed or GPS-derived trip distance in km",
    )
    fuel_litres: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 3), nullable=True, comment="Fuel consumed during the trip in litres"
    )
    departure_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    arrival_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    gps_track: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="GeoJSON LineString or array of {lat, lng, ts} waypoints",
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Relationships ─────────────────────────────────────────
    vehicle: Mapped["Vehicle"] = relationship(
        "Vehicle", back_populates="trips", lazy="selectin"
    )
    driver: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[driver_id], lazy="selectin"
    )
    job: Mapped[Optional["Job"]] = relationship(
        "Job", foreign_keys=[job_id], lazy="selectin"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Trip id={self.id} vehicle_id={self.vehicle_id} "
            f"job_id={self.job_id} departure={self.departure_time}>"
        )


# =============================================================
# Valid value sets
# =============================================================

VEHICLE_TYPES = {"compactor", "hook_loader", "open_lorry", "skip_truck", "van"}
VEHICLE_STATUSES = {"available", "on_trip", "maintenance", "retired"}


# =============================================================
# Pydantic Schemas — Vehicle
# =============================================================


class VehicleCreate(BaseModel):
    registration: str = Field(..., max_length=30, examples=["WXY 1234"])
    vehicle_type: str = Field(
        ..., description="compactor | hook_loader | open_lorry | skip_truck | van"
    )
    make: Optional[str] = Field(None, max_length=100)
    model: Optional[str] = Field(None, max_length=100)
    year: Optional[int] = Field(None, ge=1990, le=2100)
    capacity_kg: Optional[Decimal] = Field(None, ge=0)
    gps_device_id: Optional[str] = Field(None, max_length=100)
    assigned_driver_id: Optional[uuid.UUID] = None
    last_service_date: Optional[date] = None
    next_service_date: Optional[date] = None
    odometer_km: Optional[Decimal] = Field(None, ge=0)
    status: str = Field(default="available")

    model_config = ConfigDict(str_strip_whitespace=True)


class VehicleUpdate(BaseModel):
    registration: Optional[str] = Field(None, max_length=30)
    vehicle_type: Optional[str] = None
    make: Optional[str] = Field(None, max_length=100)
    model: Optional[str] = Field(None, max_length=100)
    year: Optional[int] = Field(None, ge=1990, le=2100)
    capacity_kg: Optional[Decimal] = Field(None, ge=0)
    gps_device_id: Optional[str] = Field(None, max_length=100)
    assigned_driver_id: Optional[uuid.UUID] = None
    last_service_date: Optional[date] = None
    next_service_date: Optional[date] = None
    odometer_km: Optional[Decimal] = Field(None, ge=0)
    status: Optional[str] = None

    model_config = ConfigDict(str_strip_whitespace=True)


class VehicleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    registration: str
    vehicle_type: str
    make: Optional[str]
    model: Optional[str]
    year: Optional[int]
    capacity_kg: Optional[Decimal]
    gps_device_id: Optional[str]
    assigned_driver_id: Optional[uuid.UUID]
    last_service_date: Optional[date]
    next_service_date: Optional[date]
    odometer_km: Optional[Decimal]
    status: str
    created_at: datetime


class VehicleListItem(BaseModel):
    """Lightweight schema for list endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    registration: str
    vehicle_type: str
    make: Optional[str]
    model: Optional[str]
    status: str
    assigned_driver_id: Optional[uuid.UUID]
    next_service_date: Optional[date]
    odometer_km: Optional[Decimal]


# =============================================================
# Pydantic Schemas — Trip
# =============================================================


class TripCreate(BaseModel):
    job_id: Optional[uuid.UUID] = None
    vehicle_id: uuid.UUID
    driver_id: Optional[uuid.UUID] = None
    start_odometer: Optional[Decimal] = Field(None, ge=0)
    end_odometer: Optional[Decimal] = Field(None, ge=0)
    distance_km: Optional[Decimal] = Field(None, ge=0)
    fuel_litres: Optional[Decimal] = Field(None, ge=0)
    departure_time: Optional[datetime] = None
    arrival_time: Optional[datetime] = None
    gps_track: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None


class TripUpdate(BaseModel):
    end_odometer: Optional[Decimal] = Field(None, ge=0)
    distance_km: Optional[Decimal] = Field(None, ge=0)
    fuel_litres: Optional[Decimal] = Field(None, ge=0)
    arrival_time: Optional[datetime] = None
    gps_track: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None


class TripRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: Optional[uuid.UUID]
    vehicle_id: uuid.UUID
    driver_id: Optional[uuid.UUID]
    start_odometer: Optional[Decimal]
    end_odometer: Optional[Decimal]
    distance_km: Optional[Decimal]
    fuel_litres: Optional[Decimal]
    departure_time: Optional[datetime]
    arrival_time: Optional[datetime]
    gps_track: Optional[Dict[str, Any]]
    notes: Optional[str]


# =============================================================
# Maintenance Log Schema (in-memory / no dedicated table yet)
# =============================================================


class MaintenanceLogCreate(BaseModel):
    """Payload for logging a maintenance event against a vehicle."""

    vehicle_id: uuid.UUID
    service_date: date
    service_type: str = Field(
        ...,
        max_length=100,
        examples=["Oil Change", "Tyre Rotation", "Annual Inspection"],
    )
    odometer_at_service_km: Optional[Decimal] = Field(None, ge=0)
    next_service_date: Optional[date] = None
    next_service_odometer_km: Optional[Decimal] = Field(None, ge=0)
    cost_myr: Optional[Decimal] = Field(None, ge=0)
    workshop: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = None
    performed_by: Optional[str] = Field(
        None, max_length=255, description="Technician or workshop name"
    )


class MaintenanceLogRead(MaintenanceLogCreate):
    id: uuid.UUID
    logged_at: datetime

    model_config = ConfigDict(from_attributes=True)
