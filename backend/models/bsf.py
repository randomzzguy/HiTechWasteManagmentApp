# =============================================================
# Hi-Tech Waste Management — BSF (Black Soldier Fly) Batch Model
# SQLAlchemy 2.0 async ORM + Pydantic v2 schemas
# =============================================================

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from database import Base
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import (
    Date,
    DateTime,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

# =============================================================
# Valid value sets
# =============================================================

CONTAMINATION_LEVELS = {"clean", "minor", "rejected"}
BATCH_STATUSES = {"active", "completed", "rejected"}

# =============================================================
# SQLAlchemy ORM Model
# =============================================================


class BSFBatch(Base):
    """
    Tracks a Black Soldier Fly (BSF) bioconversion batch.

    Food waste collected from clients is fed to BSF larvae.
    The larvae consume the organic matter and are harvested as
    high-protein animal feed (frass and prepupae).

    Key metrics:
        - food_waste_kg       : total food waste input
        - larvae_output_kg    : protein biomass harvested
        - conversion_ratio    : larvae_output_kg / food_waste_kg
        - contamination_level : quality assessment of input waste

    source_job_ids stores the UUIDs of the collection jobs that
    contributed food waste to this batch, enabling full traceability
    back to individual client collections.
    """

    __tablename__ = "bsf_batches"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
        index=True,
    )
    intake_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
        comment="Date the food waste batch was received into the BSF farm",
    )

    # Array of job UUIDs that contributed food waste to this batch (stored as JSON for cross-DB compatibility)
    source_job_ids: Mapped[Optional[List[uuid.UUID]]] = mapped_column(
        JSON,
        nullable=True,
        default=list,
        comment="UUIDs of collection jobs that supplied food waste for this batch (as JSON array of strings)",
    )

    food_waste_kg: Mapped[Decimal] = mapped_column(
        Numeric(12, 3),
        nullable=False,
        comment="Total food waste input to the batch in kilograms",
    )

    # JSON structure capturing contribution per client:
    # [{"client_id": "uuid", "client_name": "ABC Sdn Bhd", "kg": 250.5}, ...]
    client_sources: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Per-client breakdown of food waste contributions",
    )

    contamination_level: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="clean",
        comment="clean | minor | rejected — quality assessment of input waste",
    )

    larvae_output_kg: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 3),
        nullable=True,
        comment="Protein biomass (prepupae / frass) harvested in kilograms",
    )
    conversion_ratio: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 4),
        nullable=True,
        comment=(
            "larvae_output_kg / food_waste_kg. Computed in Python at harvest time."
        ),
    )

    livestock_recipient: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Farm or buyer that received the larvae output",
    )

    batch_start: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="Date larvae inoculation / batch processing began",
    )
    batch_end: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="Date batch was harvested / completed / rejected",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="active",
        index=True,
        comment="active | completed | rejected",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    # ── Python-level computed properties ──────────────────────

    @property
    def computed_conversion_ratio(self) -> Optional[Decimal]:
        """
        Returns larvae_output_kg / food_waste_kg.
        Authoritative value — stored conversion_ratio is populated
        from this at harvest/completion time.
        """
        if self.larvae_output_kg is not None and self.food_waste_kg:
            return Decimal(str(self.larvae_output_kg)) / Decimal(
                str(self.food_waste_kg)
            )
        return None

    @property
    def duration_days(self) -> Optional[int]:
        """Number of days the batch ran (batch_end - batch_start)."""
        if self.batch_start and self.batch_end:
            return (self.batch_end - self.batch_start).days
        return None

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<BSFBatch id={self.id} intake={self.intake_date} "
            f"food_kg={self.food_waste_kg} status={self.status}>"
        )


# =============================================================
# Pydantic Schemas
# =============================================================


class BSFBatchCreate(BaseModel):
    """Schema for creating a new BSF batch from food waste collection jobs."""

    intake_date: date = Field(
        ...,
        description="Date food waste was received into the BSF facility",
    )
    source_job_ids: Optional[List[uuid.UUID]] = Field(
        default=None,
        description="Collection job UUIDs that contributed food waste",
    )
    food_waste_kg: Decimal = Field(
        ...,
        gt=0,
        description="Total food waste input in kilograms",
    )
    client_sources: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description=(
            "Per-client contribution list: [{client_id, client_name, kg}, ...]"
        ),
    )
    contamination_level: str = Field(
        default="clean",
        description="clean | minor | rejected",
    )
    batch_start: Optional[date] = Field(
        default=None,
        description="Date larvae inoculation began (defaults to intake_date)",
    )
    livestock_recipient: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Intended farm or buyer for larvae output",
    )

    model_config = ConfigDict(str_strip_whitespace=True)

    @model_validator(mode="after")
    def validate_contamination_level(self) -> "BSFBatchCreate":
        if self.contamination_level not in CONTAMINATION_LEVELS:
            raise ValueError(
                f"contamination_level must be one of {sorted(CONTAMINATION_LEVELS)}"
            )
        return self


