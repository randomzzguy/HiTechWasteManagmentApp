# =============================================================
# Hi-Tech Waste Management — ESG & Carbon Router
# Carbon records, client/company dashboards, report generation
# =============================================================

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from config import get_settings
from database import get_db
from fastapi import APIRouter, Depends, HTTPException, Query, status
from models.esg import (
    CarbonRecord,
    CarbonRecordCreate,
    CarbonRecordListItem,
    CarbonRecordRead,
    CarbonRecordUpdate,
    ESGClientDashboard,
    ESGCompanyDashboard,
    ESGReportGenerateRequest,
    ESGReportStatusResponse,
)
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from routers.auth import get_current_user, require_roles

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()

# =============================================================
# Role constants
# =============================================================

MANAGEMENT_ROLES = ["superadmin", "management", "operations_manager"]
ALL_STAFF = [
    "superadmin",
    "management",
    "operations_manager",
    "field_supervisor",
    "compliance_officer",
]

# =============================================================
# In-memory report task store
# Maps task_id -> {status, pdf_url, ...}
# In production, query the Celery result backend instead.
# =============================================================
_REPORT_TASKS: Dict[str, Dict[str, Any]] = {}


# =============================================================
# Helpers
# =============================================================


def _date_to_utc_start(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=timezone.utc)


def _date_to_utc_end(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, 23, 59, 59, 999999, tzinfo=timezone.utc)


# SDG tags that apply to waste management activities
SDG_TAGS_STANDARD = [
    "SDG 12: Responsible Consumption and Production",
    "SDG 13: Climate Action",
    "SDG 15: Life on Land",
]

SDG_TAGS_EXTENDED = SDG_TAGS_STANDARD + [
    "SDG 3: Good Health and Well-being",
    "SDG 11: Sustainable Cities and Communities",
    "SDG 17: Partnerships for the Goals",
]


# =============================================================
# GET /carbon-records — list carbon records
# =============================================================


@router.get(
    "/carbon-records",
    response_model=Dict[str, Any],
    summary="List carbon records",
    description=(
        "Returns a paginated list of carbon records. "
        "Optionally filter by client_id, job_id, and calculated_at date range."
    ),
)
async def list_carbon_records(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
    client_id: Optional[uuid.UUID] = Query(
        default=None, description="Filter by client UUID"
    ),
    job_id: Optional[uuid.UUID] = Query(default=None, description="Filter by job UUID"),
    date_from: Optional[date] = Query(
        default=None, description="Filter records calculated on or after this date"
    ),
    date_to: Optional[date] = Query(
        default=None, description="Filter records calculated on or before this date"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    """Returns paginated carbon/ESG records with optional filters."""

    filters: list = []

    # Client-portal users can only see their own data
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
        filters.append(CarbonRecord.client_id == client_obj.id)
    elif client_id is not None:
        filters.append(CarbonRecord.client_id == client_id)

    if job_id is not None:
        filters.append(CarbonRecord.job_id == job_id)

    if date_from:
        filters.append(CarbonRecord.calculated_at >= _date_to_utc_start(date_from))
    if date_to:
        filters.append(CarbonRecord.calculated_at <= _date_to_utc_end(date_to))

    base_stmt = select(CarbonRecord)
    if filters:
        base_stmt = base_stmt.where(and_(*filters))

    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total_result = await db.execute(count_stmt)
    total: int = total_result.scalar_one()

    stmt = (
        base_stmt.order_by(CarbonRecord.calculated_at.desc()).offset(skip).limit(limit)
    )
    result = await db.execute(stmt)
    records = result.scalars().all()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": [CarbonRecordListItem.model_validate(r) for r in records],
    }


# =============================================================
# POST /carbon-records — create carbon record
# =============================================================


@router.post(
    "/carbon-records",
    response_model=CarbonRecordRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a carbon record",
    description=(
        "Creates a new carbon impact record for a job. "
        "net_carbon_impact_kgco2e is auto-computed from components if not provided."
    ),
)
async def create_carbon_record(
    payload: CarbonRecordCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> CarbonRecordRead:
    """
    Creates a new carbon calculation record.

    - Validates job and client exist if provided.
    - Auto-computes net_carbon_impact_kgco2e from component fields
      via the Pydantic model validator (transport - landfill - recycling - wte).
    - Denormalises client_id from the parent job if omitted.
    """
    # Validate and denormalise client_id from job if possible
    resolved_client_id = payload.client_id
    if payload.job_id is not None:
        from models.job import Job

        job_result = await db.execute(select(Job).where(Job.id == payload.job_id))
        job = job_result.scalar_one_or_none()
        if job is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {payload.job_id} not found",
            )
        if resolved_client_id is None:
            resolved_client_id = job.client_id

    # Validate client exists if supplied
    if resolved_client_id is not None:
        from models.client import Client as ClientModel

        client_result = await db.execute(
            select(ClientModel).where(ClientModel.id == resolved_client_id)
        )
        if client_result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Client {resolved_client_id} not found",
            )

    calculated_at = payload.calculated_at or datetime.now(timezone.utc)

    record = CarbonRecord(
        id=uuid.uuid4(),
        job_id=payload.job_id,
        client_id=resolved_client_id,
        calculated_at=calculated_at,
        transport_emissions_kgco2e=payload.transport_emissions_kgco2e,
        landfill_avoidance_kgco2e=payload.landfill_avoidance_kgco2e,
        recycling_credit_kgco2e=payload.recycling_credit_kgco2e,
        wte_credit_kgco2e=payload.wte_credit_kgco2e,
        net_carbon_impact_kgco2e=payload.net_carbon_impact_kgco2e,
        methodology_notes=payload.methodology_notes,
    )
    db.add(record)
    await db.flush()
    await db.refresh(record)

    logger.info(
        "CarbonRecord created id=%s job=%s client=%s net_kgco2e=%s by user=%s",
        record.id,
        record.job_id,
        record.client_id,
        record.net_carbon_impact_kgco2e,
        current_user.get("sub"),
    )
    return CarbonRecordRead.model_validate(record)


