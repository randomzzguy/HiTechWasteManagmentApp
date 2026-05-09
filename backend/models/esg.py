# =============================================================
# Hi-Tech Waste Management — ESG / Carbon Record Model
# SQLAlchemy 2.0 async ORM + Pydantic v2 schemas
# =============================================================

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from models.client import Client
    from models.job import Job

from database import Base
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import DateTime, ForeignKey, Numeric, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

# =============================================================
# SQLAlchemy ORM Model
# =============================================================


class CarbonRecord(Base):
    """
    Stores the carbon impact calculation for a single job or collection event.

    Methodology components:
        transport_emissions_kgco2e  — CO₂e from vehicle fuel consumption
        landfill_avoidance_kgco2e  — Credit for waste diverted from landfill
        recycling_credit_kgco2e    — Credit for material recycling
        wte_credit_kgco2e          — Credit for waste-to-energy processing

    net_carbon_impact_kgco2e is computed in Python as:
        transport_emissions - landfill_avoidance - recycling_credit - wte_credit

    A negative net value indicates a net-positive environmental outcome
    (more carbon avoided than emitted).
    """

    __tablename__ = "carbon_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
        index=True,
    )
    job_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="The job this carbon calculation is linked to",
    )
    client_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Denormalised client FK for faster client-scoped ESG queries",
    )
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        index=True,
        comment="Timestamp when this carbon calculation was performed",
    )

    # ── Emission components (kgCO₂e) ─────────────────────────
    transport_emissions_kgco2e: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(14, 4),
        nullable=True,
        comment=(
            "CO₂ equivalent emissions from fleet fuel consumption for this job "
            "(positive value = carbon emitted)"
        ),
    )
    landfill_avoidance_kgco2e: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(14, 4),
        nullable=True,
        comment=(
            "Carbon credit for diverting waste from landfill "
            "(positive value = carbon avoided)"
        ),
    )
    recycling_credit_kgco2e: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(14, 4),
        nullable=True,
        comment=(
            "Carbon credit attributed to recyclable material recovery "
            "(positive value = carbon avoided)"
        ),
    )
    wte_credit_kgco2e: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(14, 4),
        nullable=True,
        comment=(
            "Carbon credit from waste-to-energy processing "
            "(positive value = carbon avoided)"
        ),
    )
    net_carbon_impact_kgco2e: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(14, 4),
        nullable=True,
        comment=(
            "Net carbon impact = transport_emissions "
            "- landfill_avoidance - recycling_credit - wte_credit. "
            "Negative = net environmental benefit."
        ),
    )

    methodology_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment=(
            "Free-text description of the emission factors and methodology "
            "used for this calculation (e.g. GHG Protocol, IPCC AR6)"
        ),
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

    # ── Python-level computed property ────────────────────────

    @property
    def computed_net_impact(self) -> Optional[Decimal]:
        """
        Authoritative net carbon impact computation.

        net = transport_emissions
              - landfill_avoidance
              - recycling_credit
              - wte_credit

        Returns None if transport_emissions is not set (insufficient data).
        All credit fields default to Decimal('0') if None.
        """
        if self.transport_emissions_kgco2e is None:
            return None
        zero = Decimal("0")
        return (
            self.transport_emissions_kgco2e
            - (self.landfill_avoidance_kgco2e or zero)
            - (self.recycling_credit_kgco2e or zero)
            - (self.wte_credit_kgco2e or zero)
        )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<CarbonRecord id={self.id} "
            f"job_id={self.job_id} "
            f"net_kgco2e={self.net_carbon_impact_kgco2e} "
            f"calculated_at={self.calculated_at}>"
        )


# =============================================================
# Pydantic Schemas
# =============================================================


