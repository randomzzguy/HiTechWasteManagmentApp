# =============================================================
# Hi-Tech Waste Management — Invoice Model
# SQLAlchemy 2.0 async ORM + Pydantic v2 schemas
# =============================================================

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from models.client import Client
    from models.user import User

from database import Base
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import (
    Boolean,
    Date,
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
# Valid value sets
# =============================================================

INVOICE_STATUSES = {"unpaid", "partial", "paid", "overdue"}


# =============================================================
# SQLAlchemy ORM Model
# =============================================================


class Invoice(Base):
    """
    Represents a client invoice generated from one or more completed jobs.

    Billing model summary:
        - line_items   : JSON array of itemised charges
        - subtotal_myr : sum of line items before tax
        - tax_myr      : SST / GST component
        - total_myr    : subtotal + tax
        - paid_amount_myr : cumulative payments received

    status transitions:
        unpaid → partial → paid
        unpaid / partial → overdue (time-based, updated by scheduler)

    job_ids is stored as a PostgreSQL ARRAY of UUIDs so a single
    invoice can bundle multiple completed jobs for a client.

    line_items JSON structure (array of objects):
    [
        {
            "description": "General Waste Collection — 3 trips",
            "quantity":    3,
            "unit":        "trip",
            "unit_price":  350.00,
            "amount":      1050.00,
            "job_id":      "uuid-string"   // optional reference
        },
        ...
    ]
    """

    __tablename__ = "invoices"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
        index=True,
    )
    invoice_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="Human-readable invoice number, e.g. INV-2024-00123",
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Array of job UUIDs bundled in this invoice (stored as JSON for cross-DB compatibility)
    job_ids: Mapped[Optional[List[uuid.UUID]]] = mapped_column(
        JSON,
        nullable=True,
        default=list,
        comment="UUIDs of jobs included in this invoice (as JSON array of strings)",
    )

    # ── Billing dates ─────────────────────────────────────────
    issue_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).date(),
        comment="Date the invoice was issued to the client",
    )
    due_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        index=True,
        comment="Payment due date; overdue check compares this to today",
    )

    # ── Line items & amounts ──────────────────────────────────
    line_items: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Itemised charges array — see class docstring for structure",
    )
    subtotal_myr: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Sum of all line item amounts before tax (MYR)",
    )
    tax_myr: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Tax component (SST 6% or 0%) in MYR",
    )
    total_myr: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="subtotal_myr + tax_myr; authoritative invoice total in MYR",
    )

    # ── Payment tracking ──────────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="unpaid",
        index=True,
        comment="unpaid | partial | paid | overdue",
    )
    paid_amount_myr: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Cumulative amount received against this invoice in MYR",
    )

    # ── Misc ──────────────────────────────────────────────────
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Internal or client-facing notes printed on the invoice",
    )
    pdf_path: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Filesystem or object-store path to the generated PDF",
    )
    is_void: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="Soft-delete / void flag — voided invoices are excluded from reports",
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
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who generated / raised the invoice",
    )

    # ── Relationships ─────────────────────────────────────────
    client: Mapped["Client"] = relationship(
        "Client",
        foreign_keys=[client_id],
        lazy="selectin",
    )
    creator: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[created_by],
        lazy="selectin",
    )

    # ── Python-level computed properties ──────────────────────

    @property
    def outstanding_myr(self) -> Decimal:
        """Amount still owed: total_myr - paid_amount_myr."""
        return self.total_myr - self.paid_amount_myr

    @property
    def is_overdue(self) -> bool:
        """True when due_date has passed and the invoice is not fully paid."""
        if self.due_date is None:
            return False
        return self.due_date < datetime.now(
            timezone.utc
        ).date() and self.status not in {"paid"}

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Invoice id={self.id} number={self.invoice_number!r} "
            f"client_id={self.client_id} status={self.status} "
            f"total={self.total_myr}>"
        )


# =============================================================
# Pydantic Schemas — Line Item
# =============================================================


