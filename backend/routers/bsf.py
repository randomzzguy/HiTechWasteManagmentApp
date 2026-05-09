# =============================================================
# Hi-Tech Waste Management — BSF (Black Soldier Fly) Router
# Batch management, food waste intake, circularity statistics
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
from models.bsf import (
    BATCH_STATUSES,
    CONTAMINATION_LEVELS,
    BSFBatch,
    BSFBatchCreate,
    BSFBatchListItem,
    BSFBatchRead,
    BSFBatchUpdate,
    BSFCircularityStats,
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
STAFF_ROLES = [
    "superadmin",
    "management",
    "operations_manager",
    "field_supervisor",
    "compliance_officer",
]


# =============================================================
# Helpers
# =============================================================


async def _get_batch_or_404(batch_id: uuid.UUID, db: AsyncSession) -> BSFBatch:
    """Fetch a BSF batch by ID or raise HTTP 404."""
    result = await db.execute(select(BSFBatch).where(BSFBatch.id == batch_id))
    batch = result.scalar_one_or_none()
    if batch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"BSF batch {batch_id} not found",
        )
    return batch


# =============================================================
# GET /batches — list BSF batches
# =============================================================


@router.get(
    "/batches",
    response_model=Dict[str, Any],
    summary="List BSF batches",
    description=(
        "Returns a paginated list of Black Soldier Fly (BSF) bioconversion batches. "
        "Optionally filter by status (active | completed | rejected), "
        "contamination level, and intake date range."
    ),
)
async def list_batches(
    skip: int = Query(default=0, ge=0, description="Number of records to skip"),
    limit: int = Query(default=50, ge=1, le=200, description="Max records to return"),
    status_filter: Optional[str] = Query(
        default=None,
        alias="status",
        description="active | completed | rejected",
    ),
    contamination_level: Optional[str] = Query(
        default=None,
        description="clean | minor | rejected",
    ),
    intake_date_from: Optional[date] = Query(
        default=None,
        description="Filter batches with intake_date on or after this date",
    ),
    intake_date_to: Optional[date] = Query(
        default=None,
        description="Filter batches with intake_date on or before this date",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Returns a paginated list of BSF batches.

    Each batch tracks:
    - Food waste intake quantity and sources
    - Larvae output and conversion ratio
    - Batch start / end dates and status
    - Contamination level of the input food waste
    """
    if status_filter and status_filter not in BATCH_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid status. Must be one of: {sorted(BATCH_STATUSES)}",
        )
    if contamination_level and contamination_level not in CONTAMINATION_LEVELS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid contamination_level. Must be one of: {sorted(CONTAMINATION_LEVELS)}",
        )

    filters: list = []

    if status_filter:
        filters.append(BSFBatch.status == status_filter)
    if contamination_level:
        filters.append(BSFBatch.contamination_level == contamination_level)
    if intake_date_from:
        filters.append(BSFBatch.intake_date >= intake_date_from)
    if intake_date_to:
        filters.append(BSFBatch.intake_date <= intake_date_to)

    base_stmt = select(BSFBatch)
    if filters:
        base_stmt = base_stmt.where(and_(*filters))

    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total_result = await db.execute(count_stmt)
    total: int = total_result.scalar_one()

    stmt = (
        base_stmt.order_by(BSFBatch.intake_date.desc(), BSFBatch.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    batches = result.scalars().all()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": [BSFBatchListItem.model_validate(b) for b in batches],
    }


# =============================================================
# POST /batches — create BSF batch from food waste job
# =============================================================


@router.post(
    "/batches",
    response_model=BSFBatchRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a BSF batch from food waste collection",
    description=(
        "Creates a new BSF bioconversion batch from one or more food waste collection jobs. "
        "Validates that source jobs exist and are of type 'food_waste_bsf' or 'general_collection'."
    ),
    dependencies=[Depends(require_roles(*STAFF_ROLES))],
)
async def create_batch(
    payload: BSFBatchCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> BSFBatchRead:
    """
    Creates a new BSF batch.

    - Validates source job IDs if provided (must exist in jobs table).
    - `batch_start` defaults to `intake_date` if not explicitly provided.
    - `conversion_ratio` is computed automatically when `larvae_output_kg` is set.
    """
    from models.job import Job

    # Validate source jobs if provided
    if payload.source_job_ids:
        for job_id in payload.source_job_ids:
            job_result = await db.execute(select(Job).where(Job.id == job_id))
            job = job_result.scalar_one_or_none()
            if job is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Source job {job_id} not found",
                )
            # Warn but don't block if job type is unexpected
            if job.job_type not in {"food_waste_bsf", "general_collection"}:
                logger.warning(
                    "Source job %s has type '%s' — expected 'food_waste_bsf' or 'general_collection'",
                    job_id,
                    job.job_type,
                )

    # Default batch_start to intake_date if not provided
    batch_start = payload.batch_start or payload.intake_date

    # Build client_sources as list if provided, or normalise
    client_sources_data: Optional[Any] = None
    if payload.client_sources is not None:
        client_sources_data = payload.client_sources

    batch = BSFBatch(
        id=uuid.uuid4(),
        intake_date=payload.intake_date,
        source_job_ids=payload.source_job_ids,
        food_waste_kg=payload.food_waste_kg,
        client_sources=client_sources_data,
        contamination_level=payload.contamination_level,
        larvae_output_kg=None,
        conversion_ratio=None,
        livestock_recipient=payload.livestock_recipient,
        batch_start=batch_start,
        batch_end=None,
        status="active",
        created_at=datetime.now(timezone.utc),
    )
    db.add(batch)
    await db.flush()
    await db.refresh(batch)

    logger.info(
        "BSF batch created id=%s intake_date=%s food_kg=%s by user=%s",
        batch.id,
        batch.intake_date,
        batch.food_waste_kg,
        current_user.get("sub"),
    )
    return BSFBatchRead.from_orm_with_computed(batch)


# =============================================================
# GET /batches/{id} — batch detail
# =============================================================


@router.get(
    "/batches/{batch_id}",
    response_model=BSFBatchRead,
    summary="Get BSF batch detail",
)
async def get_batch(
    batch_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> BSFBatchRead:
    """
    Returns the full details of a single BSF batch including:
    - Food waste input quantity and client sources
    - Larvae output and computed conversion ratio
    - Batch timing and lifecycle status
    - Duration in days (batch_end - batch_start)
    """
    batch = await _get_batch_or_404(batch_id, db)
    return BSFBatchRead.from_orm_with_computed(batch)


# =============================================================
# PATCH /batches/{id} — update batch
# =============================================================


@router.patch(
    "/batches/{batch_id}",
    response_model=BSFBatchRead,
    summary="Update a BSF batch",
    description=(
        "Partially updates a BSF batch. "
        "Typically used to record harvest results: "
        "larvae_output_kg, batch_end, and status → completed/rejected."
    ),
    dependencies=[Depends(require_roles(*STAFF_ROLES))],
)
async def update_batch(
    batch_id: uuid.UUID,
    payload: BSFBatchUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> BSFBatchRead:
    """
    Partially updates a BSF batch.

    Common use cases:
    - **Record harvest**: set `larvae_output_kg`, `batch_end`, `status=completed`
    - **Reject a batch**: set `status=rejected`, `batch_end` to today
    - **Update livestock recipient** after confirmation of sale/transfer
    - **Correct contamination level** if assessment changed

    When `larvae_output_kg` is set and `conversion_ratio` is not explicitly
    provided, the conversion ratio is auto-computed as
    `larvae_output_kg / food_waste_kg`.
    """
    batch = await _get_batch_or_404(batch_id, db)

    # Reject modifications to already-completed/rejected batches (allow correction)
    if batch.status in {"completed", "rejected"} and payload.status not in {
        None,
        "completed",
        "rejected",
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Batch is already in terminal state '{batch.status}'. "
                "Only corrections to the same terminal state are allowed."
            ),
        )

    update_data = payload.model_dump(exclude_unset=True)

    # Auto-compute conversion_ratio if larvae_output_kg is being set
    if "larvae_output_kg" in update_data and "conversion_ratio" not in update_data:
        larvae_kg = update_data["larvae_output_kg"]
        if larvae_kg is not None and batch.food_waste_kg and batch.food_waste_kg > 0:
            update_data["conversion_ratio"] = (
                Decimal(str(larvae_kg)) / Decimal(str(batch.food_waste_kg))
            ).quantize(Decimal("0.0001"))

    # Auto-set batch_end to today when completing/rejecting
    if (
        "status" in update_data
        and update_data["status"] in {"completed", "rejected"}
        and "batch_end" not in update_data
        and batch.batch_end is None
    ):
        update_data["batch_end"] = date.today()

    for field, value in update_data.items():
        setattr(batch, field, value)

    await db.flush()
    await db.refresh(batch)

    logger.info(
        "BSF batch %s updated fields=%s by user=%s",
        batch_id,
        list(update_data.keys()),
        current_user.get("sub"),
    )
    return BSFBatchRead.from_orm_with_computed(batch)


# =============================================================
# DELETE /batches/{id} — soft-delete (reject) a batch
# =============================================================


@router.delete(
    "/batches/{batch_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Delete (reject) a BSF batch",
    dependencies=[Depends(require_roles(*MANAGEMENT_ROLES))],
)
async def delete_batch(
    batch_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> None:
    """
    Soft-deletes a BSF batch by setting its status to 'rejected'.
    Active batches that have not been processed are marked rejected.
    Completed batches with larvae output are not deletable to preserve
    the circularity audit trail.
    """
    batch = await _get_batch_or_404(batch_id, db)

    if (
        batch.status == "completed"
        and batch.larvae_output_kg
        and batch.larvae_output_kg > 0
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Cannot delete a completed batch with recorded larvae output. "
                "This record is part of the circularity audit trail."
            ),
        )

    batch.status = "rejected"
    if batch.batch_end is None:
        batch.batch_end = date.today()

    await db.flush()
    logger.info(
        "BSF batch %s rejected (soft-deleted) by user %s",
        batch_id,
        current_user.get("sub"),
    )


# =============================================================
# GET /stats/circularity — aggregate circularity metrics
# =============================================================


@router.get(
    "/stats/circularity",
    response_model=BSFCircularityStats,
    summary="BSF farm circularity statistics",
    description=(
        "Returns aggregate circularity metrics for the BSF farm: "
        "total food waste processed, total larvae (protein) output, "
        "average conversion ratio, and per-client source breakdowns."
    ),
)
async def circularity_stats(
    date_from: Optional[date] = Query(
        default=None,
        description="Start of the reporting period (inclusive, by intake_date)",
    ),
    date_to: Optional[date] = Query(
        default=None,
        description="End of the reporting period (inclusive, by intake_date)",
    ),
    include_rejected: bool = Query(
        default=False,
        description="Include rejected batches in the aggregation (default: False)",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> BSFCircularityStats:
    """
    Aggregates BSF farm circularity metrics over an optional period.

    Metrics returned:
    - **total_food_waste_kg**        : Total food waste input across all matching batches
    - **total_larvae_output_kg**     : Total protein biomass (prepupae) harvested
    - **average_conversion_ratio**   : Mean larvae_output / food_waste across completed batches
    - **batch_count**                : Total matching batches
    - **completed_batches**          : Batches with status='completed'
    - **rejected_batches**           : Batches with status='rejected'
    - **active_batches**             : Batches still in progress
    - **top_client_sources**         : Top clients by food-waste contribution (sorted descending)

    **Circularity impact interpretation:**
    A 15-20% conversion ratio (industry benchmark) means for every 100 kg of
    food waste processed, 15-20 kg of high-protein animal feed is produced,
    diverting organic waste from landfill and creating a circular economy loop.
    """
    # Build status filter — exclude rejected unless requested
    status_values: List[str] = ["active", "completed"]
    if include_rejected:
        status_values.append("rejected")

    filters: list = [BSFBatch.status.in_(status_values)]

    if date_from:
        filters.append(BSFBatch.intake_date >= date_from)
    if date_to:
        filters.append(BSFBatch.intake_date <= date_to)

    # ── Aggregate totals ──────────────────────────────────────
    agg_stmt = select(
        func.count(BSFBatch.id).label("batch_count"),
        func.coalesce(func.sum(BSFBatch.food_waste_kg), 0).label("total_food_waste_kg"),
        func.coalesce(func.sum(BSFBatch.larvae_output_kg), 0).label("total_larvae_kg"),
        func.coalesce(func.avg(BSFBatch.conversion_ratio), None).label("avg_ratio"),
        # Status counts via conditional aggregation
        func.count(BSFBatch.id)
        .filter(BSFBatch.status == "completed")
        .label("completed"),
        func.count(BSFBatch.id).filter(BSFBatch.status == "rejected").label("rejected"),
        func.count(BSFBatch.id).filter(BSFBatch.status == "active").label("active"),
    ).where(and_(*filters))

    agg_result = await db.execute(agg_stmt)
    agg_row = agg_result.one()

    total_food_waste_kg = Decimal(str(agg_row.total_food_waste_kg))
    total_larvae_kg = Decimal(str(agg_row.total_larvae_kg))
    avg_ratio: Optional[Decimal] = (
        Decimal(str(agg_row.avg_ratio)).quantize(Decimal("0.0001"))
        if agg_row.avg_ratio is not None
        else None
    )

    # ── Top client sources ────────────────────────────────────
    # client_sources is a JSON array:
    # [{"client_id": "uuid", "client_name": "...", "kg": 250.5}, ...]
    # We fetch all batches and aggregate in Python (works for moderate data volumes)
    batches_stmt = select(BSFBatch.client_sources).where(
        and_(
            *filters,
            BSFBatch.client_sources.is_not(None),
        )
    )
    batches_result = await db.execute(batches_stmt)
    all_client_sources = batches_result.scalars().all()

    # Aggregate per-client contributions
    client_totals: Dict[str, Dict[str, Any]] = {}
    for sources in all_client_sources:
        if not isinstance(sources, list):
            continue
        for entry in sources:
            if not isinstance(entry, dict):
                continue
            cid = entry.get("client_id", "unknown")
            cname = entry.get("client_name", "Unknown")
            kg = float(entry.get("kg", 0) or 0)

            if cid not in client_totals:
                client_totals[cid] = {
                    "client_id": cid,
                    "client_name": cname,
                    "total_kg": 0.0,
                    "batch_count": 0,
                }
            client_totals[cid]["total_kg"] += kg
            client_totals[cid]["batch_count"] += 1

    # Sort by total_kg descending, take top 10
    top_clients: List[Dict[str, Any]] = sorted(
        client_totals.values(),
        key=lambda x: x["total_kg"],
        reverse=True,
    )[:10]

    # ── Also compute overall conversion ratio from total data ─
    # (weighted, more accurate than simple average of ratios)
    computed_overall_ratio: Optional[Decimal] = None
    if total_food_waste_kg > 0 and total_larvae_kg > 0:
        computed_overall_ratio = (total_larvae_kg / total_food_waste_kg).quantize(
            Decimal("0.0001")
        )

    return BSFCircularityStats(
        total_food_waste_kg=total_food_waste_kg.quantize(Decimal("0.001")),
        total_larvae_output_kg=total_larvae_kg.quantize(Decimal("0.001")),
        average_conversion_ratio=computed_overall_ratio or avg_ratio,
        batch_count=agg_row.batch_count,
        completed_batches=agg_row.completed,
        rejected_batches=agg_row.rejected,
        active_batches=agg_row.active,
        top_client_sources=top_clients,
    )


# =============================================================
# GET /stats/summary — quick dashboard summary
# =============================================================


@router.get(
    "/stats/summary",
    response_model=Dict[str, Any],
    summary="BSF farm dashboard summary",
    description="Returns key BSF farm KPIs for dashboard tiles.",
)
async def bsf_summary(
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Returns high-level BSF farm KPI tiles:
    - Active batches in progress
    - Total food waste processed (all time)
    - Total larvae output (all time)
    - Average conversion ratio across completed batches
    - Most recent batch info
    """
    # Overall aggregates
    agg_stmt = select(
        func.count(BSFBatch.id).label("total_batches"),
        func.coalesce(func.sum(BSFBatch.food_waste_kg), 0).label("total_food_kg"),
        func.coalesce(func.sum(BSFBatch.larvae_output_kg), 0).label("total_larvae_kg"),
        func.count(BSFBatch.id).filter(BSFBatch.status == "active").label("active"),
        func.count(BSFBatch.id)
        .filter(BSFBatch.status == "completed")
        .label("completed"),
        func.count(BSFBatch.id).filter(BSFBatch.status == "rejected").label("rejected"),
    )
    agg_result = await db.execute(agg_stmt)
    agg = agg_result.one()

    total_food = float(agg.total_food_kg)
    total_larvae = float(agg.total_larvae_kg)
    overall_ratio = (
        round(total_larvae / total_food * 100, 2) if total_food > 0 else None
    )

    # Most recent batch
    recent_stmt = (
        select(BSFBatch)
        .order_by(BSFBatch.intake_date.desc(), BSFBatch.created_at.desc())
        .limit(1)
    )
    recent_result = await db.execute(recent_stmt)
    recent_batch = recent_result.scalar_one_or_none()

    recent_info: Optional[Dict[str, Any]] = None
    if recent_batch:
        recent_info = {
            "id": str(recent_batch.id),
            "intake_date": recent_batch.intake_date.isoformat(),
            "food_waste_kg": float(recent_batch.food_waste_kg),
            "larvae_output_kg": float(recent_batch.larvae_output_kg)
            if recent_batch.larvae_output_kg
            else None,
            "status": recent_batch.status,
            "contamination_level": recent_batch.contamination_level,
        }

    return {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "total_batches": agg.total_batches,
        "active_batches": agg.active,
        "completed_batches": agg.completed,
        "rejected_batches": agg.rejected,
        "total_food_waste_kg": total_food,
        "total_larvae_output_kg": total_larvae,
        "overall_conversion_pct": overall_ratio,
        "most_recent_batch": recent_info,
    }
