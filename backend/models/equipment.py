# =============================================================
# Hi-Tech Waste Management — Equipment & Container Models
# Compaction machines, deployments, maintenance, containers,
# fill-level readings, and pickup triggers.
# =============================================================

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from database import Base
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from models.client import Client
    from models.user import User

# =============================================================
# Valid value sets
# =============================================================

COMPACTOR_STATUSES = {"available", "deployed", "maintenance", "decommissioned"}
CONTAINER_STATUSES = {"available", "at_site", "in_transit", "at_recycler", "decommissioned"}
CONTAINER_TYPES = {"skip_bin", "roll_on_roll_off", "compaction_chamber"}


# =============================================================
# SQLAlchemy ORM Models
# =============================================================


class CompactionMachine(Base):
    """
    Hydraulic compaction unit owned by Hi-Tech and deployed at client sites.

    status choices: available | deployed | maintenance | decommissioned
    """

    __tablename__ = "compaction_machines"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    asset_tag: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True,
        comment="Internal asset tag e.g. CM-001"
    )
    model_name: Mapped[str] = mapped_column(String(150), nullable=False)
    serial_number: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="available", index=True,
        comment="available | deployed | maintenance | decommissioned"
    )
    purchase_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    compaction_force_kn: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 2), nullable=True, comment="Rated compaction force in kilonewtons"
    )
    maintenance_interval_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=90,
        comment="Days between scheduled services"
    )
    last_service_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    next_service_date: Mapped[Optional[date]] = mapped_column(
        Date, nullable=True, index=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc), server_default=func.now()
    )

    # ── Relationships ─────────────────────────────────────────
    deployments: Mapped[List["CompactorDeployment"]] = relationship(
        "CompactorDeployment", back_populates="machine",
        lazy="select", cascade="all, delete-orphan"
    )
    maintenance_logs: Mapped[List["CompactorMaintenanceLog"]] = relationship(
        "CompactorMaintenanceLog", back_populates="machine",
        lazy="select", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<CompactionMachine {self.asset_tag} status={self.status}>"


class CompactorDeployment(Base):
    """
    Records a single deployment of a compaction machine at a client site.
    """

    __tablename__ = "compactor_deployments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    machine_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("compaction_machines.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="RESTRICT"),
        nullable=False, index=True
    )
    site_address: Mapped[str] = mapped_column(Text, nullable=False)
    deployment_start: Mapped[date] = mapped_column(Date, nullable=False)
    deployment_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    authorised_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )

    # ── Relationships ─────────────────────────────────────────
    machine: Mapped["CompactionMachine"] = relationship(
        "CompactionMachine", back_populates="deployments", lazy="selectin"
    )
    client: Mapped["Client"] = relationship("Client", lazy="selectin")
    authoriser: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[authorised_by], lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<CompactorDeployment machine={self.machine_id} client={self.client_id}>"


class CompactorMaintenanceLog(Base):
    """
    Records a single maintenance service event for a compaction machine.
    """

    __tablename__ = "compactor_maintenance_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    machine_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("compaction_machines.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    service_date: Mapped[date] = mapped_column(Date, nullable=False)
    service_type: Mapped[str] = mapped_column(String(100), nullable=False)
    technician_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    cost_myr: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    logged_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )

    # ── Relationships ─────────────────────────────────────────
    machine: Mapped["CompactionMachine"] = relationship(
        "CompactionMachine", back_populates="maintenance_logs", lazy="selectin"
    )
    logger: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[logged_by], lazy="selectin"
    )