class InvoiceLineItem(BaseModel):
    """
    Represents a single line item on an invoice.
    Stored as a JSON array in the line_items column.
    """

    description: str = Field(
        ...,
        min_length=1,
        max_length=500,
        examples=["General Waste Collection — 3 trips"],
    )
    quantity: Decimal = Field(..., gt=0, examples=[3])
    unit: Optional[str] = Field(
        None,
        max_length=50,
        examples=["trip", "kg", "month", "unit"],
    )
    unit_price: Decimal = Field(..., ge=0, examples=[350.00])
    amount: Optional[Decimal] = Field(
        default=None,
        ge=0,
        description="quantity × unit_price; auto-computed if omitted",
    )
    job_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Optional reference to the job this line item relates to",
    )
    notes: Optional[str] = Field(default=None, max_length=255)

    model_config = ConfigDict(str_strip_whitespace=True)

    @model_validator(mode="after")
    def compute_amount(self) -> "InvoiceLineItem":
        if self.amount is None:
            self.amount = self.quantity * self.unit_price
        return self

    def to_dict(self) -> Dict[str, Any]:
        return {
            "description": self.description,
            "quantity": float(self.quantity),
            "unit": self.unit,
            "unit_price": float(self.unit_price),
            "amount": float(self.amount) if self.amount is not None else None,
            "job_id": str(self.job_id) if self.job_id else None,
            "notes": self.notes,
        }


# =============================================================
# Pydantic Schemas — Invoice CRUD
# =============================================================


class InvoiceCreate(BaseModel):
    """Payload for creating a new invoice."""

    client_id: uuid.UUID
    job_ids: Optional[List[uuid.UUID]] = Field(
        default=None,
        description="Jobs to bundle into this invoice",
    )
    issue_date: Optional[date] = Field(
        default=None,
        description="Invoice date; defaults to today if omitted",
    )
    due_date: Optional[date] = Field(
        default=None,
        description="Payment due date; typically issue_date + 30 days",
    )
    line_items: Optional[List[InvoiceLineItem]] = Field(
        default=None,
        description="Itemised charges",
    )
    # If subtotal/tax/total are not provided, they are computed from line_items
    subtotal_myr: Optional[Decimal] = Field(default=None, ge=0)
    tax_myr: Optional[Decimal] = Field(default=None, ge=0)
    total_myr: Optional[Decimal] = Field(default=None, ge=0)
    notes: Optional[str] = None

    model_config = ConfigDict(str_strip_whitespace=True)

    @model_validator(mode="after")
    def compute_totals(self) -> "InvoiceCreate":
        """Auto-compute subtotal and total from line items when not provided."""
        if self.line_items:
            computed_subtotal = Decimal("0") + sum(
                (item.amount or Decimal("0")) for item in self.line_items
            )
            if self.subtotal_myr is None:
                self.subtotal_myr = computed_subtotal
        if self.subtotal_myr is not None and self.total_myr is None:
            tax = self.tax_myr or Decimal("0")
            self.total_myr = Decimal(str(self.subtotal_myr)) + Decimal(str(tax))
        return self


class InvoiceUpdate(BaseModel):
    """Payload for partial updates to an invoice."""

    job_ids: Optional[List[uuid.UUID]] = None
    issue_date: Optional[date] = None
    due_date: Optional[date] = None
    line_items: Optional[List[InvoiceLineItem]] = None
    subtotal_myr: Optional[Decimal] = Field(None, ge=0)
    tax_myr: Optional[Decimal] = Field(None, ge=0)
    total_myr: Optional[Decimal] = Field(None, ge=0)
    notes: Optional[str] = None
    is_void: Optional[bool] = None

    model_config = ConfigDict(str_strip_whitespace=True)