class BSFBatchUpdate(BaseModel):
    """
    Schema for partial updates to a BSF batch.
    Typically used to record harvest results (larvae_output_kg, conversion_ratio,
    batch_end, status change to completed/rejected).
    """

    larvae_output_kg: Optional[Decimal] = Field(
        default=None,
        ge=0,
        description="Protein biomass harvested in kg",
    )
    conversion_ratio: Optional[Decimal] = Field(
        default=None,
        ge=0,
        description="Override computed conversion ratio if needed",
    )
    livestock_recipient: Optional[str] = Field(default=None, max_length=255)
    batch_end: Optional[date] = Field(
        default=None,
        description="Date batch was completed or rejected",
    )
    status: Optional[str] = Field(
        default=None,
        description="active | completed | rejected",
    )
    contamination_level: Optional[str] = None
    client_sources: Optional[List[Dict[str, Any]]] = None
    source_job_ids: Optional[List[uuid.UUID]] = None

    model_config = ConfigDict(str_strip_whitespace=True)

    @model_validator(mode="after")
    def validate_fields(self) -> "BSFBatchUpdate":
        if self.status is not None and self.status not in BATCH_STATUSES:
            raise ValueError(f"status must be one of {sorted(BATCH_STATUSES)}")
        if (
            self.contamination_level is not None
            and self.contamination_level not in CONTAMINATION_LEVELS
        ):
            raise ValueError(
                f"contamination_level must be one of {sorted(CONTAMINATION_LEVELS)}"
            )
        return self


class BSFBatchRead(BaseModel):
    """Full BSF batch representation returned to API consumers."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    intake_date: date
    source_job_ids: Optional[List[uuid.UUID]]
    food_waste_kg: Decimal
    client_sources: Optional[Any]
    contamination_level: str
    larvae_output_kg: Optional[Decimal]
    conversion_ratio: Optional[Decimal]
    livestock_recipient: Optional[str]
    batch_start: Optional[date]
    batch_end: Optional[date]
    duration_days: Optional[int] = None
    status: str
    created_at: datetime

    @classmethod
    def from_orm_with_computed(cls, obj: BSFBatch) -> "BSFBatchRead":
        """Populate computed properties not natively handled by from_attributes."""
        data = {
            "id": obj.id,
            "intake_date": obj.intake_date,
            "source_job_ids": obj.source_job_ids,
            "food_waste_kg": obj.food_waste_kg,
            "client_sources": obj.client_sources,
            "contamination_level": obj.contamination_level,
            "larvae_output_kg": obj.larvae_output_kg,
            "conversion_ratio": (
                obj.conversion_ratio
                if obj.conversion_ratio is not None
                else obj.computed_conversion_ratio
            ),
            "livestock_recipient": obj.livestock_recipient,
            "batch_start": obj.batch_start,
            "batch_end": obj.batch_end,
            "duration_days": obj.duration_days,
            "status": obj.status,
            "created_at": obj.created_at,
        }
        return cls(**data)


class BSFBatchListItem(BaseModel):
    """Lightweight representation for list endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    intake_date: date
    food_waste_kg: Decimal
    larvae_output_kg: Optional[Decimal]
    conversion_ratio: Optional[Decimal]
    contamination_level: str
    status: str
    batch_start: Optional[date]
    batch_end: Optional[date]
    livestock_recipient: Optional[str]


# =============================================================
# Aggregation / Stats Response Schemas
# =============================================================


class BSFCircularityStats(BaseModel):
    """
    Aggregate circularity metrics for the BSF farm,
    returned by GET /bsf/stats/circularity.
    """

    total_food_waste_kg: Decimal = Field(
        description="Total food waste processed across all completed batches"
    )
    total_larvae_output_kg: Decimal = Field(
        description="Total protein biomass harvested"
    )
    average_conversion_ratio: Optional[Decimal] = Field(
        default=None,
        description="Mean larvae_output_kg / food_waste_kg across completed batches",
    )
    batch_count: int = Field(description="Number of batches included in the aggregate")
    completed_batches: int
    rejected_batches: int
    active_batches: int
    top_client_sources: List[Dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "Top clients by food-waste contribution, sorted descending by total_kg"
        ),
    )