class Container(Base):
    """
    Physical receptacle (skip bin, roll-on/roll-off, compaction chamber)
    that holds densified waste at a client site until transport to recycler.

    status choices: available | at_site | in_transit | at_recycler | decommissioned
    container_type: skip_bin | roll_on_roll_off | compaction_chamber
    """

    __tablename__ = "containers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    container_code: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True,
        comment="Internal code e.g. CNT-001"
    )
    container_type: Mapped[str] = mapped_column(
        String(30), nullable=False,
        comment="skip_bin | roll_on_roll_off | compaction_chamber"
    )
    capacity_m3: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 2), nullable=True, comment="Capacity in cubic metres"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="available", index=True,
        comment="available | at_site | in_transit | at_recycler | decommissioned"
    )
    current_client_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="SET NULL"), nullable=True, index=True
    )
    current_site_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    current_compactor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("compaction_machines.id", ondelete="SET NULL"), nullable=True
    )
    target_material_type: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True,
        comment="e.g. cardboard, plastics, metals, food_waste, general"
    )
    fill_level: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="Current fill level percentage 0-100"
    )
    pickup_threshold: Mapped[int] = mapped_column(
        Integer, nullable=False, default=85,
        comment="Fill level % that triggers a pickup notification"
    )
    assigned_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc), server_default=func.now()
    )

    # ── Relationships ─────────────────────────────────────────
    current_client: Mapped[Optional["Client"]] = relationship(
        "Client", foreign_keys=[current_client_id], lazy="selectin"
    )
    fill_readings: Mapped[List["ContainerFillReading"]] = relationship(
        "ContainerFillReading", back_populates="container",
        lazy="select", cascade="all, delete-orphan",
        order_by="ContainerFillReading.recorded_at.desc()"
    )
    pickup_triggers: Mapped[List["PickupTrigger"]] = relationship(
        "PickupTrigger", back_populates="container",
        lazy="select", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Container {self.container_code} status={self.status} fill={self.fill_level}%>"


class ContainerFillReading(Base):
    """
    Records a single fill-level reading for a container at a point in time.
    """

    __tablename__ = "container_fill_readings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    container_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("containers.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    fill_level: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Fill level percentage 0-100"
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc), server_default=func.now(),
        index=True
    )
    reported_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    photo_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Relationships ─────────────────────────────────────────
    container: Mapped["Container"] = relationship(
        "Container", back_populates="fill_readings", lazy="selectin"
    )
    reporter: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[reported_by], lazy="selectin"
    )


class PickupTrigger(Base):
    """
    Created automatically when a container's fill level reaches the threshold.
    Drives the pickup workflow.
    """

    __tablename__ = "pickup_triggers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    container_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("containers.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )
    fill_level_at_trigger: Mapped[int] = mapped_column(Integer, nullable=False)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    acknowledged_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    linked_job_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, index=True
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Relationships ─────────────────────────────────────────
    container: Mapped["Container"] = relationship(
        "Container", back_populates="pickup_triggers", lazy="selectin"
    )
    acknowledger: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[acknowledged_by], lazy="selectin"
    )


class ContainerTransportLog(Base):
    """
    Records each status transition for a container during transport.
    """

    __tablename__ = "container_transport_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    container_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("containers.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    from_status: Mapped[str] = mapped_column(String(20), nullable=False)
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    transitioned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )
    responsible_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    vehicle_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vehicles.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Relationships ─────────────────────────────────────────
    responsible_user: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[responsible_user_id], lazy="selectin"
    )


# =============================================================
# Pydantic Schemas — CompactionMachine
# =============================================================


class CompactionMachineCreate(BaseModel):
    asset_tag: str = Field(..., max_length=50, examples=["CM-001"])
    model_name: str = Field(..., max_length=150)
    serial_number: str = Field(..., max_length=100)
    purchase_date: Optional[date] = None
    compaction_force_kn: Optional[Decimal] = Field(None, ge=0)
    maintenance_interval_days: int = Field(default=90, ge=1)
    notes: Optional[str] = None

    model_config = ConfigDict(str_strip_whitespace=True)


