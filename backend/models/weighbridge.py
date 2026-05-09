# =============================================================
# Hi-Tech Waste Management — Weighbridge Model
# SQLAlchemy async ORM + Pydantic v2 schemas
# =============================================================

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, Optional

from database import Base
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import DateTime, ForeignKey, Numeric, Text, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from models.client import Client
    from models.job import Job
    from models.user import User

# =============================================================
# SQLAlchemy ORM Model
# =============================================================


class WeighbridgeRecord(Base):
    """
    Records a weighbridge measurement for a job.

    The composite primary key (id, recorded_at) mirrors a TimescaleDB
    hypertable pattern, allowing efficient time-range partitioning.

    net_weight_kg is computed in Python as (gross_weight_kg - tare_weight_kg)
    and stored for fast querying — it is NOT a generated/computed DB column.
    """

    __tablename__ = "weighbridge_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        primary_key=True,  # composite PK — second component
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
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

    gross_weight_kg: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 3),
        nullable=True,
        comment="Total weight of loaded vehicle on weighbridge (kg)",
    )
    tare_weight_kg: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 3),
        nullable=True,
        comment="Empty vehicle weight (kg)",
    )
    net_weight_kg: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 3),
        nullable=True,
        comment="gross - tare; computed in Python before INSERT",
    )

    # Breakdown by waste type, e.g.:
    # {"general_waste_kg": 500.0, "recyclable_kg": 120.5, "scheduled_waste_kg": 80.0}
    waste_type_breakdown: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
    )

    operator_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

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
    operator: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[operator_id],
        lazy="selectin",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<WeighbridgeRecord id={self.id} "
            f"recorded_at={self.recorded_at} "
            f"net_kg={self.net_weight_kg}>"
        )


# =============================================================
# Pydantic Schemas
# =============================================================


class WeighbridgeCreate(BaseModel):
    """
    Schema for creating a new weighbridge record.

    net_weight_kg is optional — if omitted it will be computed from
    gross_weight_kg - tare_weight_kg by the API handler before persisting.
    """

    job_id: Optional[uuid.UUID] = None
    client_id: Optional[uuid.UUID] = None
    recorded_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp of measurement; defaults to server UTC now",
    )
    gross_weight_kg: Optional[Decimal] = Field(None, ge=0)
    tare_weight_kg: Optional[Decimal] = Field(None, ge=0)
    net_weight_kg: Optional[Decimal] = Field(
        None,
        ge=0,
        description="If omitted, computed as gross - tare",
    )
    waste_type_breakdown: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "Keyed breakdown of waste categories, "
            "e.g. {'general_waste_kg': 500.0, 'recyclable_kg': 120.5}"
        ),
    )
    operator_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None

    model_config = {"str_strip_whitespace": True}

    @model_validator(mode="after")
    def compute_net_weight(self) -> "WeighbridgeCreate":
        """Auto-compute net_weight_kg when gross and tare are both provided."""
        if (
            self.net_weight_kg is None
            and self.gross_weight_kg is not None
            and self.tare_weight_kg is not None
        ):
            computed = self.gross_weight_kg - self.tare_weight_kg
            if computed < 0:
                raise ValueError(
                    "net_weight_kg cannot be negative "
                    "(gross_weight_kg must be >= tare_weight_kg)"
                )
            self.net_weight_kg = computed
        return self


class WeighbridgeRead(BaseModel):
    """Schema returned to API consumers for a weighbridge record."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    recorded_at: datetime
    job_id: Optional[uuid.UUID]
    client_id: Optional[uuid.UUID]
    gross_weight_kg: Optional[Decimal]
    tare_weight_kg: Optional[Decimal]
    net_weight_kg: Optional[Decimal]
    waste_type_breakdown: Optional[Dict[str, Any]]
    operator_id: Optional[uuid.UUID]
    notes: Optional[str]


class WeighbridgeUpdate(BaseModel):
    """Schema for partial updates to an existing weighbridge record."""

    gross_weight_kg: Optional[Decimal] = Field(None, ge=0)
    tare_weight_kg: Optional[Decimal] = Field(None, ge=0)
    net_weight_kg: Optional[Decimal] = Field(None, ge=0)
    waste_type_breakdown: Optional[Dict[str, Any]] = None
    operator_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None

    model_config = {"str_strip_whitespace": True}

    @model_validator(mode="after")
    def recompute_net_weight(self) -> "WeighbridgeUpdate":
        """Re-compute net if gross/tare updated but net not explicitly provided."""
        if (
            self.net_weight_kg is None
            and self.gross_weight_kg is not None
            and self.tare_weight_kg is not None
        ):
            computed = self.gross_weight_kg - self.tare_weight_kg
            if computed < 0:
                raise ValueError(
                    "net_weight_kg cannot be negative "
                    "(gross_weight_kg must be >= tare_weight_kg)"
                )
            self.net_weight_kg = computed
        return self


# =============================================================
# Aggregation response schemas (used by /stats endpoints)
# =============================================================


class TonnageStatPoint(BaseModel):
    """Single data point in a tonnage time-series response."""

    period: str = Field(description="ISO date string representing the period start")
    total_net_kg: Decimal
    total_gross_kg: Optional[Decimal] = None
    record_count: int


class DiversionStatPoint(BaseModel):
    """Diversion rate for a given period or grouping."""

    period: str
    total_kg: Decimal
    diverted_kg: Decimal
    diversion_rate_pct: Decimal = Field(
        description="(recyclable + diverted) / total * 100"
    )
