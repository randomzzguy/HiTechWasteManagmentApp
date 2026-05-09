# =============================================================
# Hi-Tech Waste Management — Scheduled Waste Models
# SQLAlchemy async ORM models + Pydantic v2 schemas
# scheduled_waste_batches & consignment_notes
# =============================================================

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from models.user import User

from database import Base
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

# =============================================================
# ORM Models
# =============================================================


class ScheduledWasteBatch(Base):
    """
    Tracks a batch of scheduled (hazardous) waste held in on-site storage.

    Malaysian DOE regulations mandate that scheduled waste must be
    collected and disposed of within 180 days (or 90 days for certain
    codes). The storage_deadline is enforced as a Python property so
    compliance logic does not depend on DB-level computed columns.
    """

    __tablename__ = "scheduled_waste_batches"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    job_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    sw_code: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="e.g. SW 305, SW 410 — DOE scheduled waste code",
    )
    waste_description: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    quantity_kg: Mapped[Decimal] = mapped_column(
        Numeric(12, 3),
        nullable=False,
    )
    physical_state: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="solid",
        comment="solid | liquid | sludge | gas",
    )
    container_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="e.g. 200L drum, IBC, sealed bag",
    )
    container_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    storage_start_date: Mapped[date] = mapped_column(nullable=False)
    # storage_deadline is derived (start + 90 days) via Python property below.
    # Stored separately so queries can filter/sort on it directly.
    _storage_deadline_db: Mapped[Optional[date]] = mapped_column(
        "storage_deadline",
        nullable=True,
        comment="Computed: storage_start_date + 90 days. Populated on insert.",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="in_storage",
        index=True,
        comment="in_storage | dispatched | processed",
    )
    consignment_note_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="Populated once a consignment note is linked",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # ── Relationships ─────────────────────────────────────────
    consignment_note: Mapped[Optional["ConsignmentNote"]] = relationship(
        "ConsignmentNote",
        back_populates="batch",
        uselist=False,
        lazy="selectin",
    )

    # ── Python-level computed property ────────────────────────
    @property
    def storage_deadline(self) -> Optional[date]:
        """
        Returns storage_start_date + 90 days.
        The DB column is populated at write time by the router/service layer
        to keep query filtering fast; this property is the authoritative source.
        """
        if self.storage_start_date is None:
            return None
        from datetime import timedelta

        return self.storage_start_date + timedelta(days=90)

    @property
    def days_remaining(self) -> Optional[int]:
        """
        Calendar days until the 90-day storage deadline, relative to today.
        Negative value means the deadline has already passed.
        """
        deadline = self.storage_deadline
        if deadline is None:
            return None
        return (deadline - date.today()).days

    def __repr__(self) -> str:
        return (
            f"<ScheduledWasteBatch id={self.id} sw_code={self.sw_code} "
            f"status={self.status} deadline={self.storage_deadline}>"
        )


class ConsignmentNote(Base):
    """
    Official consignment note (CN) accompanying a scheduled-waste shipment.
    Generated from a ScheduledWasteBatch when the waste is ready for collection.
    """

    __tablename__ = "consignment_notes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scheduled_waste_batches.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        index=True,
    )
    note_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="Human-readable CN number, e.g. CN-2024-00123",
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    cenviro_reference: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Cenviro (DOE portal) tracking reference",
    )
    transport_date: Mapped[Optional[date]] = mapped_column(nullable=True)
    transporter_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    vehicle_registration: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True
    )
    processing_facility: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="draft",
        index=True,
        comment="draft | submitted | confirmed | processed",
    )
    pdf_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    signed_by_hitech: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Hi-Tech staff who signed the CN",
    )
    signed_by_client: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Client representative who signed the CN",
    )

    # ── Relationships ─────────────────────────────────────────
    batch: Mapped["ScheduledWasteBatch"] = relationship(
        "ScheduledWasteBatch",
        back_populates="consignment_note",
        lazy="selectin",
    )
    signer_hitech: Mapped[Optional["User"]] = relationship(  # type: ignore[name-defined]
        "User",
        foreign_keys=[signed_by_hitech],
        lazy="select",
    )
    signer_client: Mapped[Optional["User"]] = relationship(  # type: ignore[name-defined]
        "User",
        foreign_keys=[signed_by_client],
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"<ConsignmentNote id={self.id} number={self.note_number} "
            f"status={self.status}>"
        )


# =============================================================
# Pydantic Schemas — ScheduledWasteBatch
# =============================================================

PHYSICAL_STATES = {"solid", "liquid", "sludge", "gas"}
BATCH_STATUSES = {"in_storage", "dispatched", "processed"}


