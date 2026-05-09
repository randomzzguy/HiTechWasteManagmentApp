# =============================================================
# Hi-Tech Waste Management — Client Models
# SQLAlchemy async ORM models for clients and client_waste_streams
# =============================================================

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from database import Base
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from models.job import Job
    from models.user import User

# =============================================================
# ORM Models
# =============================================================


class Client(Base):
    """
    Represents a waste-management client (company).
    Each client can have multiple waste streams and a linked portal user.
    """

    __tablename__ = "clients"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    company_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    industry_vertical: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ssm_number: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, unique=True
    )
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Primary-in-charge (PIC) contact
    pic_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    pic_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    pic_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Linked portal user (the client's own login account)
    portal_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Contract & commercial details
    contract_start: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    contract_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    sla_diversion_target: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2), nullable=True, comment="Target diversion rate in percent (0-100)"
    )
    billing_model: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="e.g. per_trip, monthly_retainer, weight_based",
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # ── Relationships ─────────────────────────────────────────
    waste_streams: Mapped[List["ClientWasteStream"]] = relationship(
        "ClientWasteStream",
        back_populates="client",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    portal_user: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[portal_user_id],
        lazy="select",
    )
    jobs: Mapped[List["Job"]] = relationship(
        "Job",
        back_populates="client",
        lazy="select",
        foreign_keys="[Job.client_id]",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Client id={self.id} company='{self.company_name}'>"


class ClientWasteStream(Base):
    """
    Describes a specific waste type that a client generates,
    including expected volumes and handling requirements.
    """

    __tablename__ = "client_waste_streams"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    waste_type: Mapped[str] = mapped_column(String(100), nullable=False)
    estimated_kg_per_month: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    collection_frequency: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="e.g. weekly, fortnightly, monthly, on_call",
    )
    special_handling_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Relationships ─────────────────────────────────────────
    client: Mapped["Client"] = relationship("Client", back_populates="waste_streams")

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<ClientWasteStream id={self.id} client_id={self.client_id} "
            f"type='{self.waste_type}'>"
        )


# =============================================================
# Pydantic Schemas — ClientWasteStream
# =============================================================


class ClientWasteStreamBase(BaseModel):
    waste_type: str = Field(..., max_length=100, examples=["General Waste"])
    estimated_kg_per_month: Optional[Decimal] = Field(None, ge=0)
    collection_frequency: Optional[str] = Field(
        None, max_length=50, examples=["weekly"]
    )
    special_handling_notes: Optional[str] = None


class ClientWasteStreamCreate(ClientWasteStreamBase):
    pass


class ClientWasteStreamUpdate(BaseModel):
    waste_type: Optional[str] = Field(None, max_length=100)
    estimated_kg_per_month: Optional[Decimal] = Field(None, ge=0)
    collection_frequency: Optional[str] = Field(None, max_length=50)
    special_handling_notes: Optional[str] = None


class ClientWasteStreamRead(ClientWasteStreamBase):
    id: uuid.UUID
    client_id: uuid.UUID

    model_config = {"from_attributes": True}


# =============================================================
# Pydantic Schemas — Client
# =============================================================


class ClientBase(BaseModel):
    company_name: str = Field(..., max_length=255)
    industry_vertical: Optional[str] = Field(None, max_length=100)
    ssm_number: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = None
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    pic_name: Optional[str] = Field(None, max_length=255)
    pic_email: Optional[EmailStr] = None
    pic_phone: Optional[str] = Field(None, max_length=50)
    portal_user_id: Optional[uuid.UUID] = None
    contract_start: Optional[date] = None
    contract_end: Optional[date] = None
    sla_diversion_target: Optional[Decimal] = Field(None, ge=0, le=100)
    billing_model: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = None
    is_active: bool = True


class ClientCreate(ClientBase):
    waste_streams: Optional[List[ClientWasteStreamCreate]] = Field(default_factory=list)


class ClientUpdate(BaseModel):
    company_name: Optional[str] = Field(None, max_length=255)
    industry_vertical: Optional[str] = Field(None, max_length=100)
    ssm_number: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = None
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    pic_name: Optional[str] = Field(None, max_length=255)
    pic_email: Optional[EmailStr] = None
    pic_phone: Optional[str] = Field(None, max_length=50)
    portal_user_id: Optional[uuid.UUID] = None
    contract_start: Optional[date] = None
    contract_end: Optional[date] = None
    sla_diversion_target: Optional[Decimal] = Field(None, ge=0, le=100)
    billing_model: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class ClientRead(ClientBase):
    id: uuid.UUID
    created_at: datetime
    waste_streams: List[ClientWasteStreamRead] = []

    model_config = {"from_attributes": True}


class ClientListItem(BaseModel):
    """Lightweight client representation for list endpoints."""

    id: uuid.UUID
    company_name: str
    industry_vertical: Optional[str]
    city: Optional[str]
    state: Optional[str]
    pic_name: Optional[str]
    pic_email: Optional[str]
    is_active: bool
    contract_end: Optional[date]
    sla_diversion_target: Optional[Decimal]

    model_config = {"from_attributes": True}
