# =============================================================
# Hi-Tech Waste Management — Recycler Delivery Models
# Container-to-recycler delivery workflow: manifest, proof of
# delivery, weight reconciliation, and buyer confirmation.
# =============================================================

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

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

if TYPE_CHECKING:
    from models.client import Client
    from models.equipment import Container
    from models.recyclable import DownstreamBuyer
    from models.user import User
    from models.vehicle import Vehicle

# =============================================================
# Valid value sets
# =============================================================

DELIVERY_STATUSES = {
    "pending_departure",
    "in_transit",
    "arrived",
    "proof_submitted",
    "reconciliation_discrepancy",
    "completed",
    "cancelled",
}


# =============================================================
# SQLAlchemy ORM Models
# =============================================================


class RecyclerDelivery(Base):
    """
    Records a container-to-recycler delivery trip with full chain-of-custody.

    Status pipeline:
    pending_departure → in_transit → arrived → proof_submitted
    → (reconciliation_discrepancy?) → completed
    """

    __tablename__ = "recycler_deliveries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    container_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("containers.id", ondelete="RESTRICT"),
        nullable=False, index=True
    )
    buyer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("downstream_buyers.id", ondelete="RESTRICT"),
        nullable=False, index=True
    )
    vehicle_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vehicles.id", ondelete="SET NULL"), nullable=True
    )
    driver_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="pending_departure", index=True,
        comment="pending_departure | in_transit | arrived | proof_submitted | reconciliation_discrepancy | completed | cancelled"
    )

    # Manifest fields
    declared_material_breakdown: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True,
        comment="Per-material declared weights in kg e.g. {paper_kg: 100, pet_kg: 50}"
    )
    declared_total_weight_kg: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 3), nullable=True
    )
    planned_departure_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Transport tracking
    departed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    arrived_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Proof of delivery
    proof_photos: Mapped[Optional[List[str]]] = mapped_column(
        JSON, nullable=True,
        comment="Array of photo URLs submitted as proof of delivery"
    )
    weight_ticket_ref: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True,
        comment="Recycler's weight ticket reference number"
    )
    recycler_recorded_weight_kg: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 3), nullable=True
    )
    proof_submitted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Reconciliation
    weight_variance_kg: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 3), nullable=True
    )
    weight_variance_pct: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 3), nullable=True
    )
    reconciliation_status: Mapped[Optional[str]] = mapped_column(
        String(30), nullable=True,
        comment="ok | discrepancy_accepted | discrepancy_rejected | pending_reweigh"
    )
    reconciliation_justification: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )

    # Buyer confirmation
    buyer_rep_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    buyer_confirmed_breakdown: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True,
        comment="Buyer's confirmed per-material weights"
    )
    buyer_reference_number: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    buyer_confirmed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Link back to recyclable record once completed
    recyclable_record_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("recyclable_records.id", ondelete="SET NULL"), nullable=True
    )

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
    buyer: Mapped["DownstreamBuyer"] = relationship(
        "DownstreamBuyer", lazy="selectin"
    )
    driver: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[driver_id], lazy="selectin"
    )
    creator: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[created_by], lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<RecyclerDelivery container={self.container_id} status={self.status}>"


# =============================================================
# Pydantic Schemas
# =============================================================


class RecyclerDeliveryCreate(BaseModel):
    container_id: uuid.UUID
    buyer_id: uuid.UUID
    vehicle_id: Optional[uuid.UUID] = None
    driver_id: Optional[uuid.UUID] = None
    declared_material_breakdown: Dict[str, float] = Field(
        ..., description="Per-material weights in kg e.g. {paper_kg: 100, pet_kg: 50}"
    )
    declared_total_weight_kg: Decimal = Field(..., gt=0)
    planned_departure_at: Optional[datetime] = None

    model_config = ConfigDict(str_strip_whitespace=True)


class ProofOfDeliverySubmit(BaseModel):
    proof_photos: List[str] = Field(
        ..., min_length=1, description="At least one photo URL required"
    )
    weight_ticket_ref: str = Field(..., min_length=1)
    recycler_recorded_weight_kg: Decimal = Field(..., gt=0)

    model_config = ConfigDict(str_strip_whitespace=True)


class ReconciliationReview(BaseModel):
    """Operations manager accepts or rejects a weight discrepancy."""
    action: str = Field(..., description="accept | reject")
    justification: Optional[str] = Field(
        None, description="Required when action = accept"
    )

    model_config = ConfigDict(str_strip_whitespace=True)


class BuyerConfirmationSubmit(BaseModel):
    buyer_rep_name: str = Field(..., max_length=200)
    buyer_confirmed_breakdown: Dict[str, float] = Field(
        ..., description="Buyer's confirmed per-material weights in kg"
    )
    buyer_reference_number: Optional[str] = Field(None, max_length=100)

    model_config = ConfigDict(str_strip_whitespace=True)


class RecyclerDeliveryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    container_id: uuid.UUID
    buyer_id: uuid.UUID
    vehicle_id: Optional[uuid.UUID]
    driver_id: Optional[uuid.UUID]
    status: str
    declared_material_breakdown: Optional[Dict[str, Any]]
    declared_total_weight_kg: Optional[Decimal]
    planned_departure_at: Optional[datetime]
    departed_at: Optional[datetime]
    arrived_at: Optional[datetime]
    proof_photos: Optional[List[str]]
    weight_ticket_ref: Optional[str]
    recycler_recorded_weight_kg: Optional[Decimal]
    proof_submitted_at: Optional[datetime]
    weight_variance_kg: Optional[Decimal]
    weight_variance_pct: Optional[Decimal]
    reconciliation_status: Optional[str]
    reconciliation_justification: Optional[str]
    buyer_rep_name: Optional[str]
    buyer_confirmed_breakdown: Optional[Dict[str, Any]]
    buyer_reference_number: Optional[str]
    buyer_confirmed_at: Optional[datetime]
    recyclable_record_id: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime


class ReconciliationRead(BaseModel):
    """Response for GET /recycler-deliveries/{id}/reconciliation"""
    delivery_id: uuid.UUID
    declared_total_weight_kg: Optional[Decimal]
    recycler_recorded_weight_kg: Optional[Decimal]
    variance_kg: Optional[Decimal]
    variance_pct: Optional[Decimal]
    reconciliation_status: Optional[str]
