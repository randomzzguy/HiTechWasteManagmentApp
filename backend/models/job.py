# =============================================================
# Hi-Tech Waste Management — Job Model
# SQLAlchemy async ORM model + Pydantic schemas
# =============================================================

from __future__ import annotations

import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from database import Base
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    Time,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from models.client import Client
    from models.user import User
    from models.vehicle import Vehicle

# =============================================================
# SQLAlchemy ORM Model
# =============================================================


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_number: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    job_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        # one of: general_collection | scheduled_waste | witnessed_destruction
        #         | food_waste_bsf | equipment_rental | consultancy
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="draft",
        index=True,
        # one of: draft | confirmed | dispatched | in_progress | completed | invoiced
    )
    scheduled_date: Mapped[Optional[date]] = mapped_column(nullable=True)
    scheduled_time_start: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    collection_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    assigned_vehicle_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vehicles.id", ondelete="SET NULL"),
        nullable=True,
    )
    assigned_driver_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    assigned_supervisor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    estimated_weight_kg: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 3), nullable=True
    )
    actual_weight_kg: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 3), nullable=True
    )
    disposal_route: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # ── Relationships ─────────────────────────────────────────
    client: Mapped["Client"] = relationship(
        "Client", back_populates="jobs", lazy="selectin"
    )
    assigned_vehicle: Mapped[Optional["Vehicle"]] = relationship(
        "Vehicle", foreign_keys=[assigned_vehicle_id], lazy="selectin"
    )
    assigned_driver: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[assigned_driver_id], lazy="selectin"
    )
    assigned_supervisor: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[assigned_supervisor_id], lazy="selectin"
    )
    creator: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[created_by], lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Job {self.job_number} status={self.status}>"


class RecurringJobTemplate(Base):
    """
    Stores recurring job templates for automated job generation.
    
    Templates define job parameters that can be used to automatically
    generate job instances based on recurrence rules (iCal RRULE format).
    """
    
    __tablename__ = "recurring_job_templates"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(
        String(255), nullable=False,
        comment="Human-readable template name"
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="One of: general_collection | scheduled_waste | witnessed_destruction | food_waste_bsf | equipment_rental | consultancy"
    )
    collection_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    assigned_vehicle_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vehicles.id", ondelete="SET NULL"),
        nullable=True,
    )
    assigned_driver_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    assigned_supervisor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    estimated_weight_kg: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 3), nullable=True
    )
    disposal_route: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    recurrence_rule: Mapped[str] = mapped_column(
        String(255), nullable=False,
        comment="iCal RRULE string, e.g. FREQ=WEEKLY;BYDAY=MO,WE,FR"
    )
    is_active: Mapped[bool] = mapped_column(
        default=True, nullable=False, server_default="true"
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    
    # ── Relationships ─────────────────────────────────────────
    client: Mapped["Client"] = relationship(
        "Client", lazy="selectin"
    )
    assigned_vehicle: Mapped[Optional["Vehicle"]] = relationship(
        "Vehicle", foreign_keys=[assigned_vehicle_id], lazy="selectin"
    )
    assigned_driver: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[assigned_driver_id], lazy="selectin"
    )
    assigned_supervisor: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[assigned_supervisor_id], lazy="selectin"
    )
    
    def __repr__(self) -> str:
        return f"<RecurringJobTemplate {self.name} client={self.client_id}>"


# =============================================================
# Valid value sets
# =============================================================

JOB_TYPES = {
    "general_collection",
    "scheduled_waste",
    "witnessed_destruction",
    "food_waste_bsf",
    "equipment_rental",
    "consultancy",
}

JOB_STATUSES = {
    "draft",
    "confirmed",
    "dispatched",
    "in_progress",
    "completed",
    "invoiced",
}

# Ordered pipeline — status can only advance forward
STATUS_PIPELINE = [
    "draft",
    "confirmed",
    "dispatched",
    "in_progress",
    "completed",
    "invoiced",
]


# =============================================================
# Pydantic Schemas
# =============================================================


