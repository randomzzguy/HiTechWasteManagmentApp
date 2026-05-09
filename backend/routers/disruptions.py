# =============================================================
# Hi-Tech Waste Management — Disruptions Router
# Operational disruption log: creation, job impact, resolution.
# =============================================================

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from database import get_db
from fastapi import APIRouter, Depends, HTTPException, Query, status
from models.disruption import (
    DISRUPTION_STATUSES,
    DISRUPTION_TYPES,
    DisruptionClosure,
    DisruptionJobImpact,
    DisruptionJobImpactRead,
    DisruptionLog,
    DisruptionLogCreate,
    DisruptionLogRead,
    DisruptionLogUpdate,
    ResolutionUpdate,
)
from models.user import User
from models.vehicle import Vehicle
from routers.auth import get_current_user, require_roles
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.get("/", response_model=List[DisruptionLogRead])
async def list_disruptions(
    status: Optional[str] = Query(None),
    disruption_type: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List disruption logs with optional filters."""
    q = select(DisruptionLog)
    if status:
        q = q.where(DisruptionLog.status == status)
    if disruption_type:
        q = q.where(DisruptionLog.disruption_type == disruption_type)
    if date_from:
        q = q.where(DisruptionLog.occurred_at >= date_from)
    if date_to:
        q = q.where(DisruptionLog.occurred_at <= date_to)
    q = q.order_by(DisruptionLog.occurred_at.desc())
    result = await db.execute(q)
    return result.scalars().all()


@router.post(
    "/",
    response_model=DisruptionLogRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_disruption(
    payload: DisruptionLogCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Log an operational disruption. Roles: superadmin, operations_manager,
    field_supervisor, driver.
    """
    allowed_roles = {"superadmin", "operations_manager", "field_supervisor", "driver"}
    if current_user.role not in allowed_roles:
        raise HTTPException(
            status_code=403,
            detail=f"Role '{current_user.role}' is not permitted to create disruption logs",
        )

    if payload.disruption_type not in DISRUPTION_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"disruption_type must be one of {sorted(DISRUPTION_TYPES)}",
        )

    # Vehicle breakdown requires vehicle_id
    if payload.disruption_type == "vehicle_breakdown" and not payload.vehicle_id:
        raise HTTPException(
            status_code=422,
            detail="vehicle_id is required for vehicle_breakdown disruptions",
        )

    # Highway restriction requires highway_name and time window
    if payload.disruption_type == "highway_restriction":
        if not payload.highway_name:
            raise HTTPException(
                status_code=422,
                detail="highway_name is required for highway_restriction disruptions",
            )
        if not payload.restriction_start_time or not payload.restriction_end_time:
            raise HTTPException(
                status_code=422,
                detail="restriction_start_time and restriction_end_time are required for highway_restriction",
            )

    disruption = DisruptionLog(
        disruption_type=payload.disruption_type,
        occurred_at=payload.occurred_at or datetime.now(timezone.utc),
        reported_by=current_user.id,
        description=payload.description,
        affected_job_ids=[str(j) for j in payload.affected_job_ids],
        vehicle_id=payload.vehicle_id,
        highway_name=payload.highway_name,
        restriction_start_time=payload.restriction_start_time,
        restriction_end_time=payload.restriction_end_time,
        status="open",
        severity="warning",
        resolution_history=[],
    )
    db.add(disruption)
    await db.flush()

    # Auto-set vehicle to maintenance for breakdowns
    if payload.disruption_type == "vehicle_breakdown" and payload.vehicle_id:
        vehicle = await db.get(Vehicle, payload.vehicle_id)
        if vehicle:
            vehicle.status = "maintenance"

    # Create job impact records
    if payload.job_impacts:
        for impact_input in payload.job_impacts:
            impact = DisruptionJobImpact(
                disruption_id=disruption.id,
                job_id=impact_input.job_id,
                estimated_delay_minutes=impact_input.estimated_delay_minutes,
                original_scheduled_completion=impact_input.original_scheduled_completion,
                revised_estimated_completion=impact_input.revised_estimated_completion,
                notes=impact_input.notes,
            )
            db.add(impact)

    await db.flush()
    await db.refresh(disruption)
    return disruption


@router.get("/{disruption_id}", response_model=DisruptionLogRead)
async def get_disruption(
    disruption_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    disruption = await db.get(DisruptionLog, disruption_id)
    if not disruption:
        raise HTTPException(status_code=404, detail="Disruption log not found")
    return disruption


@router.patch(
    "/{disruption_id}",
    response_model=DisruptionLogRead,
    dependencies=[Depends(require_roles("superadmin", "operations_manager"))],
)
async def update_disruption(
    disruption_id: uuid.UUID,
    payload: DisruptionLogUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Assign a resolver or update severity."""
    disruption = await db.get(DisruptionLog, disruption_id)
    if not disruption:
        raise HTTPException(status_code=404, detail="Disruption log not found")
    if disruption.status == "resolved":
        raise HTTPException(status_code=409, detail="Disruption is already resolved")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(disruption, field, value)

    await db.flush()
    await db.refresh(disruption)
    return disruption


@router.post(
    "/{disruption_id}/resolution-update",
    response_model=DisruptionLogRead,
)
async def add_resolution_update(
    disruption_id: uuid.UUID,
    payload: ResolutionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Resolver submits a progress update on an open disruption."""
    disruption = await db.get(DisruptionLog, disruption_id)
    if not disruption:
        raise HTTPException(status_code=404, detail="Disruption log not found")
    if disruption.status == "resolved":
        raise HTTPException(status_code=409, detail="Disruption is already resolved")

    history = disruption.resolution_history or []
    history.append(
        {
            "text": payload.update_text,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "resolver_id": str(current_user.id),
        }
    )
    disruption.resolution_history = history
    await db.flush()
    await db.refresh(disruption)
    return disruption


@router.post(
    "/{disruption_id}/close",
    response_model=DisruptionLogRead,
    dependencies=[Depends(require_roles("superadmin", "operations_manager"))],
)
async def close_disruption(
    disruption_id: uuid.UUID,
    payload: DisruptionClosure,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Close a disruption with a formal closure note."""
    disruption = await db.get(DisruptionLog, disruption_id)
    if not disruption:
        raise HTTPException(status_code=404, detail="Disruption log not found")
    if disruption.status == "resolved":
        raise HTTPException(status_code=409, detail="Disruption is already resolved")

    # Vehicle breakdown requires confirmation that vehicle status was updated
    if disruption.disruption_type == "vehicle_breakdown":
        if not payload.vehicle_status_updated:
            raise HTTPException(
                status_code=422,
                detail="vehicle_status_updated must be True before closing a vehicle_breakdown disruption",
            )

    disruption.status = "resolved"
    disruption.closure_note = payload.closure_note
    disruption.closed_at = datetime.now(timezone.utc)
    disruption.closed_by = current_user.id

    await db.flush()
    await db.refresh(disruption)
    return disruption


@router.get("/{disruption_id}/impact", response_model=List[DisruptionJobImpactRead])
async def get_disruption_impact(
    disruption_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all job impacts for a disruption."""
    q = select(DisruptionJobImpact).where(
        DisruptionJobImpact.disruption_id == disruption_id
    )
    result = await db.execute(q)
    return result.scalars().all()
