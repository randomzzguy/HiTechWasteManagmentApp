# =============================================================
# Hi-Tech Waste Management — Finance Router
# Invoices, payment recording, and revenue statistics
# =============================================================

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from config import get_settings
from database import get_db
from fastapi import APIRouter, Depends, HTTPException, Query, status
from models.invoice import (
    INVOICE_STATUSES,
    AgeingBracket,
    Invoice,
    InvoiceCreate,
    InvoiceListItem,
    InvoiceRead,
    InvoiceUpdate,
    PaymentRecord,
    RevenueByClient,
    RevenueByMonth,
    RevenueByServiceType,
    RevenueStatsResponse,
)
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from routers.auth import get_current_user, require_roles

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()

# =============================================================
# Role constants
# =============================================================

MANAGEMENT_ROLES = ["superadmin", "management", "operations_manager"]
FINANCE_ROLES = ["superadmin", "management"]
ALL_STAFF = [
    "superadmin",
    "management",
    "operations_manager",
    "field_supervisor",
    "compliance_officer",
]


# =============================================================
# Helpers
# =============================================================


async def _get_invoice_or_404(invoice_id: uuid.UUID, db: AsyncSession) -> Invoice:
    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    invoice = result.scalar_one_or_none()
    if invoice is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice {invoice_id} not found",
        )
    return invoice


async def _generate_invoice_number(db: AsyncSession) -> str:
    """
    Generates a sequential invoice number in the format INV-YYYY-NNNNN.
    Uses a count query to determine the next sequence number.
    """
    year = datetime.now(timezone.utc).year
    result = await db.execute(
        select(func.count())
        .select_from(Invoice)
        .where(Invoice.invoice_number.like(f"INV-{year}-%"))
    )
    count = result.scalar_one() or 0
    return f"INV-{year}-{count + 1:05d}"


def _determine_invoice_status(
    total_myr: Decimal,
    paid_amount_myr: Decimal,
    due_date: Optional[date],
) -> str:
    """
    Determines invoice status based on payment amounts and due date.

    Rules:
    - paid in full → 'paid'
    - partial payment received → 'partial'
    - due date has passed and not fully paid → 'overdue'
    - otherwise → 'unpaid'
    """
    today = date.today()

    if paid_amount_myr >= total_myr:
        return "paid"
    if paid_amount_myr > 0:
        if due_date and due_date < today:
            return "overdue"
        return "partial"
    if due_date and due_date < today:
        return "overdue"
    return "unpaid"


# =============================================================
# GET /invoices — list invoices
# =============================================================