class JobCreate(BaseModel):
    client_id: uuid.UUID
    job_type: str = Field(..., description="One of: " + ", ".join(sorted(JOB_TYPES)))
    scheduled_date: Optional[date] = None
    scheduled_time_start: Optional[time] = None
    collection_address: Optional[str] = None
    assigned_vehicle_id: Optional[uuid.UUID] = None
    assigned_driver_id: Optional[uuid.UUID] = None
    assigned_supervisor_id: Optional[uuid.UUID] = None
    estimated_weight_kg: Optional[Decimal] = Field(None, ge=0)
    disposal_route: Optional[str] = None
    notes: Optional[str] = None


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_number: str
    client_id: uuid.UUID
    job_type: str
    status: str
    scheduled_date: Optional[date]
    scheduled_time_start: Optional[time]
    collection_address: Optional[str]
    assigned_vehicle_id: Optional[uuid.UUID]
    assigned_driver_id: Optional[uuid.UUID]
    assigned_supervisor_id: Optional[uuid.UUID]
    estimated_weight_kg: Optional[Decimal]
    actual_weight_kg: Optional[Decimal]
    disposal_route: Optional[str]
    notes: Optional[str]
    completed_at: Optional[datetime]
    created_by: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime


class JobUpdate(BaseModel):
    job_type: Optional[str] = None
    scheduled_date: Optional[date] = None
    scheduled_time_start: Optional[time] = None
    collection_address: Optional[str] = None
    assigned_vehicle_id: Optional[uuid.UUID] = None
    assigned_driver_id: Optional[uuid.UUID] = None
    assigned_supervisor_id: Optional[uuid.UUID] = None
    estimated_weight_kg: Optional[Decimal] = Field(None, ge=0)
    actual_weight_kg: Optional[Decimal] = Field(None, ge=0)
    disposal_route: Optional[str] = None
    notes: Optional[str] = None


class JobStatusUpdate(BaseModel):
    status: str = Field(..., description="New status — must be next step in pipeline")
    notes: Optional[str] = Field(
        None, description="Optional note about the status change"
    )


# =============================================================
# Recurring Job Template Schemas
# =============================================================


class RecurringJobTemplateCreate(BaseModel):
    """Schema for creating a recurring job template."""
    
    name: str = Field(..., max_length=255, description="Human-readable template name")
    client_id: uuid.UUID
    job_type: str = Field(..., description="Job type for this template")
    collection_address: Optional[str] = None
    assigned_vehicle_id: Optional[uuid.UUID] = None
    assigned_driver_id: Optional[uuid.UUID] = None
    assigned_supervisor_id: Optional[uuid.UUID] = None
    estimated_weight_kg: Optional[Decimal] = Field(None, ge=0)
    disposal_route: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None
    recurrence_rule: str = Field(
        ...,
        max_length=255,
        description="iCal RRULE string, e.g. FREQ=WEEKLY;BYDAY=MO,WE,FR",
    )
    is_active: bool = True
    
    model_config = ConfigDict(str_strip_whitespace=True)


class RecurringJobTemplateUpdate(BaseModel):
    """Schema for updating a recurring job template."""
    
    name: Optional[str] = Field(None, max_length=255)
    job_type: Optional[str] = None
    collection_address: Optional[str] = None
    assigned_vehicle_id: Optional[uuid.UUID] = None
    assigned_driver_id: Optional[uuid.UUID] = None
    assigned_supervisor_id: Optional[uuid.UUID] = None
    estimated_weight_kg: Optional[Decimal] = Field(None, ge=0)
    disposal_route: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None
    recurrence_rule: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = None
    
    model_config = ConfigDict(str_strip_whitespace=True)


class RecurringJobTemplateRead(BaseModel):
    """Schema for reading a recurring job template."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: uuid.UUID
    name: str
    client_id: uuid.UUID
    job_type: str
    collection_address: Optional[str]
    assigned_vehicle_id: Optional[uuid.UUID]
    assigned_driver_id: Optional[uuid.UUID]
    assigned_supervisor_id: Optional[uuid.UUID]
    estimated_weight_kg: Optional[Decimal]
    disposal_route: Optional[str]
    notes: Optional[str]
    recurrence_rule: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
