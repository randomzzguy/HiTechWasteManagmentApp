# =============================================================
# Hi-Tech Waste Management — Labour Deployment Models
# Staff profiles, site assignments, shifts, and attendance.
# =============================================================

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from database import Base
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    String,
    Text,
    Time,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from models.client import Client
    from models.user import User

# =============================================================
# Valid value sets
# =============================================================

EMPLOYMENT_TYPES = {"permanent", "contract", "foreign_worker"}
STAFF_STATUSES = {"available", "on_site", "on_leave", "inactive"}
SHIFT_TYPES = {"morning", "afternoon", "night"}
ABSENCE_REASONS = {"sick_leave", "annual_leave", "no_show", "emergency"}
ATTENDANCE_STATUSES = {"present", "absent", "no_checkout", "late"}


# =============================================================
# SQLAlchemy ORM Models
# =============================================================


class StaffProfile(Base):
    """
    Extended profile for field staff, linked to the users table.
    Captures employment type, labour agent details, and work permit info
    for foreign workers.
    """

    __tablename__ = "staff_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True
    )
    employment_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="permanent",
        comment="permanent | contract | foreign_worker"
    )
    labour_agent_name: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True,
        comment="Name of labour supply agency (for foreign workers)"
    )
    # IC/passport stored encrypted at application layer
    id_number_encrypted: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Encrypted IC or passport number"
    )
    assignment_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="available", index=True,
        comment="available | on_site | on_leave | inactive"
    )
    current_site_assignment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True,
        comment="FK to site_assignments.id — set when on_site"
    )
    work_permit_expiry: Mapped[Optional[date]] = mapped_column(
        Date, nullable=True,
        comment="Work permit expiry date for foreign workers"
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
    user: Mapped["User"] = relationship("User", lazy="selectin")

    def __repr__(self) -> str:
        return f"<StaffProfile user={self.user_id} status={self.assignment_status}>"


class StaffStatusHistory(Base):
    """
    Audit trail for staff assignment status changes.
    """

    __tablename__ = "staff_status_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    staff_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("staff_profiles.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    previous_status: Mapped[str] = mapped_column(String(20), nullable=False)
    new_status: Mapped[str] = mapped_column(String(20), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )
    changed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class SiteAssignment(Base):
    """
    Links a team of staff members to a client site for a date range.
    Replaces WhatsApp-based coordination.
    """

    __tablename__ = "site_assignments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="RESTRICT"),
        nullable=False, index=True
    )
    site_address: Mapped[str] = mapped_column(Text, nullable=False)
    supervisor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False, index=True,
        comment="Field supervisor responsible for this site"
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, index=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
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
    client: Mapped["Client"] = relationship("Client", lazy="selectin")
    supervisor: Mapped["User"] = relationship(
        "User", foreign_keys=[supervisor_id], lazy="selectin"
    )
    members: Mapped[List["SiteAssignmentMember"]] = relationship(
        "SiteAssignmentMember", back_populates="assignment",
        lazy="selectin", cascade="all, delete-orphan"
    )
    shifts: Mapped[List["Shift"]] = relationship(
        "Shift", back_populates="site_assignment",
        lazy="select", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<SiteAssignment client={self.client_id} active={self.is_active}>"


class SiteAssignmentMember(Base):
    """
    Junction table linking staff members to a site assignment with their role.
    """

    __tablename__ = "site_assignment_members"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    assignment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("site_assignments.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    staff_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("staff_profiles.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    role_at_site: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="Role at this specific site e.g. field_supervisor, waste_segregator"
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )
    left_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Relationships ─────────────────────────────────────────
    assignment: Mapped["SiteAssignment"] = relationship(
        "SiteAssignment", back_populates="members", lazy="selectin"
    )
    staff_profile: Mapped["StaffProfile"] = relationship(
        "StaffProfile", lazy="selectin"
    )


class Shift(Base):
    """
    A scheduled work period at a client site for a set of staff members.
    """

    __tablename__ = "shifts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    site_assignment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("site_assignments.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    shift_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    shift_type: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="morning | afternoon | night"
    )
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )

    # ── Relationships ─────────────────────────────────────────
    site_assignment: Mapped["SiteAssignment"] = relationship(
        "SiteAssignment", back_populates="shifts", lazy="selectin"
    )
    attendances: Mapped[List["ShiftAttendance"]] = relationship(
        "ShiftAttendance", back_populates="shift",
        lazy="selectin", cascade="all, delete-orphan"
    )
    creator: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[created_by], lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Shift {self.shift_date} {self.shift_type} site={self.site_assignment_id}>"