class CompactionMachineUpdate(BaseModel):
    model_name: Optional[str] = Field(None, max_length=150)
    status: Optional[str] = None
    compaction_force_kn: Optional[Decimal] = Field(None, ge=0)
    maintenance_interval_days: Optional[int] = Field(None, ge=1)
    last_service_date: Optional[date] = None
    next_service_date: Optional[date] = None
    notes: Optional[str] = None

    model_config = ConfigDict(str_strip_whitespace=True)


class CompactionMachineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    asset_tag: str
    model_name: str
    serial_number: str
    status: str
    purchase_date: Optional[date]
    compaction_force_kn: Optional[Decimal]
    maintenance_interval_days: int
    last_service_date: Optional[date]
    next_service_date: Optional[date]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime


class CompactorDeploymentCreate(BaseModel):
    client_id: uuid.UUID
    site_address: str
    deployment_start: date
    notes: Optional[str] = None


class CompactorDeploymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    machine_id: uuid.UUID
    client_id: uuid.UUID
    site_address: str
    deployment_start: date
    deployment_end: Optional[date]
    authorised_by: Optional[uuid.UUID]
    notes: Optional[str]
    created_at: datetime


class CompactorMaintenanceLogCreate(BaseModel):
    service_date: date
    service_type: str = Field(..., max_length=100)
    technician_name: Optional[str] = Field(None, max_length=200)
    cost_myr: Optional[Decimal] = Field(None, ge=0)
    notes: Optional[str] = None


class CompactorMaintenanceLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    machine_id: uuid.UUID
    service_date: date
    service_type: str
    technician_name: Optional[str]
    cost_myr: Optional[Decimal]
    logged_by: Optional[uuid.UUID]
    notes: Optional[str]
    created_at: datetime


# =============================================================
# Pydantic Schemas — Container
# =============================================================


class ContainerCreate(BaseModel):
    container_code: str = Field(..., max_length=50, examples=["CNT-001"])
    container_type: str = Field(
        ..., description="skip_bin | roll_on_roll_off | compaction_chamber"
    )
    capacity_m3: Optional[Decimal] = Field(None, ge=0)
    pickup_threshold: int = Field(default=85, ge=1, le=100)
    notes: Optional[str] = None

    model_config = ConfigDict(str_strip_whitespace=True)


class ContainerAssignSite(BaseModel):
    client_id: uuid.UUID
    site_address: str
    compactor_id: Optional[uuid.UUID] = None
    target_material_type: Optional[str] = Field(None, max_length=50)
    assigned_date: Optional[date] = None


class ContainerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    container_code: str
    container_type: str
    capacity_m3: Optional[Decimal]
    status: str
    current_client_id: Optional[uuid.UUID]
    current_site_address: Optional[str]
    current_compactor_id: Optional[uuid.UUID]
    target_material_type: Optional[str]
    fill_level: int
    pickup_threshold: int
    assigned_date: Optional[date]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime


class FillLevelUpdate(BaseModel):
    fill_level: int = Field(..., ge=0, le=100, description="Fill level percentage 0-100")
    photo_url: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("fill_level")
    @classmethod
    def validate_fill_level(cls, v: int) -> int:
        if not 0 <= v <= 100:
            raise ValueError("fill_level must be between 0 and 100")
        return v


class FillReadingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    container_id: uuid.UUID
    fill_level: int
    recorded_at: datetime
    reported_by: Optional[uuid.UUID]
    photo_url: Optional[str]
    notes: Optional[str]


class PickupTriggerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    container_id: uuid.UUID
    triggered_at: datetime
    fill_level_at_trigger: int
    acknowledged_at: Optional[datetime]
    acknowledged_by: Optional[uuid.UUID]
    linked_job_id: Optional[uuid.UUID]
    is_active: bool
    closed_at: Optional[datetime]


class ContainerTransportUpdate(BaseModel):
    """Used by driver to update container status during transport."""
    to_status: str = Field(
        ..., description="in_transit | at_recycler | available"
    )
    vehicle_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None