@router.get(
    "/invoices",
    response_model=Dict[str, Any],
    summary="List invoices",
    description=(
        "Returns a paginated list of invoices. "
        "Filter by status (unpaid | partial | paid | overdue), "
        "client_id, date range, and void status."
    ),
)
async def list_invoices(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    status_filter: Optional[str] = Query(
        default=None,
        alias="status",
        description="unpaid | partial | paid | overdue",
    ),
    client_id: Optional[uuid.UUID] = Query(
        default=None, description="Filter by client UUID"
    ),
    date_from: Optional[date] = Query(
        default=None, description="Filter by issue_date on or after this date"
    ),
    date_to: Optional[date] = Query(
        default=None, description="Filter by issue_date on or before this date"
    ),
    include_void: bool = Query(
        default=False, description="Include voided invoices (default: False)"
    ),
    search: Optional[str] = Query(
        default=None, description="Partial match on invoice_number or notes"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    """List invoices with optional filters and pagination."""

    if status_filter and status_filter not in INVOICE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid status. Must be one of: {sorted(INVOICE_STATUSES)}",
        )

    filters: list = []

    # Client portal users see only their own invoices
    if current_user.get("role") == "client":
        from models.client import Client as ClientModel

        client_result = await db.execute(
            select(ClientModel).where(
                ClientModel.portal_user_id == uuid.UUID(current_user["sub"])
            )
        )
        client_obj = client_result.scalar_one_or_none()
        if client_obj is None:
            return {"items": [], "total": 0, "skip": skip, "limit": limit}
        filters.append(Invoice.client_id == client_obj.id)
    elif client_id is not None:
        filters.append(Invoice.client_id == client_id)

    if status_filter:
        filters.append(Invoice.status == status_filter)
    if date_from:
        filters.append(Invoice.issue_date >= date_from)
    if date_to:
        filters.append(Invoice.issue_date <= date_to)
    if not include_void:
        filters.append(Invoice.is_void == False)  # noqa: E712
    if search:
        like = f"%{search}%"
        filters.append(
            or_(
                Invoice.invoice_number.ilike(like),
                Invoice.notes.ilike(like),
            )
        )

    base_stmt = select(Invoice)
    if filters:
        base_stmt = base_stmt.where(and_(*filters))

    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total_result = await db.execute(count_stmt)
    total: int = total_result.scalar_one()

    stmt = (
        base_stmt.order_by(Invoice.issue_date.desc(), Invoice.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    invoices = result.scalars().all()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": [InvoiceListItem.model_validate(inv) for inv in invoices],
    }


# =============================================================
# POST /invoices — create invoice
# =============================================================


@router.post(
    "/invoices",
    response_model=InvoiceRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create an invoice",
    description=(
        "Creates a new invoice from one or more completed jobs. "
        "Subtotal, tax, and total are auto-computed from line_items if not provided. "
        "Due date defaults to issue_date + 30 days."
    ),
    dependencies=[Depends(require_roles(*MANAGEMENT_ROLES))],
)
async def create_invoice(
    payload: InvoiceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> InvoiceRead:
    """
    Creates a new client invoice.

    - Validates the client exists.
    - Validates all referenced job_ids exist and belong to the client.
    - Auto-generates a sequential invoice_number in the format INV-YYYY-NNNNN.
    - Subtotal and total are computed from line_items if not explicitly provided.
    - Default due_date = issue_date + 30 days.
    """
    from models.client import Client as ClientModel
    from models.job import Job

    # Validate client exists
    client_result = await db.execute(
        select(ClientModel).where(ClientModel.id == payload.client_id)
    )
    if client_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client {payload.client_id} not found",
        )

    # Validate job_ids if provided
    if payload.job_ids:
        for job_id in payload.job_ids:
            job_result = await db.execute(select(Job).where(Job.id == job_id))
            job = job_result.scalar_one_or_none()
            if job is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Job {job_id} not found",
                )
            if job.client_id != payload.client_id:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"Job {job_id} does not belong to client {payload.client_id}. "
                        "All bundled jobs must belong to the same client."
                    ),
                )

    # Generate unique invoice number with collision guard
    invoice_number: Optional[str] = None
    for attempt in range(5):
        candidate = await _generate_invoice_number(db)
        existing = await db.execute(
            select(Invoice.id).where(Invoice.invoice_number == candidate)
        )
        if existing.scalar_one_or_none() is None:
            invoice_number = candidate
            break

    if invoice_number is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not generate a unique invoice number. Please retry.",
        )

    # Resolve dates
    issue_date = payload.issue_date or datetime.now(timezone.utc).date()
    due_date = payload.due_date or (issue_date + timedelta(days=30))

    # Compute totals
    subtotal_myr = payload.subtotal_myr or Decimal("0.00")
    tax_myr = payload.tax_myr or Decimal("0.00")
    total_myr = payload.total_myr or (subtotal_myr + tax_myr)

    # Serialise line items to plain dicts for JSON storage
    line_items_data: Optional[List[Dict[str, Any]]] = None
    if payload.line_items:
        line_items_data = [item.to_dict() for item in payload.line_items]

    # Convert UUIDs to strings for JSON serialization
    job_ids_json = [str(jid) for jid in payload.job_ids] if payload.job_ids else None
    
    invoice = Invoice(
        id=uuid.uuid4(),
        invoice_number=invoice_number,
        client_id=payload.client_id,
        job_ids=job_ids_json,
        issue_date=issue_date,
        due_date=due_date,
        line_items=line_items_data,
        subtotal_myr=subtotal_myr,
        tax_myr=tax_myr,
        total_myr=total_myr,
        status="unpaid",
        paid_amount_myr=Decimal("0.00"),
        notes=payload.notes,
        is_void=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        created_by=uuid.UUID(current_user["sub"]),
    )
    db.add(invoice)
    await db.flush()
    await db.refresh(invoice)

    logger.info(
        "Invoice %s created for client %s by user %s",
        invoice.invoice_number,
        payload.client_id,
        current_user["sub"],
    )
    return InvoiceRead.from_orm_with_computed(invoice)


# =============================================================
# GET /invoices/{id} — invoice detail
# =============================================================


