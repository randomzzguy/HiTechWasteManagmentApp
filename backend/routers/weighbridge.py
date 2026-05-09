# =============================================================
# Hi-Tech Waste Management — Weighbridge Router
# Records CRUD + tonnage/diversion aggregation stats
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
from models.weighbridge import (
    WeighbridgeCreate,
    WeighbridgeRead,
    WeighbridgeRecord,
    WeighbridgeUpdate,
)
from sqlalchemy import and_, cast, func, select
from sqlalchemy.dialects.postgresql import INTERVAL
from sqlalchemy.ext.asyncio import AsyncSession

from routers.auth import get_current_user, require_roles

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()

# =============================================================
# Helpers
# =============================================================

MANAGEMENT_ROLES = ["superadmin", "management", "operations_manager"]
OPERATOR_ROLES = [
    "superadmin",
    "management",
    "operations_manager",
    "field_supervisor",
    "compliance_officer",
]


async def _get_record_or_404(
    record_id: uuid.UUID, db: AsyncSession
) -> WeighbridgeRecord:
    """Fetch a weighbridge record by id or raise 404."""
    result = await db.execute(
        select(WeighbridgeRecord).where(WeighbridgeRecord.id == record_id)
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Weighbridge record {record_id} not found",
        )
    return record


def _date_to_utc_start(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=timezone.utc)


def _date_to_utc_end(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, 23, 59, 59, 999999, tzinfo=timezone.utc)


# =============================================================
# GET /records  — list weighbridge records
# =============================================================