class ShiftAttendance(Base):
    """
    Tracks actual attendance for each staff member on each shift.
    """

    __tablename__ = "shift_attendances"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    shift_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shifts.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    staff_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("staff_profiles.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="present",
        comment="present | absent | no_checkout | late"
    )
    check_in_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    check_out_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    absence_reason: Mapped[Optional[str]] = mapped_column(
        String(30), nullable=True,
        comment="sick_leave | annual_leave | no_show | emergency"
    )
    recorded_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )

    # ── Relationships ─────────────────────────────────────────
    shift: Mapped["Shift"] = relationship(
        "Shift", back_populates="attendances", lazy="selectin"
    )
    staff_profile: Mapped["StaffProfile"] = relationship(
        "StaffProfile", lazy="selectin"
    )
    recorder: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[recorded_by], lazy="selectin"
    )


# =============================================================
# Pydantic Schemas — StaffProfile
# =============================================================


class StaffProfileCreate(BaseModel):
    user_id: uuid.UUID
    employment_type: str = Field(
        default="permanent",
        description="permanent | contract | foreign_worker"
    )
    labour_agent_name: Optional[str] = Field(None, max_length=200)
    work_permit_expiry: Optional[date] = None
    notes: Optional[str] = None

    model_config = ConfigDict(str_strip_whitespace=True)


class StaffProfileUpdate(BaseModel):
    employment_type: Optional[str] = None
    labour_agent_name: Optional[str] = Field(None, max_length=200)
    assignment_status: Optional[str] = None
    work_permit_expiry: Optional[date] = None
    notes: Optional[str] = None

    model_config = ConfigDict(str_strip_whitespace=True)


class StaffProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    employment_type: str
    labour_agent_name: Optional[str]
    assignment_status: str
    current_site_assignment_id: Optional[uuid.UUID]
    work_permit_expiry: Optional[date]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime


# =============================================================
# Pydantic Schemas — SiteAssignment
# =============================================================


class SiteAssignmentMemberInput(BaseModel):
    staff_profile_id: uuid.UUID
    role_at_site: str = Field(..., max_length=50)


class SiteAssignmentCreate(BaseModel):
    client_id: uuid.UUID
    site_address: str
    supervisor_id: uuid.UUID
    start_date: date
    end_date: Optional[date] = None
    members: List[SiteAssignmentMemberInput] = Field(
        ..., min_length=1, description="Must include at least one field_supervisor"
    )
    notes: Optional[str] = None

    model_config = ConfigDict(str_strip_whitespace=True)


class SiteAssignmentMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    assignment_id: uuid.UUID
    staff_profile_id: uuid.UUID
    role_at_site: str
    joined_at: datetime
    left_at: Optional[datetime]


class SiteAssignmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_id: uuid.UUID
    site_address: str
    supervisor_id: uuid.UUID
    start_date: date
    end_date: Optional[date]
    is_active: bool
    notes: Optional[str]
    created_at: datetime
    members: List[SiteAssignmentMemberRead] = []


# =============================================================
# Pydantic Schemas — Shift
# =============================================================


class ShiftCreate(BaseModel):
    site_assignment_id: uuid.UUID
    shift_date: date
    shift_type: str = Field(..., description="morning | afternoon | night")
    start_time: time
    end_time: time
    staff_profile_ids: List[uuid.UUID] = Field(..., min_length=1)
    notes: Optional[str] = None

    model_config = ConfigDict(str_strip_whitespace=True)


class ShiftRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    site_assignment_id: uuid.UUID
    shift_date: date
    shift_type: str
    start_time: time
    end_time: time
    created_by: Optional[uuid.UUID]
    notes: Optional[str]
    created_at: datetime
    attendances: List["ShiftAttendanceRead"] = []


class ShiftAttendanceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    shift_id: uuid.UUID
    staff_profile_id: uuid.UUID
    status: str
    check_in_at: Optional[datetime]
    check_out_at: Optional[datetime]
    absence_reason: Optional[str]
    notes: Optional[str]


class CheckInOut(BaseModel):
    """Used for check-in and check-out actions."""
    staff_profile_id: uuid.UUID
    timestamp: Optional[datetime] = None


class MarkAbsent(BaseModel):
    staff_profile_id: uuid.UUID
    absence_reason: str = Field(
        ..., description="sick_leave | annual_leave | no_show | emergency"
    )
    notes: Optional[str] = None