@router.get(
    "/invoices/{invoice_id}",
    response_model=InvoiceRead,
    summary="Get invoice detail",
)
async def get_invoice(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> InvoiceRead:
    """Returns full details of a single invoice including outstanding balance."""
    invoice = await _get_invoice_or_404(invoice_id, db)

    # Client portal access control
    if current_user.get("role") == "client":
        from models.client import Client as ClientModel

        client_result = await db.execute(
            select(ClientModel).where(
                ClientModel.portal_user_id == uuid.UUID(current_user["sub"])
            )
        )
        client_obj = client_result.scalar_one_or_none()
        if client_obj is None or client_obj.id != invoice.client_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this invoice",
            )

    return InvoiceRead.from_orm_with_computed(invoice)


# =============================================================
# PUT /invoices/{id} — update invoice
# =============================================================


@router.put(
    "/invoices/{invoice_id}",
    response_model=InvoiceRead,
    summary="Update an invoice",
    dependencies=[Depends(require_roles(*MANAGEMENT_ROLES))],
)
async def update_invoice(
    invoice_id: uuid.UUID,
    payload: InvoiceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> InvoiceRead:
    """
    Partially updates an invoice.

    Restrictions:
    - Paid invoices cannot be modified (void first).
    - Voided invoices cannot be modified.
    """
    invoice = await _get_invoice_or_404(invoice_id, db)

    if invoice.is_void:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Voided invoices cannot be modified",
        )
    if invoice.status == "paid" and current_user.get("role") not in {
        "superadmin",
        "management",
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Paid invoices can only be modified by management or superadmin",
        )

    update_data = payload.model_dump(exclude_unset=True)

    # Serialise updated line items if provided
    if "line_items" in update_data and update_data["line_items"] is not None:
        update_data["line_items"] = [
            item.to_dict() for item in update_data["line_items"]
        ]

    for field, value in update_data.items():
        setattr(invoice, field, value)

    invoice.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(invoice)

    logger.info(
        "Invoice %s updated by user %s",
        invoice.invoice_number,
        current_user["sub"],
    )
    return InvoiceRead.from_orm_with_computed(invoice)


# =============================================================
# PATCH /invoices/{id}/payment — record a payment
# =============================================================


@router.patch(
    "/invoices/{invoice_id}/payment",
    response_model=InvoiceRead,
    summary="Record a payment against an invoice",
    description=(
        "Records a payment received against an invoice. "
        "Updates the paid_amount_myr and automatically transitions the status: "
        "unpaid/partial → partial (if still outstanding) → paid (when fully settled). "
        "Overpayment is not allowed."
    ),
    dependencies=[Depends(require_roles(*MANAGEMENT_ROLES, "compliance_officer"))],
)
async def record_payment(
    invoice_id: uuid.UUID,
    payload: PaymentRecord,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> InvoiceRead:
    """
    Records a payment receipt against an invoice.

    Business rules:
    - Voided invoices cannot receive payments.
    - The total paid amount cannot exceed the invoice total_myr.
    - Status is automatically updated:
      - New paid_amount >= total_myr → 'paid'
      - New paid_amount > 0 but < total_myr → 'partial'
    - Payment metadata (date, reference, method) is appended to the invoice notes.
    """
    invoice = await _get_invoice_or_404(invoice_id, db)

    if invoice.is_void:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot record payment against a voided invoice",
        )
    if invoice.status == "paid":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Invoice is already fully paid",
        )

    # Validate payment amount does not exceed outstanding balance
    outstanding = invoice.total_myr - invoice.paid_amount_myr
    if payload.amount_myr > outstanding:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Payment amount {payload.amount_myr} MYR exceeds outstanding balance "
                f"{outstanding} MYR. Overpayment is not allowed."
            ),
        )

    # Apply payment
    new_paid_total = invoice.paid_amount_myr + payload.amount_myr

    # Determine new status
    new_status = _determine_invoice_status(
        invoice.total_myr, new_paid_total, invoice.due_date
    )

    # Append payment audit trail to notes
    payment_date = payload.payment_date or date.today()
    payment_note = (
        f"\n[Payment {payment_date.isoformat()}] MYR {payload.amount_myr:.2f}"
    )
    if payload.payment_reference:
        payment_note += f" | Ref: {payload.payment_reference}"
    if payload.payment_method:
        payment_note += f" | Method: {payload.payment_method}"
    if payload.notes:
        payment_note += f" | Note: {payload.notes}"
    payment_note += f" | Recorded by: {current_user['sub']}"

    invoice.paid_amount_myr = new_paid_total
    invoice.status = new_status
    invoice.notes = (invoice.notes or "") + payment_note
    invoice.updated_at = datetime.now(timezone.utc)

    await db.flush()
    await db.refresh(invoice)

    logger.info(
        "Payment of MYR %.2f recorded on invoice %s (new status: %s) by user %s",
        float(payload.amount_myr),
        invoice.invoice_number,
        new_status,
        current_user["sub"],
    )
    return InvoiceRead.from_orm_with_computed(invoice)