# =============================================================
# GET /carbon-records/{id} — single record
# =============================================================


@router.get(
    "/carbon-records/{record_id}",
    response_model=CarbonRecordRead,
    summary="Get a carbon record by ID",
)
async def get_carbon_record(
    record_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> CarbonRecordRead:
    """Returns the full detail of a single carbon record."""
    result = await db.execute(select(CarbonRecord).where(CarbonRecord.id == record_id))
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Carbon record {record_id} not found",
        )
    return CarbonRecordRead.model_validate(record)


# =============================================================
# PUT /carbon-records/{id} — update record
# =============================================================


@router.put(
    "/carbon-records/{record_id}",
    response_model=CarbonRecordRead,
    summary="Update a carbon record",
)
async def update_carbon_record(
    record_id: uuid.UUID,
    payload: CarbonRecordUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> CarbonRecordRead:
    """Partially updates a carbon record and recomputes net impact if needed."""
    result = await db.execute(select(CarbonRecord).where(CarbonRecord.id == record_id))
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Carbon record {record_id} not found",
        )

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(record, field, value)

    await db.flush()
    await db.refresh(record)
    return CarbonRecordRead.model_validate(record)


# =============================================================
# GET /client/{id}/dashboard — client ESG dashboard
# =============================================================


@router.get(
    "/client/{client_id}/dashboard",
    response_model=ESGClientDashboard,
    summary="Full ESG dashboard for a client",
    description=(
        "Returns a comprehensive ESG performance dashboard for a single client. "
        "Includes total CO₂ saved, diversion rate history, recycling breakdown, "
        "trend vs previous period, and SDG alignment tags."
    ),
)
async def client_esg_dashboard(
    client_id: uuid.UUID,
    date_from: Optional[date] = Query(
        default=None, description="Period start date (defaults to 12 months ago)"
    ),
    date_to: Optional[date] = Query(
        default=None, description="Period end date (defaults to today)"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> ESGClientDashboard:
    """
    Full ESG client dashboard.

    Returns:
    - Carbon impact totals (transport emissions, credits, net impact)
    - Diversion rate percentage (recyclable kg / total waste kg × 100)
    - Recycling breakdown by material type
    - Monthly CO₂ trend history
    - Trend vs previous period (% change)
    - Applicable UN SDG tags

    The period defaults to the current calendar year if not specified.
    """
    # Validate client exists
    from models.client import Client as ClientModel

    client_result = await db.execute(
        select(ClientModel).where(ClientModel.id == client_id)
    )
    client = client_result.scalar_one_or_none()
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client {client_id} not found",
        )

    # Client-portal access check
    if current_user.get("role") == "client":
        portal_result = await db.execute(
            select(ClientModel).where(
                ClientModel.portal_user_id == uuid.UUID(current_user["sub"])
            )
        )
        portal_client = portal_result.scalar_one_or_none()
        if portal_client is None or portal_client.id != client_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this client's ESG dashboard",
            )

    # Default period = current year
    today = date.today()
    if date_to is None:
        date_to = today
    if date_from is None:
        date_from = date(today.year, 1, 1)

    dt_from = _date_to_utc_start(date_from)
    dt_to = _date_to_utc_end(date_to)

    # ── Carbon aggregates for the period ─────────────────────
    carbon_stmt = select(
        func.count(CarbonRecord.id).label("record_count"),
        func.coalesce(func.sum(CarbonRecord.transport_emissions_kgco2e), 0).label(
            "transport"
        ),
        func.coalesce(func.sum(CarbonRecord.landfill_avoidance_kgco2e), 0).label(
            "landfill"
        ),
        func.coalesce(func.sum(CarbonRecord.recycling_credit_kgco2e), 0).label(
            "recycling"
        ),
        func.coalesce(func.sum(CarbonRecord.wte_credit_kgco2e), 0).label("wte"),
        func.coalesce(func.sum(CarbonRecord.net_carbon_impact_kgco2e), 0).label("net"),
    ).where(
        and_(
            CarbonRecord.client_id == client_id,
            CarbonRecord.calculated_at >= dt_from,
            CarbonRecord.calculated_at <= dt_to,
        )
    )
    carbon_result = await db.execute(carbon_stmt)
    carbon_row = carbon_result.one()

    total_transport = Decimal(str(carbon_row.transport))
    total_landfill = Decimal(str(carbon_row.landfill))
    total_recycling_credit = Decimal(str(carbon_row.recycling))
    total_wte = Decimal(str(carbon_row.wte))
    total_net = Decimal(str(carbon_row.net))
    total_co2_saved = (
        total_landfill + total_recycling_credit + total_wte - total_transport
    ).quantize(Decimal("0.0001"))

    # ── Weighbridge (total waste) ─────────────────────────────
    from models.weighbridge import WeighbridgeRecord

    wb_stmt = select(
        func.coalesce(func.sum(WeighbridgeRecord.net_weight_kg), 0).label("total_kg")
    ).where(
        and_(
            WeighbridgeRecord.client_id == client_id,
            WeighbridgeRecord.recorded_at >= dt_from,
            WeighbridgeRecord.recorded_at <= dt_to,
        )
    )
    wb_result = await db.execute(wb_stmt)
    wb_row = wb_result.one()
    total_waste_kg = Decimal(str(wb_row.total_kg))

    # ── Recyclable totals ─────────────────────────────────────
    from models.recyclable import RecyclableRecord

    rec_stmt = select(
        func.coalesce(func.sum(RecyclableRecord.total_recyclable_kg), 0).label(
            "total_rec"
        )
    ).where(
        and_(
            RecyclableRecord.client_id == client_id,
            RecyclableRecord.recorded_at >= dt_from,
            RecyclableRecord.recorded_at <= dt_to,
        )
    )
    rec_result = await db.execute(rec_stmt)
    rec_row = rec_result.one()
    total_recyclable_kg = Decimal(str(rec_row.total_rec))

    # Compute rates
    diversion_rate_pct: Optional[Decimal] = None
    recycling_rate_pct: Optional[Decimal] = None
    if total_waste_kg > 0:
        diversion_rate_pct = (total_recyclable_kg / total_waste_kg * 100).quantize(
            Decimal("0.01")
        )
        recycling_rate_pct = diversion_rate_pct  # simplified

    # ── Previous period for trend comparison ─────────────────
    period_days = (date_to - date_from).days
    prev_date_to = date_from
    prev_date_from = date(
        max(prev_date_to.year - 1, 2000),
        prev_date_to.month,
        prev_date_to.day,
    )
    dt_prev_from = _date_to_utc_start(prev_date_from)
    dt_prev_to = _date_to_utc_end(prev_date_to)

    prev_stmt = select(
        func.coalesce(func.sum(CarbonRecord.net_carbon_impact_kgco2e), 0).label(
            "prev_net"
        )
    ).where(
        and_(
            CarbonRecord.client_id == client_id,
            CarbonRecord.calculated_at >= dt_prev_from,
            CarbonRecord.calculated_at <= dt_prev_to,
        )
    )
    prev_result = await db.execute(prev_stmt)
    prev_row = prev_result.one()
    prev_net = Decimal(str(prev_row.prev_net))

    co2_trend_pct: Optional[Decimal] = None
    if prev_net != 0:
        co2_trend_pct = ((total_net - prev_net) / abs(prev_net) * 100).quantize(
            Decimal("0.01")
        )

    # ── Monthly diversion rate history ────────────────────────
    month_wb_stmt = (
        select(
            func.date_trunc("month", WeighbridgeRecord.recorded_at).label("period"),
            func.coalesce(func.sum(WeighbridgeRecord.net_weight_kg), 0).label(
                "total_kg"
            ),
        )
        .where(
            and_(
                WeighbridgeRecord.client_id == client_id,
                WeighbridgeRecord.recorded_at >= dt_from,
                WeighbridgeRecord.recorded_at <= dt_to,
            )
        )
        .group_by(func.date_trunc("month", WeighbridgeRecord.recorded_at))
        .order_by(func.date_trunc("month", WeighbridgeRecord.recorded_at))
    )
    month_wb_result = await db.execute(month_wb_stmt)
    wb_monthly: Dict[str, float] = {
        row.period.isoformat(): float(row.total_kg)
        for row in month_wb_result.all()
        if row.period
    }

    month_rec_stmt = (
        select(
            func.date_trunc("month", RecyclableRecord.recorded_at).label("period"),
            func.coalesce(func.sum(RecyclableRecord.total_recyclable_kg), 0).label(
                "total_rec"
            ),
        )
        .where(
            and_(
                RecyclableRecord.client_id == client_id,
                RecyclableRecord.recorded_at >= dt_from,
                RecyclableRecord.recorded_at <= dt_to,
            )
        )
        .group_by(func.date_trunc("month", RecyclableRecord.recorded_at))
        .order_by(func.date_trunc("month", RecyclableRecord.recorded_at))
    )
    month_rec_result = await db.execute(month_rec_stmt)
    rec_monthly: Dict[str, float] = {
        row.period.isoformat(): float(row.total_rec)
        for row in month_rec_result.all()
        if row.period
    }

    all_months = sorted(set(list(wb_monthly.keys()) + list(rec_monthly.keys())))
    diversion_history: List[Dict[str, Any]] = []
    for month in all_months:
        wb_kg = wb_monthly.get(month, 0.0)
        rec_kg = rec_monthly.get(month, 0.0)
        rate = round(rec_kg / wb_kg * 100, 2) if wb_kg > 0 else 0.0
        diversion_history.append(
            {
                "period": month,
                "total_waste_kg": wb_kg,
                "recyclable_kg": rec_kg,
                "diversion_rate_pct": rate,
            }
        )

    # ── Recycling breakdown by material ──────────────────────
    rec_records_stmt = select(RecyclableRecord.material_breakdown).where(
        and_(
            RecyclableRecord.client_id == client_id,
            RecyclableRecord.recorded_at >= dt_from,
            RecyclableRecord.recorded_at <= dt_to,
            RecyclableRecord.material_breakdown.is_not(None),
        )
    )
    rec_records_result = await db.execute(rec_records_stmt)
    all_breakdowns = rec_records_result.scalars().all()

    material_totals: Dict[str, float] = {}
    for bd in all_breakdowns:
        if not isinstance(bd, dict):
            continue
        for key, val in bd.items():
            if val is not None:
                material_totals[key] = material_totals.get(key, 0.0) + float(val)

    recycling_breakdown = [
        {"material": k.replace("_kg", ""), "total_kg": round(v, 3)}
        for k, v in sorted(material_totals.items(), key=lambda x: x[1], reverse=True)
        if v > 0
    ]

    # ── SDG tags based on activity ────────────────────────────
    sdg_tags = SDG_TAGS_STANDARD.copy()
    if total_recyclable_kg > 0:
        sdg_tags.append("SDG 12: Responsible Consumption and Production")
    if total_co2_saved > 0:
        sdg_tags.append("SDG 13: Climate Action")
    sdg_tags = list(set(sdg_tags))

    return ESGClientDashboard(
        client_id=client_id,
        period_from=date_from.isoformat(),
        period_to=date_to.isoformat(),
        total_co2_saved_kgco2e=total_co2_saved,
        total_transport_emissions_kgco2e=total_transport,
        total_landfill_avoidance_kgco2e=total_landfill,
        total_recycling_credit_kgco2e=total_recycling_credit,
        total_wte_credit_kgco2e=total_wte,
        diversion_rate_pct=diversion_rate_pct,
        recycling_rate_pct=recycling_rate_pct,
        co2_trend_pct=co2_trend_pct,
        diversion_rate_history=diversion_history,
        recycling_breakdown=recycling_breakdown,
        sdg_tags=sdg_tags,
    )