class PaymentRecord(BaseModel):
    """
    Payload for PATCH /invoices/{id}/payment — records a payment
    against an invoice and updates the status automatically.
    """

    amount_myr: Decimal = Field(
        ...,
        gt=0,
        description="Payment amount received in Malaysian Ringgit",
    )
    payment_date: Optional[date] = Field(
        default=None,
        description="Date payment was received; defaults to today",
    )
    payment_reference: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Bank transfer reference, cheque number, receipt number, etc.",
    )
    payment_method: Optional[str] = Field(
        default=None,
        max_length=50,
        description="e.g. bank_transfer, cheque, cash, online",
    )
    notes: Optional[str] = Field(default=None, max_length=500)

    model_config = ConfigDict(str_strip_whitespace=True)


class InvoiceRead(BaseModel):
    """Full invoice representation returned to API consumers."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    invoice_number: str
    client_id: uuid.UUID
    job_ids: Optional[List[uuid.UUID]]
    issue_date: date
    due_date: Optional[date]
    line_items: Optional[List[Dict[str, Any]]]
    subtotal_myr: Decimal
    tax_myr: Decimal
    total_myr: Decimal
    status: str
    paid_amount_myr: Decimal
    outstanding_myr: Optional[Decimal] = None  # populated from property
    notes: Optional[str]
    pdf_path: Optional[str]
    is_void: bool
    created_at: datetime
    updated_at: datetime
    created_by: Optional[uuid.UUID]

    @classmethod
    def from_orm_with_computed(cls, obj: Invoice) -> "InvoiceRead":
        return cls(
            id=obj.id,
            invoice_number=obj.invoice_number,
            client_id=obj.client_id,
            job_ids=obj.job_ids,
            issue_date=obj.issue_date,
            due_date=obj.due_date,
            line_items=obj.line_items,
            subtotal_myr=obj.subtotal_myr,
            tax_myr=obj.tax_myr,
            total_myr=obj.total_myr,
            status=obj.status,
            paid_amount_myr=obj.paid_amount_myr,
            outstanding_myr=obj.outstanding_myr,
            notes=obj.notes,
            pdf_path=obj.pdf_path,
            is_void=obj.is_void,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
            created_by=obj.created_by,
        )


class InvoiceListItem(BaseModel):
    """Lightweight invoice schema for list endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    invoice_number: str
    client_id: uuid.UUID
    issue_date: date
    due_date: Optional[date]
    total_myr: Decimal
    paid_amount_myr: Decimal
    status: str
    is_void: bool
    created_at: datetime


# =============================================================
# Finance Stats / Aggregation Response Schemas
# =============================================================


class RevenueByMonth(BaseModel):
    """Monthly revenue data point."""

    year: int
    month: int
    period_label: str = Field(description="e.g. '2024-06'")
    invoiced_myr: Decimal
    collected_myr: Decimal
    outstanding_myr: Decimal
    invoice_count: int


class RevenueByServiceType(BaseModel):
    """Revenue breakdown by job/service type."""

    service_type: str
    invoiced_myr: Decimal
    invoice_count: int


class RevenueByClient(BaseModel):
    """Revenue breakdown per client."""

    client_id: uuid.UUID
    company_name: str
    invoiced_myr: Decimal
    collected_myr: Decimal
    outstanding_myr: Decimal


class AgeingBracket(BaseModel):
    """
    Accounts-receivable ageing bucket.
    Brackets: current (not yet due), 1-30, 31-60, 61-90, 90+ days overdue.
    """

    bracket: str = Field(examples=["1-30 days", "31-60 days", "90+ days", "current"])
    invoice_count: int
    outstanding_myr: Decimal


class RevenueStatsResponse(BaseModel):
    """
    Comprehensive response for GET /finance/stats/revenue.
    Aggregates revenue by time, service type, and client,
    plus a full accounts-receivable ageing schedule.
    """

    period_from: Optional[str] = None
    period_to: Optional[str] = None
    total_invoiced_myr: Decimal
    total_collected_myr: Decimal
    total_outstanding_myr: Decimal
    by_month: List[RevenueByMonth] = Field(default_factory=list)
    by_service_type: List[RevenueByServiceType] = Field(default_factory=list)
    by_client: List[RevenueByClient] = Field(default_factory=list)
    ageing_schedule: List[AgeingBracket] = Field(default_factory=list)