# =============================================================
# DELETE /invoices/{id} — void invoice
# =============================================================


@router.delete(
    "/invoices/{invoice_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Void an invoice (soft-delete)",
    dependencies=[Depends(require_roles(*FINANCE_ROLES))],
)
async def void_invoice(
    invoice_id: uuid.UUID,
    reason: str = Query(
        ..., min_length=5, description="Reason for voiding the invoice"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> None:
    """
    Soft-deletes an invoice by setting is_void=True.

    Voided invoices:
    - Are excluded from revenue reports and ageing schedules.
    - Cannot receive further payments or modifications.
    - Are retained in the database for audit purposes.
    """
    invoice = await _get_invoice_or_404(invoice_id, db)

    if invoice.is_void:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Invoice is already voided",
        )
    if invoice.status == "paid":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Cannot void a fully paid invoice. "
                "Issue a credit note or contact finance management."
            ),
        )

    invoice.is_void = True
    invoice.status = "unpaid"  # reset to reflect the void
    void_note = (
        f"\n[VOIDED {datetime.now(timezone.utc).isoformat()}] "
        f"Reason: {reason} | By: {current_user['sub']}"
    )
    invoice.notes = (invoice.notes or "") + void_note
    invoice.updated_at = datetime.now(timezone.utc)

    await db.flush()
    logger.warning(
        "Invoice %s VOIDED | reason=%s | by user=%s",
        invoice.invoice_number,
        reason,
        current_user["sub"],
    )


# =============================================================
# GET /stats/revenue — comprehensive revenue statistics
# =============================================================


