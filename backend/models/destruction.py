# =============================================================
# Hi-Tech Waste Management — Destruction Job Model
# SQLAlchemy async ORM model + Pydantic v2 schemas
# =============================================================

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from models.job import Job
    from models.user import User

from database import Base
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

# =============================================================
# SQLAlchemy ORM Model
# =============================================================


class DestructionJob(Base):
    """
    Records a witnessed destruction job for goods/assets requiring
    certified destruction (e.g. confidential documents, defective products,
    counterfeit goods, expired pharmaceuticals).

    Supports dual sign-off by a Hi-Tech witness and a client representative,
    and optional media evidence (photos/video hashes stored in media_files JSON).

    destruction_method choices:
        shredding | incineration | landfill_compaction

    reason_codes is stored as JSON array of strings (e.g. ["EXPIRED", "DEFECTIVE"]).
    """

    __tablename__ = "destruction_jobs"

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
        comment="Parent job record that this destruction event is linked to",
    )

    # ── Goods details ─────────────────────────────────────────
    goods_description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Full description of the goods/materials being destroyed",
    )
    quantity_units: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Number of units (cartons, pallets, pieces, etc.)",
    )
    weight_kg: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 3),
        nullable=True,
        comment="Total weight of goods in kilograms",
    )

    # ── Destruction method & logistics ───────────────────────
    destruction_method: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="shredding",
        comment="shredding | incineration | landfill_compaction",
    )
    destruction_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        index=True,
    )
    destruction_location: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Physical address / facility where destruction took place",
    )

    # ── Witness information ───────────────────────────────────
    witness_hitech_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Hi-Tech staff member who witnessed the destruction",
    )
    witness_client_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Full name of the client representative witness",
    )
    witness_client_designation: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Job title / designation of the client representative",
    )

    # ── Evidence & certification ──────────────────────────────
    # Stores an array of objects, e.g.:
    # [{"type": "photo", "path": "s3://...", "hash": "sha256:..."}, ...]
    media_files: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Array of media evidence objects (photos, video references)",
    )
    certificate_issued: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="True once a Certificate of Destruction has been generated",
    )
    certificate_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="FK-like reference to certificates.id (soft reference)",
    )

    # ── Classification ────────────────────────────────────────
    # JSON array for reason codes, e.g.
    # ["EXPIRED", "DEFECTIVE", "CONFIDENTIAL", "COUNTERFEIT"]
    reason_codes: Mapped[Optional[List[str]]] = mapped_column(
        JSON,
        nullable=True,
        default=list,
        comment="Array of reason codes for destruction (stored as JSON)",
    )

    # ── Audit ─────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # ── Relationships ─────────────────────────────────────────
    job: Mapped[Optional["Job"]] = relationship(
        "Job",
        foreign_keys=[job_id],
        lazy="selectin",
    )
    witness_hitech: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[witness_hitech_id],
        lazy="selectin",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<DestructionJob id={self.id} method={self.destruction_method} "
            f"date={self.destruction_date} cert_issued={self.certificate_issued}>"
        )


# =============================================================
# Valid value sets
# =============================================================

DESTRUCTION_METHODS = {"shredding", "incineration", "landfill_compaction"}

COMMON_REASON_CODES = [
    "EXPIRED",
    "DEFECTIVE",
    "COUNTERFEIT",
    "CONFIDENTIAL",
    "RECALLED",
    "DAMAGED",
    "NON_COMPLIANT",
    "OBSOLETE",
    "OVERSTOCK",
    "CONTAMINATED",
]


# =============================================================
# Pydantic Schemas
# =============================================================