@router.get(
    "/records",
    response_model=Dict[str, Any],
    summary="List weighbridge records",
    description=(
        "Returns a paginated list of weighbridge records. "
        "Optionally filter by client_id, date_from, date_to, and waste_type."
    ),
)
async def list_records(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=500, description="Max records to return"),
    client_id: Optional[uuid.UUID] = Query(None, description="Filter by client UUID"),
    job_id: Optional[uuid.UUID] = Query(None, description="Filter by job UUID"),
    date_from: Optional[date] = Query(
        None, description="Start date filter (inclusive)"
    ),
    date_to: Optional[date] = Query(None, description="End date filter (inclusive)"),
    waste_type: Optional[str] = Query(
        None,
        description=(
            "Filter by waste_type key in waste_type_breakdown JSON, "
            "e.g. general_waste_kg, recyclable_kg, scheduled_waste_kg"
        ),
    ),
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    """List weighbridge records with optional filters and pagination."""

    filters: list = []

    # Client portal users see only their own records
    if current_user.get("role") == "client":
        from models.client import Client as ClientModel

        client_result = await db.execute(
            select(ClientModel).where(
                ClientModel.portal_user_id == uuid.UUID(current_user["id"])
            )
        )
        client_obj = client_result.scalar_one_or_none()
        if client_obj is None:
            return {"items": [], "total": 0, "skip": skip, "limit": limit}
        filters.append(WeighbridgeRecord.client_id == client_obj.id)
    elif client_id is not None:
        filters.append(WeighbridgeRecord.client_id == client_id)

    if job_id is not None:
        filters.append(WeighbridgeRecord.job_id == job_id)

    if date_from:
        filters.append(WeighbridgeRecord.recorded_at >= _date_to_utc_start(date_from))
    if date_to:
        filters.append(WeighbridgeRecord.recorded_at <= _date_to_utc_end(date_to))

    # Filter by waste_type key existing in JSON with a non-null value
    if waste_type:
        # PostgreSQL: (waste_type_breakdown ->> :key) IS NOT NULL
        filters.append(
            WeighbridgeRecord.waste_type_breakdown[waste_type].as_string() != None  # noqa: E711
        )

    base_stmt = select(WeighbridgeRecord)
    if filters:
        base_stmt = base_stmt.where(and_(*filters))

    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total_result = await db.execute(count_stmt)
    total: int = total_result.scalar_one()

    stmt = (
        base_stmt.order_by(WeighbridgeRecord.recorded_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    records = result.scalars().all()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": [WeighbridgeRead.model_validate(r) for r in records],
    }


# =============================================================
# POST /records  — create weighbridge record
# =============================================================


@router.post(
    "/records",
    response_model=WeighbridgeRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create weighbridge record",
    description=(
        "Creates a new weighbridge measurement. "
        "net_weight_kg is auto-computed from gross - tare if not provided. "
        "Broadcasts a WebSocket event to the 'weighbridge' channel after creation."
    ),
    dependencies=[Depends(require_roles(*OPERATOR_ROLES))],
)
async def create_record(
    payload: WeighbridgeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> WeighbridgeRead:
    """
    Creates a new weighbridge record.

    - `net_weight_kg` is auto-computed as `gross_weight_kg - tare_weight_kg`
      if not explicitly provided (via Pydantic model validator).
    - After a successful INSERT a WebSocket broadcast is attempted to the
      `weighbridge` channel so connected dashboards update in real time.
    """
    recorded_at = payload.recorded_at or datetime.now(timezone.utc)

    # Resolve operator_id from current user if not provided
    operator_id = payload.operator_id or uuid.UUID(current_user["id"])

    record = WeighbridgeRecord(
        id=uuid.uuid4(),
        recorded_at=recorded_at,
        job_id=payload.job_id,
        client_id=payload.client_id,
        gross_weight_kg=payload.gross_weight_kg,
        tare_weight_kg=payload.tare_weight_kg,
        net_weight_kg=payload.net_weight_kg,
        waste_type_breakdown=payload.waste_type_breakdown,
        operator_id=operator_id,
        notes=payload.notes,
    )
    db.add(record)
    await db.flush()
    await db.refresh(record)

    logger.info(
        "WeighbridgeRecord created id=%s net_kg=%s by user=%s",
        record.id,
        record.net_weight_kg,
        current_user["id"],
    )

    # ── WebSocket broadcast ───────────────────────────────────
    try:
        import json

        from websocket.manager import broadcast  # type: ignore[import]

        await broadcast(
            channel="weighbridge",
            data=json.dumps(
                {
                    "event": "new_weighbridge_record",
                    "record_id": str(record.id),
                    "recorded_at": record.recorded_at.isoformat(),
                    "client_id": str(record.client_id) if record.client_id else None,
                    "job_id": str(record.job_id) if record.job_id else None,
                    "net_weight_kg": float(record.net_weight_kg)
                    if record.net_weight_kg is not None
                    else None,
                }
            ),
        )
    except Exception as ws_exc:
        # WebSocket broadcast failure is non-fatal — log and continue
        logger.warning("WebSocket broadcast failed for weighbridge record: %s", ws_exc)

    return WeighbridgeRead.model_validate(record)


# =============================================================
# GET /records/{id}  — get single record
# =============================================================


@router.get(
    "/records/{record_id}",
    response_model=WeighbridgeRead,
    summary="Get a single weighbridge record",
)
async def get_record(
    record_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> WeighbridgeRead:
    """Returns a single weighbridge record by its ID."""
    record = await _get_record_or_404(record_id, db)
    return WeighbridgeRead.model_validate(record)


# =============================================================
# PUT /records/{id}  — update record
# =============================================================


@router.put(
    "/records/{record_id}",
    response_model=WeighbridgeRead,
    summary="Update a weighbridge record",
    dependencies=[Depends(require_roles(*OPERATOR_ROLES))],
)
async def update_record(
    record_id: uuid.UUID,
    payload: WeighbridgeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> WeighbridgeRead:
    """Partially updates a weighbridge record. Re-computes net_weight if needed."""
    record = await _get_record_or_404(record_id, db)

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(record, field, value)

    await db.flush()
    await db.refresh(record)
    return WeighbridgeRead.model_validate(record)


# =============================================================
# DELETE /records/{id}  — delete record
# =============================================================


@router.delete(
    "/records/{record_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Delete a weighbridge record",
    dependencies=[Depends(require_roles(*MANAGEMENT_ROLES))],
)
async def delete_record(
    record_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> None:
    """Hard-deletes a weighbridge record. Management roles only."""
    record = await _get_record_or_404(record_id, db)
    await db.delete(record)
    await db.flush()
    logger.info(
        "WeighbridgeRecord %s deleted by user %s", record_id, current_user["id"]
    )


# =============================================================
# GET /stats/tonnage  — aggregate tonnage
# =============================================================


@router.get(
    "/stats/tonnage",
    response_model=Dict[str, Any],
    summary="Aggregate tonnage statistics",
    description=(
        "Aggregate net tonnage grouped by time period (day/week/month/year) "
        "and optionally by client_id or waste_type key."
    ),
)
async def tonnage_stats(
    group_by: str = Query(
        default="month",
        description="Time granularity: day | week | month | year",
    ),
    client_id: Optional[uuid.UUID] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Returns time-bucketed tonnage totals.

    group_by options:
    - **day**   : daily totals
    - **week**  : ISO week totals
    - **month** : monthly totals (default)
    - **year**  : annual totals

    Each data point includes:
    - `period`        : ISO date string for the bucket start
    - `total_net_kg`  : sum of net_weight_kg
    - `total_gross_kg`: sum of gross_weight_kg
    - `record_count`  : number of weighbridge readings in the period
    """
    valid_group = {"day", "week", "month", "year"}
    if group_by not in valid_group:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"group_by must be one of: {sorted(valid_group)}",
        )

    # Map group_by to PostgreSQL date_trunc argument
    trunc_map = {"day": "day", "week": "week", "month": "month", "year": "year"}
    trunc_key = trunc_map[group_by]

    filters: list = []
    if client_id:
        filters.append(WeighbridgeRecord.client_id == client_id)
    if date_from:
        filters.append(WeighbridgeRecord.recorded_at >= _date_to_utc_start(date_from))
    if date_to:
        filters.append(WeighbridgeRecord.recorded_at <= _date_to_utc_end(date_to))

    period_expr = func.date_trunc(trunc_key, WeighbridgeRecord.recorded_at).label(
        "period"
    )

    stmt = (
        select(
            period_expr,
            func.coalesce(func.sum(WeighbridgeRecord.net_weight_kg), 0).label(
                "total_net_kg"
            ),
            func.coalesce(func.sum(WeighbridgeRecord.gross_weight_kg), 0).label(
                "total_gross_kg"
            ),
            func.count(WeighbridgeRecord.id).label("record_count"),
        )
        .group_by(period_expr)
        .order_by(period_expr)
    )

    if filters:
        stmt = stmt.where(and_(*filters))

    result = await db.execute(stmt)
    rows = result.all()

    data_points = [
        {
            "period": row.period.isoformat() if row.period else None,
            "total_net_kg": float(row.total_net_kg),
            "total_gross_kg": float(row.total_gross_kg),
            "record_count": row.record_count,
        }
        for row in rows
    ]

    # Summary totals
    total_net = sum(p["total_net_kg"] for p in data_points)
    total_gross = sum(p["total_gross_kg"] for p in data_points)
    total_records = sum(p["record_count"] for p in data_points)

    # Per-client breakdown if no specific client filter
    client_breakdown: List[Dict[str, Any]] = []
    if client_id is None:
        client_stmt = (
            select(
                WeighbridgeRecord.client_id,
                func.coalesce(func.sum(WeighbridgeRecord.net_weight_kg), 0).label(
                    "total_net_kg"
                ),
                func.count(WeighbridgeRecord.id).label("record_count"),
            )
            .group_by(WeighbridgeRecord.client_id)
            .order_by(
                func.coalesce(func.sum(WeighbridgeRecord.net_weight_kg), 0).desc()
            )
            .limit(10)
        )
        if date_from:
            client_stmt = client_stmt.where(
                WeighbridgeRecord.recorded_at >= _date_to_utc_start(date_from)
            )
        if date_to:
            client_stmt = client_stmt.where(
                WeighbridgeRecord.recorded_at <= _date_to_utc_end(date_to)
            )
        client_result = await db.execute(client_stmt)
        client_breakdown = [
            {
                "client_id": str(row.client_id) if row.client_id else None,
                "total_net_kg": float(row.total_net_kg),
                "record_count": row.record_count,
            }
            for row in client_result.all()
        ]

    return {
        "group_by": group_by,
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": date_to.isoformat() if date_to else None,
        "client_id": str(client_id) if client_id else None,
        "summary": {
            "total_net_kg": total_net,
            "total_gross_kg": total_gross,
            "total_record_count": total_records,
        },
        "time_series": data_points,
        "by_client": client_breakdown,
    }


# =============================================================
# GET /stats/diversion  — diversion rate
# =============================================================


@router.get(
    "/stats/diversion",
    response_model=Dict[str, Any],
    summary="Calculate waste diversion rate",
    description=(
        "Computes the diversion rate as: "
        "(recyclable_kg + diverted_kg) / total_net_kg × 100. "
        "Uses waste_type_breakdown JSON keys to identify recycled and diverted streams."
    ),
)
async def diversion_stats(
    client_id: Optional[uuid.UUID] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    group_by: str = Query(
        default="month",
        description="Time granularity: day | week | month | year",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Computes diversion rate over a date range.

    **Diversion formula:**
        diversion_rate = (recyclable_kg + bsf_kg + sw_disposed_kg) / total_net_kg × 100

    The calculation uses the `waste_type_breakdown` JSON column to identify
    the recyclable, BSF (food waste bioconversion), and scheduled-waste streams.

    Returns both the overall rate and a time-series breakdown.
    """
    from models.recyclable import RecyclableRecord

    valid_group = {"day", "week", "month", "year"}
    if group_by not in valid_group:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"group_by must be one of: {sorted(valid_group)}",
        )

    trunc_key = group_by  # date_trunc accepts these directly

    wb_filters: list = []
    rec_filters: list = []

    if client_id:
        wb_filters.append(WeighbridgeRecord.client_id == client_id)
        rec_filters.append(RecyclableRecord.client_id == client_id)

    if date_from:
        wb_filters.append(
            WeighbridgeRecord.recorded_at >= _date_to_utc_start(date_from)
        )
        rec_filters.append(
            RecyclableRecord.recorded_at >= _date_to_utc_start(date_from)
        )
    if date_to:
        wb_filters.append(WeighbridgeRecord.recorded_at <= _date_to_utc_end(date_to))
        rec_filters.append(RecyclableRecord.recorded_at <= _date_to_utc_end(date_to))

    # ── Total waste tonnage (weighbridge) ─────────────────────
    wb_stmt = select(
        func.coalesce(func.sum(WeighbridgeRecord.net_weight_kg), 0).label(
            "total_net_kg"
        ),
        func.count(WeighbridgeRecord.id).label("record_count"),
    )
    if wb_filters:
        wb_stmt = wb_stmt.where(and_(*wb_filters))

    wb_result = await db.execute(wb_stmt)
    wb_row = wb_result.one()
    total_net_kg = Decimal(str(wb_row.total_net_kg))

    # ── Recyclable tonnage ────────────────────────────────────
    rec_stmt = select(
        func.coalesce(func.sum(RecyclableRecord.total_recyclable_kg), 0).label(
            "total_recyclable_kg"
        ),
    )
    if rec_filters:
        rec_stmt = rec_stmt.where(and_(*rec_filters))

    rec_result = await db.execute(rec_stmt)
    rec_row = rec_result.one()
    total_recyclable_kg = Decimal(str(rec_row.total_recyclable_kg))

    # ── Scheduled waste diverted ──────────────────────────────
    from models.scheduled_waste import ScheduledWasteBatch

    sw_filters: list = [ScheduledWasteBatch.status.in_(["dispatched", "processed"])]
    if client_id:
        sw_filters.append(ScheduledWasteBatch.client_id == client_id)

    sw_stmt = select(
        func.coalesce(func.sum(ScheduledWasteBatch.quantity_kg), 0).label("total_sw_kg")
    ).where(and_(*sw_filters))
    sw_result = await db.execute(sw_stmt)
    sw_row = sw_result.one()
    total_sw_diverted_kg = Decimal(str(sw_row.total_sw_kg))

    # ── Overall diversion rate ────────────────────────────────
    total_diverted_kg = total_recyclable_kg + total_sw_diverted_kg
    overall_diversion_rate: Optional[Decimal] = None
    if total_net_kg > 0:
        overall_diversion_rate = (total_diverted_kg / total_net_kg * 100).quantize(
            Decimal("0.01")
        )

    # ── Time-series diversion rate ────────────────────────────
    period_expr = func.date_trunc(trunc_key, WeighbridgeRecord.recorded_at).label(
        "period"
    )
    wb_ts_stmt = (
        select(
            period_expr,
            func.coalesce(func.sum(WeighbridgeRecord.net_weight_kg), 0).label(
                "total_net_kg"
            ),
        )
        .group_by(period_expr)
        .order_by(period_expr)
    )
    if wb_filters:
        wb_ts_stmt = wb_ts_stmt.where(and_(*wb_filters))

    wb_ts_result = await db.execute(wb_ts_stmt)
    wb_ts_rows = wb_ts_result.all()

    rec_period_expr = func.date_trunc(trunc_key, RecyclableRecord.recorded_at).label(
        "period"
    )
    rec_ts_stmt = (
        select(
            rec_period_expr,
            func.coalesce(func.sum(RecyclableRecord.total_recyclable_kg), 0).label(
                "total_recyclable_kg"
            ),
        )
        .group_by(rec_period_expr)
        .order_by(rec_period_expr)
    )
    if rec_filters:
        rec_ts_stmt = rec_ts_stmt.where(and_(*rec_filters))

    rec_ts_result = await db.execute(rec_ts_stmt)
    rec_ts_rows = rec_ts_result.all()

    # Merge time series on period key
    wb_dict: Dict[str, float] = {
        row.period.isoformat(): float(row.total_net_kg)
        for row in wb_ts_rows
        if row.period
    }
    rec_dict: Dict[str, float] = {
        row.period.isoformat(): float(row.total_recyclable_kg)
        for row in rec_ts_rows
        if row.period
    }

    all_periods = sorted(set(list(wb_dict.keys()) + list(rec_dict.keys())))
    time_series: List[Dict[str, Any]] = []
    for period in all_periods:
        net = wb_dict.get(period, 0.0)
        recyclable = rec_dict.get(period, 0.0)
        diverted = recyclable  # simplified; add SW breakdown per period if needed
        rate = (diverted / net * 100) if net > 0 else 0.0
        time_series.append(
            {
                "period": period,
                "total_net_kg": net,
                "diverted_kg": diverted,
                "recyclable_kg": recyclable,
                "diversion_rate_pct": round(rate, 2),
            }
        )

    return {
        "client_id": str(client_id) if client_id else None,
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": date_to.isoformat() if date_to else None,
        "group_by": group_by,
        "summary": {
            "total_net_kg": float(total_net_kg),
            "total_recyclable_kg": float(total_recyclable_kg),
            "total_sw_diverted_kg": float(total_sw_diverted_kg),
            "total_diverted_kg": float(total_diverted_kg),
            "overall_diversion_rate_pct": float(overall_diversion_rate)
            if overall_diversion_rate is not None
            else None,
            "record_count": wb_row.record_count,
        },
        "time_series": time_series,
    }
