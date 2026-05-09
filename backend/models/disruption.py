# =============================================================
# Hi-Tech Waste Management — Disruption Log Models
# Operational disruptions: landfill delays, highway restrictions,
# vehicle breakdowns, with job impact and resolution workflow.
# =============================================================

from __future__ import annotations

import uuid
from datetime import datetime, time, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from database import Base
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    func,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from models.user import User
    from models.vehicle import Vehicle

# =============================================================
# Valid value sets
# =============================================================

DISRUPTION_TYPES = {
    "landfill_delay",
    "highway_restriction",
    "vehicle_breakdown",
    "site_access_denied",
    "other",
}
DISRUPTION_STATUSES = {"open", "resolved"}
DISRUPTION_SEVERITIES = {"info", "warning", "critical"}


# =============================================================
# SQLAlchemy ORM Models
# =============================================================


class DisruptionLog(Base):
    """
    Records an unplanned operational event that impacts one or more jobs.
    Types: landfill_delay | highway_restriction | vehicle_breakdown |
           site_access_denied | other
    """

    __tablename__ = "disruption_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    disruption_type: Mapped[str] = mapped_column(
        String(30), nullable=False, index=True,
        comment="landfill_delay | highway_restriction | vehicle_breakdown | site_access_denied | other"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="open", index=True,
        comment="open | resolved"
    )
    severity: Mapped[str] = mapped_column(
        String(20), nullable=False, default="warning",
        comment="info | warning | critical"
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc), server_default=func.now(),
        index=True
    )
    reported_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Affected jobs stored as JSON array of UUID strings
    affected_job_ids: Mapped[Optional[List[str]]] = mapped_column(
        JSON, nullable=True, default=list,
        comment="UUIDs of jobs impacted by this disruption (stored as JSON array)"
    )

    # Vehicle breakdown specific fields
    vehicle_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vehicles.id", ondelete="SET NULL"), nullable=True,
        comment="Required when disruption_type = vehicle_breakdown"
    )

    # Highway restriction specific fields
    highway_name: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True,
        comment="Required when disruption_type = highway_restriction"
    )
    restriction_start_time: Mapped[Optional[time]] = mapped_column(
        Time, nullable=True
    )
    restriction_end_time: Mapped[Optional[time]] = mapped_column(
        Time, nullable=True
    )

    # Resolution fields
    resolver_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resolution_history: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        JSON, nullable=True,
        comment="Array of {text, timestamp, resolver_id} update records"
    )
    closure_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    closed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

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
    reporter: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[reported_by], lazy="selectin"
    )
    resolver: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[resolver_id], lazy="selectin"
    )
    closer: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[closed_by], lazy="selectin"
    )
    vehicle: Mapped[Optional["Vehicle"]] = relationship(
        "Vehicle", foreign_keys=[vehicle_id], lazy="selectin"
    )
    job_impacts: Mapped[List["DisruptionJobImpact"]] = relationship(
        "DisruptionJobImpact", back_populates="disruption",
        lazy="selectin", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<DisruptionLog type={self.disruption_type} status={self.status}>"


class DisruptionJobImpact(Base):
    """
    Records the quantified impact of a disruption on a specific job.
    """

    __tablename__ = "disruption_job_impacts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    disruption_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("disruption_logs.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    estimated_delay_minutes: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True,
        comment="Estimated delay caused by this disruption in minutes"
    )
    original_scheduled_completion: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revised_estimated_completion: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )

    # ── Relationships ─────────────────────────────────────────
    disruption: Mapped["DisruptionLog"] = relationship(
        "DisruptionLog", back_populates="job_impacts", lazy="selectin"
    )


# =============================================================
# Pydantic Schemas
# =============================================================


class JobImpactInput(BaseModel):
    job_id: uuid.UUID
    estimated_delay_minutes: Optional[int] = Field(None, ge=0)
    original_scheduled_completion: Optional[datetime] = None
    revised_estimated_completion: Optional[datetime] = None
    notes: Optional[str] = None


class DisruptionLogCreate(BaseModel):
    disruption_type: str = Field(
        ...,
        description="landfill_delay | highway_restriction | vehicle_breakdown | site_access_denied | other"
    )
    occurred_at: Optional[datetime] = None
    description: str
    affected_job_ids: List[uuid.UUID] = Field(
        ..., min_length=1, description="At least one affected job UUID required"
    )
    job_impacts: Optional[List[JobImpactInput]] = None

    # Vehicle breakdown fields
    vehicle_id: Optional[uuid.UUID] = None

    # Highway restriction fields
    highway_name: Optional[str] = Field(None, max_length=200)
    restriction_start_time: Optional[time] = None
    restriction_end_time: Optional[time] = None

    model_config = ConfigDict(str_strip_whitespace=True)


class DisruptionLogUpdate(BaseModel):
    """For assigning a resolver."""
    resolver_id: Optional[uuid.UUID] = None
    severity: Optional[str] = None

    model_config = ConfigDict(str_strip_whitespace=True)


class ResolutionUpdate(BaseModel):
    """Submitted by the resolver as progress updates."""
    update_text: str = Field(..., min_length=1)


class DisruptionClosure(BaseModel):
    """Submitted by operations_manager to close a disruption."""
    closure_note: str = Field(..., min_length=1)
    vehicle_status_updated: Optional[bool] = Field(
        None,
        description="Required True for vehicle_breakdown type before closure"
    )


class DisruptionJobImpactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    disruption_id: uuid.UUID
    job_id: uuid.UUID
    estimated_delay_minutes: Optional[int]
    original_scheduled_completion: Optional[datetime]
    revised_estimated_completion: Optional[datetime]
    notes: Optional[str]


class DisruptionLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    disruption_type: str
    status: str
    severity: str
    occurred_at: datetime
    reported_by: Optional[uuid.UUID]
    description: str
    affected_job_ids: Optional[List[str]]
    vehicle_id: Optional[uuid.UUID]
    highway_name: Optional[str]
    restriction_start_time: Optional[time]
    restriction_end_time: Optional[time]
    resolver_id: Optional[uuid.UUID]
    resolution_history: Optional[List[Dict[str, Any]]]
    closure_note: Optional[str]
    closed_at: Optional[datetime]
    closed_by: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime
    job_impacts: List[DisruptionJobImpactRead] = []