class CarbonRecordCreate(BaseModel):
    """
    Payload for creating a new carbon record.

    If net_carbon_impact_kgco2e is omitted it is automatically computed
    from the component fields by the model validator.
    """

    job_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Job this record is linked to",
    )
    client_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Client for scoped ESG reporting (denormalised from job if omitted)",
    )
    calculated_at: Optional[datetime] = Field(
        default=None,
        description="Calculation timestamp; defaults to server UTC now if omitted",
    )
    transport_emissions_kgco2e: Optional[Decimal] = Field(
        default=None,
        ge=0,
        description="CO₂e from fleet transport (kgCO₂e)",
    )
    landfill_avoidance_kgco2e: Optional[Decimal] = Field(
        default=None,
        ge=0,
        description="Carbon credit for landfill diversion (kgCO₂e)",
    )
    recycling_credit_kgco2e: Optional[Decimal] = Field(
        default=None,
        ge=0,
        description="Carbon credit for material recycling (kgCO₂e)",
    )
    wte_credit_kgco2e: Optional[Decimal] = Field(
        default=None,
        ge=0,
        description="Carbon credit from waste-to-energy (kgCO₂e)",
    )
    net_carbon_impact_kgco2e: Optional[Decimal] = Field(
        default=None,
        description=(
            "Pre-computed net impact; auto-calculated from components if omitted"
        ),
    )
    methodology_notes: Optional[str] = Field(
        default=None,
        description="Emission factor methodology description",
    )

    model_config = ConfigDict(str_strip_whitespace=True)

    @model_validator(mode="after")
    def compute_net_impact(self) -> "CarbonRecordCreate":
        """Auto-compute net_carbon_impact_kgco2e when not explicitly provided."""
        if (
            self.net_carbon_impact_kgco2e is None
            and self.transport_emissions_kgco2e is not None
        ):
            zero = Decimal("0")
            self.net_carbon_impact_kgco2e = (
                self.transport_emissions_kgco2e
                - (self.landfill_avoidance_kgco2e or zero)
                - (self.recycling_credit_kgco2e or zero)
                - (self.wte_credit_kgco2e or zero)
            )
        return self


class CarbonRecordUpdate(BaseModel):
    """Payload for partial updates to an existing carbon record."""

    transport_emissions_kgco2e: Optional[Decimal] = Field(default=None, ge=0)
    landfill_avoidance_kgco2e: Optional[Decimal] = Field(default=None, ge=0)
    recycling_credit_kgco2e: Optional[Decimal] = Field(default=None, ge=0)
    wte_credit_kgco2e: Optional[Decimal] = Field(default=None, ge=0)
    net_carbon_impact_kgco2e: Optional[Decimal] = None
    methodology_notes: Optional[str] = None

    model_config = ConfigDict(str_strip_whitespace=True)

    @model_validator(mode="after")
    def recompute_net_impact(self) -> "CarbonRecordUpdate":
        """Re-compute net when components are updated but net is not provided."""
        if (
            self.net_carbon_impact_kgco2e is None
            and self.transport_emissions_kgco2e is not None
        ):
            zero = Decimal("0")
            self.net_carbon_impact_kgco2e = (
                self.transport_emissions_kgco2e
                - (self.landfill_avoidance_kgco2e or zero)
                - (self.recycling_credit_kgco2e or zero)
                - (self.wte_credit_kgco2e or zero)
            )
        return self


class CarbonRecordRead(BaseModel):
    """Full carbon record returned to API consumers."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: Optional[uuid.UUID]
    client_id: Optional[uuid.UUID]
    calculated_at: datetime
    transport_emissions_kgco2e: Optional[Decimal]
    landfill_avoidance_kgco2e: Optional[Decimal]
    recycling_credit_kgco2e: Optional[Decimal]
    wte_credit_kgco2e: Optional[Decimal]
    net_carbon_impact_kgco2e: Optional[Decimal]
    methodology_notes: Optional[str]


class CarbonRecordListItem(BaseModel):
    """Lightweight schema for list endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: Optional[uuid.UUID]
    client_id: Optional[uuid.UUID]
    calculated_at: datetime
    transport_emissions_kgco2e: Optional[Decimal]
    net_carbon_impact_kgco2e: Optional[Decimal]


# =============================================================
# ESG Dashboard / Aggregation Response Schemas
# =============================================================


