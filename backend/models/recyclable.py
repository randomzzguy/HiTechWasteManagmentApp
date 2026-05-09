# =============================================================
# Hi-Tech Waste Management — Recyclable Models
# SQLAlchemy 2.0 async ORM + Pydantic v2 schemas
# recyclable_records & downstream_buyers
# =============================================================

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from models.client import Client
    from models.job import Job

from database import Base
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import (
    Boolean,
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


class DownstreamBuyer(Base):
    """
    Represents a licensed downstream buyer / recycler who purchases
    segregated recyclable materials from Hi-Tech Waste Management.

    material_types is stored as a JSON array of text values,
    e.g. ['paper', 'pet', 'hdpe', 'aluminium'].
    """

    __tablename__ = "downstream_buyers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    company_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    material_types: Mapped[Optional[List[str]]] = mapped_column(
        JSON,
        nullable=True,
        default=list,
        comment="e.g. ['paper', 'pet', 'hdpe', 'aluminium', 'ferrous', 'glass', 'ewaste'] (stored as JSON array)",
    )
    contact_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    license_number: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        unique=True,
        comment="DOE or local authority recycling license number",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    # ── Relationships ─────────────────────────────────────────
    recyclable_records: Mapped[List["RecyclableRecord"]] = relationship(
        "RecyclableRecord",
        back_populates="buyer",
        lazy="select",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<DownstreamBuyer id={self.id} "
            f"company='{self.company_name}' active={self.is_active}>"
        )


class RecyclableRecord(Base):
    """
    Records a single recyclable-material collection event for a job.

    material_breakdown stores per-material weights (kg) as JSON:
    {
        "paper_kg":      150.0,
        "pet_kg":         80.5,
        "hdpe_kg":        40.0,
        "aluminium_kg":   12.0,
        "ferrous_kg":     25.0,
        "glass_kg":        0.0,
        "ewaste_kg":       5.5
    }

    total_recyclable_kg is stored explicitly for fast aggregation queries.
    """

    __tablename__ = "recyclable_records"

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
    client_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        index=True,
    )
    # Per-material breakdown stored as flexible JSON
    material_breakdown: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment=(
            "Keys: paper_kg, pet_kg, hdpe_kg, aluminium_kg, "
            "ferrous_kg, glass_kg, ewaste_kg"
        ),
    )
    total_recyclable_kg: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 3),
        nullable=True,
        comment="Sum of all material_breakdown values; pre-computed for query speed",
    )
    buyer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("downstream_buyers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    sale_value_myr: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
        comment="Revenue received from buyer in Malaysian Ringgit",
    )
    certificate_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="FK to certificates.id once a recycling certificate is generated",
    )

    # ── Relationships ─────────────────────────────────────────
    job: Mapped[Optional["Job"]] = relationship(
        "Job",
        foreign_keys=[job_id],
        lazy="selectin",
    )
    client: Mapped[Optional["Client"]] = relationship(
        "Client",
        foreign_keys=[client_id],
        lazy="selectin",
    )
    buyer: Mapped[Optional["DownstreamBuyer"]] = relationship(
        "DownstreamBuyer",
        back_populates="recyclable_records",
        lazy="selectin",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<RecyclableRecord id={self.id} "
            f"recorded_at={self.recorded_at} "
            f"total_kg={self.total_recyclable_kg}>"
        )


# =============================================================
# Pydantic Schemas — DownstreamBuyer
# =============================================================


class DownstreamBuyerCreate(BaseModel):
    company_name: str = Field(..., max_length=255)
    material_types: Optional[List[str]] = Field(
        default=None,
        description=(
            "List of material types accepted, e.g. "
            "['paper', 'pet', 'hdpe', 'aluminium', 'ferrous', 'glass', 'ewaste']"
        ),
    )
    contact_name: Optional[str] = Field(None, max_length=255)
    contact_phone: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = None
    license_number: Optional[str] = Field(None, max_length=100)
    is_active: bool = True

    model_config = ConfigDict(str_strip_whitespace=True)


class DownstreamBuyerUpdate(BaseModel):
    company_name: Optional[str] = Field(None, max_length=255)
    material_types: Optional[List[str]] = None
    contact_name: Optional[str] = Field(None, max_length=255)
    contact_phone: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = None
    license_number: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None

    model_config = ConfigDict(str_strip_whitespace=True)


class DownstreamBuyerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_name: str
    material_types: Optional[List[str]]
    contact_name: Optional[str]
    contact_phone: Optional[str]
    address: Optional[str]
    license_number: Optional[str]
    is_active: bool


# =============================================================
# Pydantic Schemas — RecyclableRecord
# =============================================================


class MaterialBreakdown(BaseModel):
    """
    Strongly-typed breakdown of recyclable material weights.
    All fields default to None so partial records are allowed.
    """

    paper_kg: Optional[Decimal] = Field(None, ge=0, description="Paper / cardboard kg")
    pet_kg: Optional[Decimal] = Field(None, ge=0, description="PET plastic kg")
    hdpe_kg: Optional[Decimal] = Field(None, ge=0, description="HDPE plastic kg")
    aluminium_kg: Optional[Decimal] = Field(None, ge=0, description="Aluminium kg")
    ferrous_kg: Optional[Decimal] = Field(None, ge=0, description="Ferrous / steel kg")
    glass_kg: Optional[Decimal] = Field(None, ge=0, description="Glass kg")
    ewaste_kg: Optional[Decimal] = Field(None, ge=0, description="Electronic waste kg")

    def total_kg(self) -> Decimal:
        """Returns the sum of all non-null material weights."""
        total = Decimal("0")
        for val in [
            self.paper_kg,
            self.pet_kg,
            self.hdpe_kg,
            self.aluminium_kg,
            self.ferrous_kg,
            self.glass_kg,
            self.ewaste_kg,
        ]:
            if val is not None:
                total += val
        return total

    def to_dict(self) -> Dict[str, Any]:
        """Serialises to a plain dict for JSON column storage."""
        return {
            "paper_kg": float(self.paper_kg) if self.paper_kg is not None else None,
            "pet_kg": float(self.pet_kg) if self.pet_kg is not None else None,
            "hdpe_kg": float(self.hdpe_kg) if self.hdpe_kg is not None else None,
            "aluminium_kg": (
                float(self.aluminium_kg) if self.aluminium_kg is not None else None
            ),
            "ferrous_kg": (
                float(self.ferrous_kg) if self.ferrous_kg is not None else None
            ),
            "glass_kg": float(self.glass_kg) if self.glass_kg is not None else None,
            "ewaste_kg": float(self.ewaste_kg) if self.ewaste_kg is not None else None,
        }


class RecyclableRecordCreate(BaseModel):
    job_id: Optional[uuid.UUID] = None
    client_id: Optional[uuid.UUID] = None
    recorded_at: Optional[datetime] = Field(
        default=None,
        description="Measurement timestamp; defaults to server UTC now",
    )
    material_breakdown: Optional[MaterialBreakdown] = None
    # If total_recyclable_kg is omitted it is computed from material_breakdown
    total_recyclable_kg: Optional[Decimal] = Field(None, ge=0)
    buyer_id: Optional[uuid.UUID] = None
    sale_value_myr: Optional[Decimal] = Field(None, ge=0)

    model_config = ConfigDict(str_strip_whitespace=True)


class RecyclableRecordUpdate(BaseModel):
    material_breakdown: Optional[MaterialBreakdown] = None
    total_recyclable_kg: Optional[Decimal] = Field(None, ge=0)
    buyer_id: Optional[uuid.UUID] = None
    sale_value_myr: Optional[Decimal] = Field(None, ge=0)
    certificate_id: Optional[uuid.UUID] = None

    model_config = ConfigDict(str_strip_whitespace=True)


class RecyclableRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: Optional[uuid.UUID]
    client_id: Optional[uuid.UUID]
    recorded_at: datetime
    material_breakdown: Optional[Dict[str, Any]]
    total_recyclable_kg: Optional[Decimal]
    buyer_id: Optional[uuid.UUID]
    sale_value_myr: Optional[Decimal]
    certificate_id: Optional[uuid.UUID]


# =============================================================
# Aggregation response schemas (used by /stats endpoint)
# =============================================================


class RecyclableStatsMaterial(BaseModel):
    """Per-material aggregate totals."""

    material: str
    total_kg: Decimal
    revenue_myr: Optional[Decimal] = None


class RecyclableStatsResponse(BaseModel):
    """Response body for GET /recyclables/stats."""

    period_from: Optional[str] = None
    period_to: Optional[str] = None
    total_recyclable_kg: Decimal
    total_revenue_myr: Decimal
    material_breakdown: List[RecyclableStatsMaterial]
    top_material: Optional[str] = None
    record_count: int