# =============================================================
# GET /company/dashboard — company-wide ESG dashboard
# =============================================================


@router.get(
    "/company/dashboard",
    response_model=ESGCompanyDashboard,
    summary="Company-wide aggregate ESG performance dashboard",
    description=(
        "Returns the company-wide aggregate ESG performance metrics. "
        "Includes total CO₂ saved, waste processed, top clients by impact, "
        "and monthly trend data."
    ),
)
async def company_esg_dashboard(
    date_from: Optional[date] = Query(
        default=None, description="Period start date (defaults to current year start)"
    ),
    date_to: Optional[date] = Query(
        default=None, description="Period end date (defaults to today)"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> ESGCompanyDashboard:
    """
    Company-wide ESG dashboard.

    Aggregates carbon records, weighbridge tonnage, and recyclable data
    across ALL clients to produce a company-level sustainability scorecard.

    Returns:
    - Total waste processed company-wide
    - Total CO₂ savings and component breakdown
    - Overall diversion and recycling rates
    - Top 5 clients by CO₂ impact
    - Monthly CO₂ trend time-series
    - Company-level SDG alignment
    """
    today = date.today()
    if date_to is None:
        date_to = today
    if date_from is None:
        date_from = date(today.year, 1, 1)

    dt_from = _date_to_utc_start(date_from)
    dt_to = _date_to_utc_end(date_to)

    # ── Company-wide carbon aggregates ───────────────────────
    carbon_stmt = select(
        func.coalesce(func.sum(CarbonRecord.transport_emissions_kgco2e), 0).label(
            "transport"
        ),
        func.coalesce(func.sum(CarbonRecord.landfill_avoidance_kgco2e), 0).label(
            "landfill"
        ),
        func.coalesce(func.sum(CarbonRecord.recycling_credit_kgco2e), 0).label(
            "recycling"
        ),
        func.coalesce(func.sum(CarbonRecord.wte_credit_kgco2e), 0).label("wte"),
        func.coalesce(func.sum(CarbonRecord.net_carbon_impact_kgco2e), 0).label("net"),
    ).where(
        and_(
            CarbonRecord.calculated_at >= dt_from,
            CarbonRecord.calculated_at <= dt_to,
        )
    )
    carbon_result = await db.execute(carbon_stmt)
    carbon_row = carbon_result.one()

    total_transport = Decimal(str(carbon_row.transport))
    total_landfill = Decimal(str(carbon_row.landfill))
    total_recycling_credit = Decimal(str(carbon_row.recycling))
    total_wte = Decimal(str(carbon_row.wte))
    total_net = Decimal(str(carbon_row.net))
    total_co2_saved = (
        total_landfill + total_recycling_credit + total_wte - total_transport
    ).quantize(Decimal("0.0001"))

    # ── Total waste processed ─────────────────────────────────
    from models.weighbridge import WeighbridgeRecord

    wb_stmt = select(
        func.coalesce(func.sum(WeighbridgeRecord.net_weight_kg), 0).label("total_kg")
    ).where(
        and_(
            WeighbridgeRecord.recorded_at >= dt_from,
            WeighbridgeRecord.recorded_at <= dt_to,
        )
    )
    wb_result = await db.execute(wb_stmt)
    wb_row = wb_result.one()
    total_waste_kg = Decimal(str(wb_row.total_kg))

    # ── Recyclable totals ─────────────────────────────────────
    from models.recyclable import RecyclableRecord

    rec_stmt = select(
        func.coalesce(func.sum(RecyclableRecord.total_recyclable_kg), 0).label(
            "total_rec"
        )
    ).where(
        and_(
            RecyclableRecord.recorded_at >= dt_from,
            RecyclableRecord.recorded_at <= dt_to,
        )
    )
    rec_result = await db.execute(rec_stmt)
    rec_row = rec_result.one()
    total_recyclable_kg = Decimal(str(rec_row.total_rec))

    overall_diversion_rate: Optional[Decimal] = None
    overall_recycling_rate: Optional[Decimal] = None
    if total_waste_kg > 0:
        overall_diversion_rate = (total_recyclable_kg / total_waste_kg * 100).quantize(
            Decimal("0.01")
        )
        overall_recycling_rate = overall_diversion_rate

    # ── Top clients by CO₂ saved ──────────────────────────────
    top_clients_stmt = (
        select(
            CarbonRecord.client_id,
            func.coalesce(func.sum(CarbonRecord.net_carbon_impact_kgco2e), 0).label(
                "net_impact"
            ),
            func.coalesce(func.sum(CarbonRecord.landfill_avoidance_kgco2e), 0).label(
                "landfill"
            ),
            func.coalesce(func.sum(CarbonRecord.recycling_credit_kgco2e), 0).label(
                "recycling"
            ),
        )
        .where(
            and_(
                CarbonRecord.calculated_at >= dt_from,
                CarbonRecord.calculated_at <= dt_to,
                CarbonRecord.client_id.is_not(None),
            )
        )
        .group_by(CarbonRecord.client_id)
        .order_by(func.sum(CarbonRecord.net_carbon_impact_kgco2e).asc())
        .limit(5)
    )
    top_result = await db.execute(top_clients_stmt)
    top_clients: List[Dict[str, Any]] = []
    for row in top_result.all():
        # Fetch company name
        from models.client import Client as ClientModel

        c_result = await db.execute(
            select(ClientModel.company_name).where(ClientModel.id == row.client_id)
        )
        company_name_row = c_result.first()
        company_name = company_name_row[0] if company_name_row else str(row.client_id)

        co2_saved = Decimal(str(row.landfill)) + Decimal(str(row.recycling))
        top_clients.append(
            {
                "client_id": str(row.client_id),
                "company_name": company_name,
                "co2_saved_kgco2e": float(co2_saved.quantize(Decimal("0.0001"))),
                "net_impact_kgco2e": float(row.net_impact),
            }
        )

    # ── Monthly CO₂ trend ─────────────────────────────────────
    monthly_stmt = (
        select(
            func.date_trunc("month", CarbonRecord.calculated_at).label("period"),
            func.coalesce(func.sum(CarbonRecord.net_carbon_impact_kgco2e), 0).label(
                "net_kgco2e"
            ),
            func.coalesce(func.sum(CarbonRecord.transport_emissions_kgco2e), 0).label(
                "transport_kgco2e"
            ),
            func.coalesce(
                func.sum(CarbonRecord.landfill_avoidance_kgco2e)
                + func.sum(CarbonRecord.recycling_credit_kgco2e)
                + func.sum(CarbonRecord.wte_credit_kgco2e),
                0,
            ).label("savings_kgco2e"),
        )
        .where(
            and_(
                CarbonRecord.calculated_at >= dt_from,
                CarbonRecord.calculated_at <= dt_to,
            )
        )
        .group_by(func.date_trunc("month", CarbonRecord.calculated_at))
        .order_by(func.date_trunc("month", CarbonRecord.calculated_at))
    )
    monthly_result = await db.execute(monthly_stmt)
    monthly_trend: List[Dict[str, Any]] = [
        {
            "period": row.period.isoformat() if row.period else None,
            "net_kgco2e": float(row.net_kgco2e),
            "transport_kgco2e": float(row.transport_kgco2e),
            "savings_kgco2e": float(row.savings_kgco2e),
        }
        for row in monthly_result.all()
        if row.period
    ]

    return ESGCompanyDashboard(
        period_from=date_from.isoformat(),
        period_to=date_to.isoformat(),
        total_waste_processed_kg=total_waste_kg,
        total_co2_saved_kgco2e=total_co2_saved,
        total_transport_emissions_kgco2e=total_transport,
        total_landfill_avoidance_kgco2e=total_landfill,
        total_recycling_credit_kgco2e=total_recycling_credit,
        total_wte_credit_kgco2e=total_wte,
        overall_diversion_rate_pct=overall_diversion_rate,
        overall_recycling_rate_pct=overall_recycling_rate,
        top_clients_by_co2_saved=top_clients,
        monthly_co2_trend=monthly_trend,
        sdg_tags=SDG_TAGS_EXTENDED,
    )


# =============================================================
# POST /reports/generate — trigger ESG report generation
# =============================================================


@router.post(
    "/reports/generate",
    response_model=ESGReportStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger ESG report generation",
    description=(
        "Triggers a Celery task to generate a PDF ESG/sustainability report. "
        "Returns a task_id for status polling via GET /esg/reports/{task_id}/pdf."
    ),
)
async def generate_esg_report(
    payload: ESGReportGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> ESGReportStatusResponse:
    """
    Triggers asynchronous ESG report generation.

    The report is generated as a PDF by a Celery worker and saved to
    REPORT_OUTPUT_DIR. Use GET /esg/reports/{task_id}/pdf to check
    status and retrieve the download URL once complete.

    Supported sections (all included by default):
    - `summary`    : Executive summary with KPI tiles
    - `carbon`     : Carbon impact breakdown and trend charts
    - `diversion`  : Waste diversion rate history
    - `recycling`  : Material recovery breakdown
    - `compliance` : Scheduled waste status overview
    - `sdg`        : SDG alignment narrative

    If `client_id` is provided, a client-scoped report is generated.
    If omitted, a company-wide report is produced.
    """
    # Validate client if specified
    if payload.client_id is not None:
        from models.client import Client as ClientModel

        client_result = await db.execute(
            select(ClientModel).where(ClientModel.id == payload.client_id)
        )
        if client_result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Client {payload.client_id} not found",
            )

    # Try to queue Celery task
    task_id: Optional[str] = None
    task_id_str = str(uuid.uuid4())

    try:
        from tasks.report_tasks import generate_esg_pdf_report  # type: ignore[import]

        task = generate_esg_pdf_report.delay(
            client_id=str(payload.client_id) if payload.client_id else None,
            period_from=payload.period_from,
            period_to=payload.period_to,
            report_title=payload.report_title,
            include_sections=payload.include_sections,
            requested_by=current_user["sub"],
        )
        task_id = task.id
        task_id_str = task_id

        logger.info(
            "ESG report generation queued: task_id=%s client=%s period=%s→%s",
            task_id,
            payload.client_id,
            payload.period_from,
            payload.period_to,
        )
    except Exception as exc:
        logger.warning(
            "Could not queue ESG report generation task: %s — using placeholder task_id",
            exc,
        )
        # Store a pending entry in the in-memory tracker
        _REPORT_TASKS[task_id_str] = {
            "task_id": task_id_str,
            "status": "pending",
            "client_id": str(payload.client_id) if payload.client_id else None,
            "period_from": payload.period_from,
            "period_to": payload.period_to,
            "report_title": payload.report_title,
            "pdf_url": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "requested_by": current_user["sub"],
            "message": (
                "Report generation queued but worker is unavailable. "
                "Please ensure the Celery worker is running."
            ),
        }

    return ESGReportStatusResponse(
        task_id=task_id_str,
        status="pending",
        pdf_url=None,
        message=(
            "ESG report generation has been queued. "
            f"Poll GET /esg/reports/{task_id_str}/pdf to check status."
        ),
    )


# =============================================================
# GET /reports/{task_id}/pdf — check report status / get PDF URL
# =============================================================


@router.get(
    "/reports/{task_id}/pdf",
    response_model=ESGReportStatusResponse,
    summary="Check ESG report status and retrieve PDF URL",
    description=(
        "Checks the status of a queued ESG report generation task. "
        "Returns the PDF download URL when the report is ready."
    ),
)
async def get_esg_report_status(
    task_id: str,
    current_user: Any = Depends(get_current_user),
) -> ESGReportStatusResponse:
    """
    Polls the status of an ESG report generation task.

    Checks the Celery result backend for the task status.
    Falls back to the in-memory store if Celery is unavailable.

    Response statuses:
    - `pending`  : Task is queued but not yet started
    - `running`  : Task is currently being processed
    - `success`  : Report generated — `pdf_url` is populated
    - `failure`  : Report generation failed — check logs
    """
    # Try to query Celery result backend
    try:
        from celery.result import AsyncResult  # type: ignore[import]
        from tasks.celery_app import celery_app  # type: ignore[import]

        result = AsyncResult(task_id, app=celery_app)

        if result.state == "PENDING":
            return ESGReportStatusResponse(
                task_id=task_id,
                status="pending",
                pdf_url=None,
                message="Report is queued and will be processed shortly.",
            )
        elif result.state == "STARTED" or result.state == "PROGRESS":
            return ESGReportStatusResponse(
                task_id=task_id,
                status="running",
                pdf_url=None,
                message="Report is currently being generated.",
            )
        elif result.state == "SUCCESS":
            task_result = result.result or {}
            pdf_url = task_result.get("pdf_url")
            return ESGReportStatusResponse(
                task_id=task_id,
                status="success",
                pdf_url=pdf_url,
                message="ESG report has been generated successfully.",
            )
        elif result.state == "FAILURE":
            return ESGReportStatusResponse(
                task_id=task_id,
                status="failure",
                pdf_url=None,
                message=f"Report generation failed: {str(result.info)}",
            )
        else:
            return ESGReportStatusResponse(
                task_id=task_id,
                status=result.state.lower(),
                pdf_url=None,
                message=f"Task state: {result.state}",
            )

    except Exception as exc:
        logger.debug("Celery result backend unavailable for task %s: %s", task_id, exc)

    # Fall back to in-memory store
    task_data = _REPORT_TASKS.get(task_id)
    if task_data:
        return ESGReportStatusResponse(
            task_id=task_id,
            status=task_data.get("status", "unknown"),
            pdf_url=task_data.get("pdf_url"),
            message=task_data.get(
                "message",
                "Task status is unknown. Check Celery worker logs.",
            ),
        )

    # Unknown task ID
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=(
            f"Report task {task_id!r} not found. "
            "It may have expired from the result backend."
        ),
    )


# =============================================================
# GET /stats/summary — ESG quick summary
# =============================================================


@router.get(
    "/stats/summary",
    response_model=Dict[str, Any],
    summary="ESG quick statistics summary",
    description=(
        "Returns headline ESG KPIs for the current calendar year: "
        "total CO₂ saved, total waste processed, overall diversion rate, "
        "and carbon record count."
    ),
)
async def esg_stats_summary(
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    """Returns headline ESG statistics for dashboard overview tiles."""

    today = date.today()
    dt_from = _date_to_utc_start(date(today.year, 1, 1))
    dt_to = _date_to_utc_end(today)

    # Carbon YTD
    carbon_stmt = select(
        func.count(CarbonRecord.id).label("count"),
        func.coalesce(func.sum(CarbonRecord.net_carbon_impact_kgco2e), 0).label("net"),
        func.coalesce(func.sum(CarbonRecord.landfill_avoidance_kgco2e), 0).label(
            "landfill"
        ),
        func.coalesce(func.sum(CarbonRecord.recycling_credit_kgco2e), 0).label(
            "recycling"
        ),
        func.coalesce(func.sum(CarbonRecord.wte_credit_kgco2e), 0).label("wte"),
        func.coalesce(func.sum(CarbonRecord.transport_emissions_kgco2e), 0).label(
            "transport"
        ),
    ).where(
        and_(
            CarbonRecord.calculated_at >= dt_from,
            CarbonRecord.calculated_at <= dt_to,
        )
    )
    carbon_result = await db.execute(carbon_stmt)
    carbon_row = carbon_result.one()

    total_savings = (
        float(carbon_row.landfill)
        + float(carbon_row.recycling)
        + float(carbon_row.wte)
        - float(carbon_row.transport)
    )

    # Total waste YTD
    from models.weighbridge import WeighbridgeRecord

    wb_stmt = select(
        func.coalesce(func.sum(WeighbridgeRecord.net_weight_kg), 0).label("total_kg"),
        func.count(WeighbridgeRecord.id).label("record_count"),
    ).where(
        and_(
            WeighbridgeRecord.recorded_at >= dt_from,
            WeighbridgeRecord.recorded_at <= dt_to,
        )
    )
    wb_result = await db.execute(wb_stmt)
    wb_row = wb_result.one()

    # Total recyclable YTD
    from models.recyclable import RecyclableRecord

    rec_stmt = select(
        func.coalesce(func.sum(RecyclableRecord.total_recyclable_kg), 0).label(
            "total_rec"
        ),
    ).where(
        and_(
            RecyclableRecord.recorded_at >= dt_from,
            RecyclableRecord.recorded_at <= dt_to,
        )
    )
    rec_result = await db.execute(rec_stmt)
    rec_row = rec_result.one()

    total_waste = float(wb_row.total_kg)
    total_rec = float(rec_row.total_rec)
    diversion_rate = round(total_rec / total_waste * 100, 2) if total_waste > 0 else 0.0

    return {
        "year": today.year,
        "period": f"{today.year}-01-01 → {today.isoformat()}",
        "carbon": {
            "record_count": carbon_row.count,
            "total_co2_saved_kgco2e": round(total_savings, 4),
            "net_impact_kgco2e": float(carbon_row.net),
            "transport_emissions_kgco2e": float(carbon_row.transport),
            "landfill_avoidance_kgco2e": float(carbon_row.landfill),
            "recycling_credit_kgco2e": float(carbon_row.recycling),
            "wte_credit_kgco2e": float(carbon_row.wte),
        },
        "waste": {
            "total_processed_kg": total_waste,
            "total_recyclable_kg": total_rec,
            "diversion_rate_pct": diversion_rate,
            "weighbridge_record_count": wb_row.record_count,
        },
        "sdg_tags": SDG_TAGS_STANDARD,
    }