@router.get(
    "/stats/revenue",
    response_model=RevenueStatsResponse,
    summary="Revenue statistics and AR ageing",
    description=(
        "Returns comprehensive revenue analytics: "
        "monthly revenue, revenue by service type, by client, "
        "and accounts-receivable ageing schedule."
    ),
)
async def revenue_stats(
    date_from: Optional[date] = Query(
        default=None,
        description="Start of reporting period (by issue_date, inclusive)",
    ),
    date_to: Optional[date] = Query(
        default=None,
        description="End of reporting period (by issue_date, inclusive)",
    ),
    client_id: Optional[uuid.UUID] = Query(
        default=None, description="Restrict to a single client"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> RevenueStatsResponse:
    """
    Returns comprehensive revenue analytics for the finance dashboard.

    Sections:
    - **Summary totals**: total invoiced, collected, and outstanding MYR
    - **By month**: monthly revenue time-series
    - **By service type**: revenue broken down by job type
    - **By client**: top clients by invoiced amount
    - **AR ageing**: accounts-receivable ageing schedule (current, 1-30, 31-60, 61-90, 90+ days)
    """
    from models.job import Job

    # Build base filters (non-void invoices only)
    base_filters: list = [Invoice.is_void == False]  # noqa: E712

    if client_id:
        base_filters.append(Invoice.client_id == client_id)
    if date_from:
        base_filters.append(Invoice.issue_date >= date_from)
    if date_to:
        base_filters.append(Invoice.issue_date <= date_to)

    # ── Summary totals ────────────────────────────────────────
    summary_stmt = select(
        func.coalesce(func.sum(Invoice.total_myr), 0).label("total_invoiced"),
        func.coalesce(func.sum(Invoice.paid_amount_myr), 0).label("total_collected"),
        func.coalesce(func.sum(Invoice.total_myr - Invoice.paid_amount_myr), 0).label(
            "total_outstanding"
        ),
    ).where(and_(*base_filters))

    summary_result = await db.execute(summary_stmt)
    summary_row = summary_result.one()

    total_invoiced = Decimal(str(summary_row.total_invoiced))
    total_collected = Decimal(str(summary_row.total_collected))
    total_outstanding = Decimal(str(summary_row.total_outstanding))

    # ── Monthly revenue time-series ───────────────────────────
    month_stmt = (
        select(
            func.date_trunc("month", Invoice.issue_date).label("period"),
            func.coalesce(func.sum(Invoice.total_myr), 0).label("invoiced"),
            func.coalesce(func.sum(Invoice.paid_amount_myr), 0).label("collected"),
            func.coalesce(
                func.sum(Invoice.total_myr - Invoice.paid_amount_myr), 0
            ).label("outstanding"),
            func.count(Invoice.id).label("invoice_count"),
        )
        .where(and_(*base_filters))
        .group_by(func.date_trunc("month", Invoice.issue_date), Invoice.issue_date)
        .order_by(func.date_trunc("month", Invoice.issue_date))
    )
    month_result = await db.execute(month_stmt)

    by_month: List[RevenueByMonth] = []
    for row in month_result:
        period_dt = row.period
        if period_dt is None:
            continue
        # period_dt may be a date or datetime
        if hasattr(period_dt, "year"):
            year = period_dt.year
            month = period_dt.month
        else:
            year, month = int(str(period_dt)[:4]), int(str(period_dt)[5:7])

        by_month.append(
            RevenueByMonth(
                year=year,
                month=month,
                period_label=f"{year}-{month:02d}",
                invoiced_myr=Decimal(str(row.invoiced)),
                collected_myr=Decimal(str(row.collected)),
                outstanding_myr=Decimal(str(row.outstanding)),
                invoice_count=row.invoice_count,
            )
        )

    # ── Revenue by service type (via job_ids array join) ──────
    # Fetch all invoices with job_ids and resolve job types
    invoices_with_jobs_stmt = select(
        Invoice.id,
        Invoice.total_myr,
        Invoice.job_ids,
    ).where(and_(*base_filters, Invoice.job_ids != None))  # noqa: E711

    invoice_job_result = await db.execute(invoices_with_jobs_stmt)
    invoice_job_rows = invoice_job_result.all()

    service_type_revenue: Dict[str, Dict[str, Any]] = {}

    for inv_row in invoice_job_rows:
        job_ids = inv_row.job_ids or []
        if not job_ids:
            continue
        # Sample first job to get type (simplified — for accuracy, prorate across all)
        for jid in job_ids[:1]:
            job_result = await db.execute(select(Job.job_type).where(Job.id == jid))
            job_type_row = job_result.scalar_one_or_none()
            if job_type_row:
                stype = job_type_row
                if stype not in service_type_revenue:
                    service_type_revenue[stype] = {
                        "invoiced_myr": Decimal("0"),
                        "count": 0,
                    }
                service_type_revenue[stype]["invoiced_myr"] += Decimal(
                    str(inv_row.total_myr)
                )
                service_type_revenue[stype]["count"] += 1

    by_service_type: List[RevenueByServiceType] = [
        RevenueByServiceType(
            service_type=stype,
            invoiced_myr=data["invoiced_myr"],
            invoice_count=data["count"],
        )
        for stype, data in sorted(
            service_type_revenue.items(),
            key=lambda x: x[1]["invoiced_myr"],
            reverse=True,
        )
    ]

    # ── Revenue by client (top 20) ────────────────────────────
    client_stmt = (
        select(
            Invoice.client_id,
            func.coalesce(func.sum(Invoice.total_myr), 0).label("invoiced"),
            func.coalesce(func.sum(Invoice.paid_amount_myr), 0).label("collected"),
            func.coalesce(
                func.sum(Invoice.total_myr - Invoice.paid_amount_myr), 0
            ).label("outstanding"),
        )
        .where(and_(*base_filters))
        .group_by(Invoice.client_id)
        .order_by(func.coalesce(func.sum(Invoice.total_myr), 0).desc())
        .limit(20)
    )
    client_result = await db.execute(client_stmt)

    by_client: List[RevenueByClient] = []
    for row in client_result:
        from models.client import Client as ClientModel

        c_result = await db.execute(
            select(ClientModel.company_name).where(ClientModel.id == row.client_id)
        )
        company_name = c_result.scalar_one_or_none() or "Unknown"

        by_client.append(
            RevenueByClient(
                client_id=row.client_id,
                company_name=company_name,
                invoiced_myr=Decimal(str(row.invoiced)),
                collected_myr=Decimal(str(row.collected)),
                outstanding_myr=Decimal(str(row.outstanding)),
            )
        )

    # ── Accounts receivable ageing schedule ───────────────────
    today = date.today()

    # Fetch all unpaid/overdue/partial non-void invoices with due_date
    unpaid_stmt = select(
        Invoice.id,
        Invoice.invoice_number,
        Invoice.due_date,
        Invoice.total_myr,
        Invoice.paid_amount_myr,
        Invoice.status,
    ).where(
        and_(
            Invoice.is_void == False,  # noqa: E712
            Invoice.status.in_(["unpaid", "partial", "overdue"]),
            *([Invoice.client_id == client_id] if client_id else []),
        )
    )
    unpaid_result = await db.execute(unpaid_stmt)
    unpaid_rows = unpaid_result.all()

    ageing_buckets: Dict[str, Dict[str, Any]] = {
        "current": {
            "bracket": "current",
            "invoice_count": 0,
            "outstanding_myr": Decimal("0"),
        },
        "1-30 days": {
            "bracket": "1-30 days",
            "invoice_count": 0,
            "outstanding_myr": Decimal("0"),
        },
        "31-60 days": {
            "bracket": "31-60 days",
            "invoice_count": 0,
            "outstanding_myr": Decimal("0"),
        },
        "61-90 days": {
            "bracket": "61-90 days",
            "invoice_count": 0,
            "outstanding_myr": Decimal("0"),
        },
        "90+ days": {
            "bracket": "90+ days",
            "invoice_count": 0,
            "outstanding_myr": Decimal("0"),
        },
    }

    for row in unpaid_rows:
        outstanding = Decimal(str(row.total_myr)) - Decimal(str(row.paid_amount_myr))
        if outstanding <= 0:
            continue

        if row.due_date is None or row.due_date >= today:
            bucket = "current"
        else:
            days_overdue = (today - row.due_date).days
            if days_overdue <= 30:
                bucket = "1-30 days"
            elif days_overdue <= 60:
                bucket = "31-60 days"
            elif days_overdue <= 90:
                bucket = "61-90 days"
            else:
                bucket = "90+ days"

        ageing_buckets[bucket]["invoice_count"] += 1
        ageing_buckets[bucket]["outstanding_myr"] += outstanding

    ageing_schedule: List[AgeingBracket] = [
        AgeingBracket(
            bracket=data["bracket"],
            invoice_count=data["invoice_count"],
            outstanding_myr=data["outstanding_myr"].quantize(Decimal("0.01")),
        )
        for data in ageing_buckets.values()
    ]

    return RevenueStatsResponse(
        period_from=date_from.isoformat() if date_from else None,
        period_to=date_to.isoformat() if date_to else None,
        total_invoiced_myr=total_invoiced.quantize(Decimal("0.01")),
        total_collected_myr=total_collected.quantize(Decimal("0.01")),
        total_outstanding_myr=total_outstanding.quantize(Decimal("0.01")),
        by_month=by_month,
        by_service_type=by_service_type,
        by_client=by_client,
        ageing_schedule=ageing_schedule,
    )


# =============================================================
# GET /stats/summary — finance dashboard KPI tiles
# =============================================================


@router.get(
    "/stats/summary",
    response_model=Dict[str, Any],
    summary="Finance dashboard KPI summary",
    description=(
        "Returns key finance metrics for dashboard tiles: "
        "total invoiced, collected, outstanding, overdue count, "
        "and monthly trend."
    ),
)
async def finance_summary(
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    """High-level finance KPI tiles for the management dashboard."""

    today = date.today()
    month_start = today.replace(day=1)

    # All-time totals (non-void)
    total_stmt = select(
        func.coalesce(func.sum(Invoice.total_myr), 0).label("total_invoiced"),
        func.coalesce(func.sum(Invoice.paid_amount_myr), 0).label("total_collected"),
        func.coalesce(func.sum(Invoice.total_myr - Invoice.paid_amount_myr), 0).label(
            "total_outstanding"
        ),
        func.count(Invoice.id).label("total_invoices"),
        func.count(Invoice.id)
        .filter(Invoice.status == "overdue")
        .label("overdue_count"),
        func.count(Invoice.id).filter(Invoice.status == "paid").label("paid_count"),
    ).where(Invoice.is_void == False)  # noqa: E712

    total_result = await db.execute(total_stmt)
    total_row = total_result.one()

    # This month
    month_stmt = select(
        func.coalesce(func.sum(Invoice.total_myr), 0).label("invoiced"),
        func.coalesce(func.sum(Invoice.paid_amount_myr), 0).label("collected"),
        func.count(Invoice.id).label("count"),
    ).where(
        and_(
            Invoice.is_void == False,  # noqa: E712
            Invoice.issue_date >= month_start,
        )
    )
    month_result = await db.execute(month_stmt)
    month_row = month_result.one()

    # Most overdue invoice
    most_overdue_stmt = (
        select(
            Invoice.invoice_number,
            Invoice.due_date,
            Invoice.client_id,
            (Invoice.total_myr - Invoice.paid_amount_myr).label("outstanding"),
        )
        .where(
            and_(
                Invoice.is_void == False,  # noqa: E712
                Invoice.status.in_(["overdue", "unpaid", "partial"]),
                Invoice.due_date < today,
            )
        )
        .order_by(Invoice.due_date.asc())
        .limit(1)
    )
    overdue_result = await db.execute(most_overdue_stmt)
    most_overdue_row = overdue_result.one_or_none()

    most_overdue: Optional[Dict[str, Any]] = None
    if most_overdue_row:
        days_overdue = (
            (today - most_overdue_row.due_date).days if most_overdue_row.due_date else 0
        )
        most_overdue = {
            "invoice_number": most_overdue_row.invoice_number,
            "due_date": most_overdue_row.due_date.isoformat()
            if most_overdue_row.due_date
            else None,
            "days_overdue": days_overdue,
            "outstanding_myr": float(most_overdue_row.outstanding),
            "client_id": str(most_overdue_row.client_id),
        }

    return {
        "as_of": today.isoformat(),
        "all_time": {
            "total_invoiced_myr": float(total_row.total_invoiced),
            "total_collected_myr": float(total_row.total_collected),
            "total_outstanding_myr": float(total_row.total_outstanding),
            "total_invoices": total_row.total_invoices,
            "overdue_invoices": total_row.overdue_count,
            "paid_invoices": total_row.paid_count,
            "collection_rate_pct": round(
                float(total_row.total_collected)
                / float(total_row.total_invoiced)
                * 100,
                2,
            )
            if float(total_row.total_invoiced) > 0
            else 0.0,
        },
        "this_month": {
            "invoiced_myr": float(month_row.invoiced),
            "collected_myr": float(month_row.collected),
            "invoice_count": month_row.count,
            "period": month_start.isoformat(),
        },
        "most_overdue_invoice": most_overdue,
    }


# =============================================================
# GET /invoices/{id}/pdf — generate or retrieve invoice PDF
# =============================================================


@router.get(
    "/invoices/{invoice_id}/pdf",
    response_model=Dict[str, Any],
    summary="Generate or retrieve invoice PDF",
    description=(
        "Returns the PDF URL for an invoice, "
        "or queues PDF generation if the PDF does not yet exist."
    ),
)
async def get_invoice_pdf(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Returns or triggers PDF generation for an invoice.

    If the PDF already exists (pdf_path is set), returns the URL immediately.
    Otherwise, queues a Celery task for PDF generation and returns a task_id.
    """
    invoice = await _get_invoice_or_404(invoice_id, db)

    # Access control for client portal
    if current_user.get("role") == "client":
        from models.client import Client as ClientModel

        client_result = await db.execute(
            select(ClientModel).where(
                ClientModel.portal_user_id == uuid.UUID(current_user["sub"])
            )
        )
        client_obj = client_result.scalar_one_or_none()
        if client_obj is None or client_obj.id != invoice.client_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this invoice",
            )

    # Return existing PDF if available
    if invoice.pdf_path:
        return {
            "invoice_id": str(invoice_id),
            "invoice_number": invoice.invoice_number,
            "status": "ready",
            "pdf_url": f"{settings.BACKEND_URL}/static/invoices/{invoice_id}.pdf",
            "pdf_path": invoice.pdf_path,
        }

    # Queue PDF generation
    task_id: Optional[str] = None
    try:
        from tasks.pdf_tasks import generate_invoice_pdf  # type: ignore[import]

        task = generate_invoice_pdf.delay(
            invoice_id=str(invoice_id),
        )
        task_id = task.id
        logger.info(
            "PDF generation queued for invoice %s task_id=%s",
            invoice.invoice_number,
            task_id,
        )
    except Exception as exc:
        logger.warning(
            "Could not queue PDF generation for invoice %s: %s",
            invoice.invoice_number,
            exc,
        )

    return {
        "invoice_id": str(invoice_id),
        "invoice_number": invoice.invoice_number,
        "status": "queued" if task_id else "error",
        "task_id": task_id,
        "pdf_url": None,
        "message": (
            "PDF generation has been queued. Poll this endpoint to check status."
            if task_id
            else "PDF generation could not be queued. Please try again."
        ),
    }


# =============================================================
# GET /stats/receivables-ageing — Receivables ageing schedule
# =============================================================


@router.get(
    "/stats/receivables-ageing",
    response_model=Dict[str, Any],
    summary="Accounts receivable ageing schedule",
    description=(
        "Returns the AR ageing schedule: outstanding amounts grouped by "
        "age buckets (current, 1-30 days, 31-60 days, 61-90 days, 90+ days)."
    ),
)
async def receivables_ageing(
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Returns the accounts receivable ageing schedule.

    This endpoint extracts just the ageing data from the full revenue stats
    for use in the finance dashboard widgets.
    """
    from decimal import Decimal

    today = date.today()

    # Fetch all unpaid/overdue/partial non-void invoices with due_date
    unpaid_stmt = select(
        Invoice.id,
        Invoice.invoice_number,
        Invoice.due_date,
        Invoice.total_myr,
        Invoice.paid_amount_myr,
        Invoice.status,
        Invoice.client_id,
    ).where(
        and_(
            Invoice.is_void == False,  # noqa: E712
            Invoice.status.in_(["unpaid", "partial", "overdue"]),
        )
    )
    unpaid_result = await db.execute(unpaid_stmt)
    unpaid_rows = unpaid_result.all()

    ageing_buckets: Dict[str, Dict[str, Any]] = {
        "current": {
            "bracket": "current",
            "invoice_count": 0,
            "outstanding_myr": Decimal("0"),
            "invoices": [],
        },
        "1-30 days": {
            "bracket": "1-30 days",
            "invoice_count": 0,
            "outstanding_myr": Decimal("0"),
            "invoices": [],
        },
        "31-60 days": {
            "bracket": "31-60 days",
            "invoice_count": 0,
            "outstanding_myr": Decimal("0"),
            "invoices": [],
        },
        "61-90 days": {
            "bracket": "61-90 days",
            "invoice_count": 0,
            "outstanding_myr": Decimal("0"),
            "invoices": [],
        },
        "90+ days": {
            "bracket": "90+ days",
            "invoice_count": 0,
            "outstanding_myr": Decimal("0"),
            "invoices": [],
        },
    }

    total_outstanding = Decimal("0")

    for row in unpaid_rows:
        outstanding = Decimal(str(row.total_myr)) - Decimal(str(row.paid_amount_myr))
        if outstanding <= 0:
            continue

        total_outstanding += outstanding

        if row.due_date is None or row.due_date >= today:
            bucket = "current"
        else:
            days_overdue = (today - row.due_date).days
            if days_overdue <= 30:
                bucket = "1-30 days"
            elif days_overdue <= 60:
                bucket = "31-60 days"
            elif days_overdue <= 90:
                bucket = "61-90 days"
            else:
                bucket = "90+ days"

        ageing_buckets[bucket]["invoice_count"] += 1
        ageing_buckets[bucket]["outstanding_myr"] += outstanding
        ageing_buckets[bucket]["invoices"].append({
            "invoice_id": str(row.id),
            "invoice_number": row.invoice_number,
            "client_id": str(row.client_id),
            "due_date": row.due_date.isoformat() if row.due_date else None,
            "outstanding_myr": float(outstanding),
            "status": row.status,
        })

    return {
        "as_of_date": today.isoformat(),
        "total_outstanding_myr": float(total_outstanding.quantize(Decimal("0.01"))),
        "ageing_schedule": [
            {
                "bracket": data["bracket"],
                "invoice_count": data["invoice_count"],
                "outstanding_myr": float(data["outstanding_myr"].quantize(Decimal("0.01"))),
            }
            for data in ageing_buckets.values()
        ],
        "buckets": {
            k: {
                "bracket": v["bracket"],
                "invoice_count": v["invoice_count"],
                "outstanding_myr": float(v["outstanding_myr"].quantize(Decimal("0.01"))),
                "invoices": v["invoices"],
            }
            for k, v in ageing_buckets.items()
        },
    }