class ScheduledWasteBatchCreate(BaseModel):
    job_id: Optional[uuid.UUID] = None
    client_id: uuid.UUID
    sw_code: str = Field(
        ...,
        max_length=20,
        examples=["SW 305"],
        description="DOE scheduled waste code",
    )
    waste_description: str = Field(..., max_length=500)
    quantity_kg: Decimal = Field(..., gt=0)
    physical_state: str = Field(
        default="solid",
        description="solid | liquid | sludge | gas",
    )
    container_type: Optional[str] = Field(None, max_length=100)
    container_count: Optional[int] = Field(None, ge=1)
    storage_start_date: date

    model_config = {"str_strip_whitespace": True}

    @model_validator(mode="after")
    def validate_physical_state(self) -> "ScheduledWasteBatchCreate":
        if self.physical_state not in PHYSICAL_STATES:
            raise ValueError(f"physical_state must be one of {sorted(PHYSICAL_STATES)}")
        return self


class ScheduledWasteBatchUpdate(BaseModel):
    sw_code: Optional[str] = Field(None, max_length=20)
    waste_description: Optional[str] = Field(None, max_length=500)
    quantity_kg: Optional[Decimal] = Field(None, gt=0)
    physical_state: Optional[str] = None
    container_type: Optional[str] = Field(None, max_length=100)
    container_count: Optional[int] = Field(None, ge=1)
    storage_start_date: Optional[date] = None
    status: Optional[str] = None
    consignment_note_id: Optional[uuid.UUID] = None

    @model_validator(mode="after")
    def validate_fields(self) -> "ScheduledWasteBatchUpdate":
        if (
            self.physical_state is not None
            and self.physical_state not in PHYSICAL_STATES
        ):
            raise ValueError(f"physical_state must be one of {sorted(PHYSICAL_STATES)}")
        if self.status is not None and self.status not in BATCH_STATUSES:
            raise ValueError(f"status must be one of {sorted(BATCH_STATUSES)}")
        return self


class ScheduledWasteBatchStatusUpdate(BaseModel):
    status: str = Field(..., description="in_storage | dispatched | processed")
    notes: Optional[str] = None

    @model_validator(mode="after")
    def validate_status(self) -> "ScheduledWasteBatchStatusUpdate":
        if self.status not in BATCH_STATUSES:
            raise ValueError(f"status must be one of {sorted(BATCH_STATUSES)}")
        return self


class ScheduledWasteBatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: Optional[uuid.UUID]
    client_id: uuid.UUID
    sw_code: str
    waste_description: str
    quantity_kg: Decimal
    physical_state: str
    container_type: Optional[str]
    container_count: Optional[int]
    storage_start_date: date
    storage_deadline: Optional[date]  # resolved via property
    days_remaining: Optional[int]  # resolved via property
    status: str
    consignment_note_id: Optional[uuid.UUID]
    created_at: datetime

    @classmethod
    def from_orm_with_computed(
        cls, obj: ScheduledWasteBatch
    ) -> "ScheduledWasteBatchRead":
        return cls(
            id=obj.id,
            job_id=obj.job_id,
            client_id=obj.client_id,
            sw_code=obj.sw_code,
            waste_description=obj.waste_description,
            quantity_kg=obj.quantity_kg,
            physical_state=obj.physical_state,
            container_type=obj.container_type,
            container_count=obj.container_count,
            storage_start_date=obj.storage_start_date,
            storage_deadline=obj.storage_deadline,
            days_remaining=obj.days_remaining,
            status=obj.status,
            consignment_note_id=obj.consignment_note_id,
            created_at=obj.created_at,
        )


# =============================================================
# Pydantic Schemas — ConsignmentNote
# =============================================================

CN_STATUSES = {"draft", "submitted", "confirmed", "processed"}


class ConsignmentNoteCreate(BaseModel):
    batch_id: uuid.UUID
    cenviro_reference: Optional[str] = Field(None, max_length=100)
    transport_date: Optional[date] = None
    transporter_name: Optional[str] = Field(None, max_length=255)
    vehicle_registration: Optional[str] = Field(None, max_length=20)
    processing_facility: Optional[str] = Field(None, max_length=255)

    model_config = {"str_strip_whitespace": True}


class ConsignmentNoteUpdate(BaseModel):
    cenviro_reference: Optional[str] = Field(None, max_length=100)
    transport_date: Optional[date] = None
    transporter_name: Optional[str] = Field(None, max_length=255)
    vehicle_registration: Optional[str] = Field(None, max_length=20)
    processing_facility: Optional[str] = Field(None, max_length=255)
    status: Optional[str] = None
    pdf_path: Optional[str] = None
    signed_by_hitech: Optional[uuid.UUID] = None
    signed_by_client: Optional[uuid.UUID] = None

    @model_validator(mode="after")
    def validate_status(self) -> "ConsignmentNoteUpdate":
        if self.status is not None and self.status not in CN_STATUSES:
            raise ValueError(f"status must be one of {sorted(CN_STATUSES)}")
        return self


class ConsignmentNoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    batch_id: uuid.UUID
    note_number: str
    generated_at: datetime
    cenviro_reference: Optional[str]
    transport_date: Optional[date]
    transporter_name: Optional[str]
    vehicle_registration: Optional[str]
    processing_facility: Optional[str]
    status: str
    pdf_path: Optional[str]
    signed_by_hitech: Optional[uuid.UUID]
    signed_by_client: Optional[uuid.UUID]