class DestructionJobCreate(BaseModel):
    """Payload for creating a new destruction job record."""

    job_id: Optional[uuid.UUID] = None
    goods_description: str = Field(
        ...,
        min_length=5,
        description="Description of goods/materials being destroyed",
    )
    quantity_units: Optional[int] = Field(
        None,
        ge=1,
        description="Number of physical units (cartons, pieces, pallets)",
    )
    weight_kg: Optional[Decimal] = Field(
        None,
        ge=0,
        description="Total weight of goods in kg",
    )
    destruction_method: str = Field(
        default="shredding",
        description="shredding | incineration | landfill_compaction",
    )
    destruction_date: Optional[date] = None
    destruction_location: Optional[str] = None
    witness_hitech_id: Optional[uuid.UUID] = None
    witness_client_name: Optional[str] = Field(None, max_length=255)
    witness_client_designation: Optional[str] = Field(None, max_length=255)
    media_files: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description=(
            "List of media evidence objects. "
            "Each item should have 'type', 'path', and optionally 'hash'."
        ),
    )
    reason_codes: Optional[List[str]] = Field(
        default=None,
        description=f"Reason codes. Common values: {COMMON_REASON_CODES}",
    )

    model_config = ConfigDict(str_strip_whitespace=True)

    @model_validator(mode="after")
    def validate_method(self) -> "DestructionJobCreate":
        if self.destruction_method not in DESTRUCTION_METHODS:
            raise ValueError(
                f"destruction_method must be one of {sorted(DESTRUCTION_METHODS)}"
            )
        return self


class DestructionJobUpdate(BaseModel):
    """Payload for partial updates to a destruction job."""

    goods_description: Optional[str] = Field(None, min_length=5)
    quantity_units: Optional[int] = Field(None, ge=1)
    weight_kg: Optional[Decimal] = Field(None, ge=0)
    destruction_method: Optional[str] = None
    destruction_date: Optional[date] = None
    destruction_location: Optional[str] = None
    witness_hitech_id: Optional[uuid.UUID] = None
    witness_client_name: Optional[str] = Field(None, max_length=255)
    witness_client_designation: Optional[str] = Field(None, max_length=255)
    media_files: Optional[List[Dict[str, Any]]] = None
    reason_codes: Optional[List[str]] = None
    certificate_issued: Optional[bool] = None
    certificate_id: Optional[uuid.UUID] = None

    model_config = ConfigDict(str_strip_whitespace=True)

    @model_validator(mode="after")
    def validate_method(self) -> "DestructionJobUpdate":
        if (
            self.destruction_method is not None
            and self.destruction_method not in DESTRUCTION_METHODS
        ):
            raise ValueError(
                f"destruction_method must be one of {sorted(DESTRUCTION_METHODS)}"
            )
        return self


class DestructionJobRead(BaseModel):
    """Full schema returned to API consumers."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: Optional[uuid.UUID]
    goods_description: str
    quantity_units: Optional[int]
    weight_kg: Optional[Decimal]
    destruction_method: str
    destruction_date: Optional[date]
    destruction_location: Optional[str]
    witness_hitech_id: Optional[uuid.UUID]
    witness_client_name: Optional[str]
    witness_client_designation: Optional[str]
    media_files: Optional[List[Dict[str, Any]]]
    certificate_issued: bool
    certificate_id: Optional[uuid.UUID]
    reason_codes: Optional[List[str]]
    created_at: datetime
    updated_at: datetime


class DestructionJobListItem(BaseModel):
    """Lightweight schema for list endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: Optional[uuid.UUID]
    goods_description: str
    weight_kg: Optional[Decimal]
    destruction_method: str
    destruction_date: Optional[date]
    certificate_issued: bool
    witness_client_name: Optional[str]
    created_at: datetime


class DestructionSignOffRequest(BaseModel):
    """
    Dual sign-off payload.
    Used by POST /destruction/jobs/{id}/sign to record witness acknowledgement.
    Both Hi-Tech witness (by user ID) and client representative (by name/designation)
    must be captured before a Certificate of Destruction can be generated.
    """

    witness_hitech_id: uuid.UUID = Field(
        ...,
        description="UUID of the Hi-Tech staff member signing off",
    )
    witness_client_name: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="Full name of the client representative",
    )
    witness_client_designation: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="Job title / designation of the client representative",
    )
    destruction_date: date = Field(
        ...,
        description="Confirmed date on which destruction was carried out",
    )
    destruction_location: str = Field(
        ...,
        min_length=5,
        description="Physical address / facility where destruction took place",
    )
    notes: Optional[str] = Field(
        None,
        description="Any additional notes about the sign-off",
    )

    model_config = ConfigDict(str_strip_whitespace=True)


class CertificateGenerationResponse(BaseModel):
    """Response returned after triggering certificate generation."""

    destruction_job_id: uuid.UUID
    certificate_id: uuid.UUID
    pdf_url: Optional[str] = Field(
        None,
        description="URL to download the generated PDF; null if still generating",
    )
    status: str = Field(
        description="immediate | queued",
        examples=["queued"],
    )
    message: str