class ESGClientDashboard(BaseModel):
    """
    Full ESG dashboard response for a single client.
    Returned by GET /esg/client/{id}/dashboard.
    """

    client_id: uuid.UUID
    period_from: str = Field(description="ISO date string for the start of the period")
    period_to: str = Field(description="ISO date string for the end of the period")

    # ── Headline KPIs ─────────────────────────────────────────
    total_co2_saved_kgco2e: Decimal = Field(
        description="Total net carbon benefit (negative = benefit)"
    )
    total_transport_emissions_kgco2e: Decimal
    total_landfill_avoidance_kgco2e: Decimal
    total_recycling_credit_kgco2e: Decimal
    total_wte_credit_kgco2e: Decimal

    # ── Diversion & recycling rates ──────────────────────────
    diversion_rate_pct: Optional[Decimal] = Field(
        default=None,
        description="(diverted waste / total waste) × 100",
    )
    recycling_rate_pct: Optional[Decimal] = Field(
        default=None,
        description="(recyclable kg / total waste kg) × 100",
    )

    # ── Trend vs previous period ─────────────────────────────
    co2_trend_pct: Optional[Decimal] = Field(
        default=None,
        description=(
            "Percentage change in net carbon impact vs the equivalent previous period. "
            "Negative = improvement."
        ),
    )

    # ── Time series ──────────────────────────────────────────
    diversion_rate_history: list = Field(
        default_factory=list,
        description="Monthly diversion rate data points [{period, rate_pct}, ...]",
    )
    recycling_breakdown: list = Field(
        default_factory=list,
        description="Per-material recycling totals [{material, total_kg}, ...]",
    )

    # ── SDG alignment tags ───────────────────────────────────
    sdg_tags: list = Field(
        default_factory=list,
        description=(
            "Applicable UN Sustainable Development Goals, "
            "e.g. ['SDG 12', 'SDG 13', 'SDG 15']"
        ),
    )


class ESGCompanyDashboard(BaseModel):
    """
    Company-wide aggregate ESG performance.
    Returned by GET /esg/company/dashboard.
    """

    period_from: str
    period_to: str

    total_waste_processed_kg: Decimal
    total_co2_saved_kgco2e: Decimal
    total_transport_emissions_kgco2e: Decimal
    total_landfill_avoidance_kgco2e: Decimal
    total_recycling_credit_kgco2e: Decimal
    total_wte_credit_kgco2e: Decimal

    overall_diversion_rate_pct: Optional[Decimal] = None
    overall_recycling_rate_pct: Optional[Decimal] = None

    # Top clients by carbon impact
    top_clients_by_co2_saved: list = Field(
        default_factory=list,
        description="[{client_id, company_name, co2_saved_kgco2e}, ...] sorted desc",
    )

    # Monthly trend
    monthly_co2_trend: list = Field(
        default_factory=list,
        description="[{period, net_kgco2e, transport_kgco2e, savings_kgco2e}, ...]",
    )

    sdg_tags: list = Field(
        default_factory=list,
        description="Company-level SDG alignment tags",
    )


class ESGReportGenerateRequest(BaseModel):
    """Request body for POST /esg/reports/generate."""

    client_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Client scope; if None, generates a company-wide report",
    )
    period_from: str = Field(
        description="ISO date string (YYYY-MM-DD) for report period start"
    )
    period_to: str = Field(
        description="ISO date string (YYYY-MM-DD) for report period end"
    )
    report_title: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Custom report title; auto-generated if omitted",
    )
    include_sections: Optional[list] = Field(
        default=None,
        description=(
            "Optional list of sections to include. "
            "Defaults to all: ['summary', 'carbon', 'diversion', "
            "'recycling', 'compliance', 'sdg']"
        ),
    )

    model_config = ConfigDict(str_strip_whitespace=True)


class ESGReportStatusResponse(BaseModel):
    """Response for report generation status queries."""

    task_id: str
    status: str = Field(description="pending | running | success | failure")
    pdf_url: Optional[str] = Field(
        default=None,
        description="Download URL once the report is ready",
    )
    message: Optional[str] = None
