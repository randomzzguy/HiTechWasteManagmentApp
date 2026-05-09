# =============================================================
# Hi-Tech Waste Management — Equipment Router
# Compaction machines: registry, deployments, maintenance.
# Containers: inventory, fill-level, pickup triggers, transport.
# =============================================================

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

from database import get_db
from fastapi import APIRouter, Depends, HTTPException, Query, status
from models.equipment import (
    COMPACTOR_STATUSES,
    CONTAINER_STATUSES,
    CONTAINER_TYPES,
    CompactionMachine,
    CompactionMachineCreate,
    CompactionMachineRead,
    CompactionMachineUpdate,
    CompactorDeployment,
    CompactorDeploymentCreate,
    CompactorDeploymentRead,
    CompactorMaintenanceLog,
    CompactorMaintenanceLogCreate,
    CompactorMaintenanceLogRead,
    Container,
    ContainerAssignSite,
    ContainerFillReading,
    ContainerRead,
    ContainerTransportLog,
    ContainerTransportUpdate,
    FillLevelUpdate,
    FillReadingRead,
    PickupTrigger,
    PickupTriggerRead,
)
from models.job import Job
from models.user import User
from routers.auth import get_current_user, require_roles
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()

# =============================================================
# Compaction Machine Endpoints
# =============================================================


@router.get("/compactors", response_model=List[CompactionMachineRead])
async def list_compactors(
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all compaction machines, optionally filtered by status."""
    q = select(CompactionMachine)
    if status:
        q = q.where(CompactionMachine.status == status)
    q = q.order_by(CompactionMachine.asset_tag)
    result = await db.execute(q)
    return result.scalars().all()


@router.post(
    "/compactors",
    response_model=CompactionMachineRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles("superadmin", "operations_manager"))],
)
async def create_compactor(
    payload: CompactionMachineCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Register a new compaction machine."""
    if payload.status if hasattr(payload, "status") else None:
        if payload.status not in COMPACTOR_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"status must be one of {sorted(COMPACTOR_STATUSES)}",
            )
    machine = CompactionMachine(**payload.model_dump())
    db.add(machine)
    await db.flush()
    await db.refresh(machine)
    return machine


@router.get("/compactors/due-service", response_model=List[CompactionMachineRead])
async def list_due_service(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return compaction machines with service due within 30 days."""
    today = date.today()
    cutoff = today + timedelta(days=30)
    q = (
        select(CompactionMachine)
        .where(
            and_(
                CompactionMachine.next_service_date <= cutoff,
                CompactionMachine.status != "decommissioned",
            )
        )
        .order_by(CompactionMachine.next_service_date)
    )
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/compactors/{machine_id}", response_model=CompactionMachineRead)
async def get_compactor(
    machine_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    machine = await db.get(CompactionMachine, machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail="Compaction machine not found")
    return machine


@router.patch(
    "/compactors/{machine_id}",
    response_model=CompactionMachineRead,
    dependencies=[Depends(require_roles("superadmin", "operations_manager"))],
)
async def update_compactor(
    machine_id: uuid.UUID,
    payload: CompactionMachineUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    machine = await db.get(CompactionMachine, machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail="Compaction machine not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(machine, field, value)
    await db.flush()
    await db.refresh(machine)
    return machine


# ── Deployments ───────────────────────────────────────────────


@router.get(
    "/compactors/{machine_id}/deployments",
    response_model=List[CompactorDeploymentRead],
)
async def list_deployments(
    machine_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return full deployment history for a compaction machine."""
    q = (
        select(CompactorDeployment)
        .where(CompactorDeployment.machine_id == machine_id)
        .order_by(CompactorDeployment.deployment_start.desc())
    )
    result = await db.execute(q)
    return result.scalars().all()


@router.post(
    "/compactors/{machine_id}/deployments",
    response_model=CompactorDeploymentRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles("superadmin", "operations_manager"))],
)
async def deploy_compactor(
    machine_id: uuid.UUID,
    payload: CompactorDeploymentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Deploy a compaction machine to a client site."""
    machine = await db.get(CompactionMachine, machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail="Compaction machine not found")
    if machine.status == "deployed":
        # Find current deployment for error message
        q = select(CompactorDeployment).where(
            and_(
                CompactorDeployment.machine_id == machine_id,
                CompactorDeployment.deployment_end.is_(None),
            )
        )
        result = await db.execute(q)
        current = result.scalar_one_or_none()
        site = current.site_address if current else "unknown site"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Machine is already deployed at: {site}",
        )

    deployment = CompactorDeployment(
        machine_id=machine_id,
        authorised_by=current_user.id,
        **payload.model_dump(),
    )
    machine.status = "deployed"
    db.add(deployment)
    await db.flush()
    await db.refresh(deployment)
    return deployment


@router.post(
    "/compactors/{machine_id}/deployments/{deployment_id}/retrieve",
    response_model=CompactorDeploymentRead,
    dependencies=[Depends(require_roles("superadmin", "operations_manager"))],
)
async def retrieve_compactor(
    machine_id: uuid.UUID,
    deployment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a compaction machine as retrieved from a client site."""
    deployment = await db.get(CompactorDeployment, deployment_id)
    if not deployment or deployment.machine_id != machine_id:
        raise HTTPException(status_code=404, detail="Deployment not found")
    if deployment.deployment_end:
        raise HTTPException(status_code=409, detail="Deployment already closed")

    deployment.deployment_end = date.today()
    machine = await db.get(CompactionMachine, machine_id)
    if machine:
        machine.status = "available"
    await db.flush()
    await db.refresh(deployment)
    return deployment


# ── Maintenance Logs ──────────────────────────────────────────


@router.get(
    "/compactors/{machine_id}/maintenance",
    response_model=List[CompactorMaintenanceLogRead],
)
async def list_maintenance_logs(
    machine_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = (
        select(CompactorMaintenanceLog)
        .where(CompactorMaintenanceLog.machine_id == machine_id)
        .order_by(CompactorMaintenanceLog.service_date.desc())
    )
    result = await db.execute(q)
    return result.scalars().all()


@router.post(
    "/compactors/{machine_id}/maintenance",
    response_model=CompactorMaintenanceLogRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles("superadmin", "operations_manager"))],
)
async def log_maintenance(
    machine_id: uuid.UUID,
    payload: CompactorMaintenanceLogCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Record a maintenance service event and update next service date."""
    machine = await db.get(CompactionMachine, machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail="Compaction machine not found")

    log = CompactorMaintenanceLog(
        machine_id=machine_id,
        logged_by=current_user.id,
        **payload.model_dump(),
    )
    db.add(log)

    # Update machine service dates
    machine.last_service_date = payload.service_date
    machine.next_service_date = payload.service_date + timedelta(
        days=machine.maintenance_interval_days
    )
    if machine.status == "maintenance":
        machine.status = "available"

    await db.flush()
    await db.refresh(log)
    return log


# =============================================================
# Container Endpoints
# =============================================================


@router.get("/containers", response_model=List[ContainerRead])
async def list_containers(
    status: Optional[str] = Query(None),
    client_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all containers with optional filters."""
    q = select(Container)
    if status:
        q = q.where(Container.status == status)
    if client_id:
        q = q.where(Container.current_client_id == client_id)
    q = q.order_by(Container.container_code)
    result = await db.execute(q)
    return result.scalars().all()


@router.post(
    "/containers",
    response_model=ContainerRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles("superadmin", "operations_manager"))],
)
async def create_container(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from models.equipment import ContainerCreate
    data = ContainerCreate(**payload)
    if data.container_type not in CONTAINER_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"container_type must be one of {sorted(CONTAINER_TYPES)}",
        )
    container = Container(**data.model_dump())
    db.add(container)
    await db.flush()
    await db.refresh(container)
    return container


@router.get("/containers/{container_id}", response_model=ContainerRead)
async def get_container(
    container_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    container = await db.get(Container, container_id)
    if not container:
        raise HTTPException(status_code=404, detail="Container not found")
    return container


@router.post(
    "/containers/{container_id}/assign-site",
    response_model=ContainerRead,
    dependencies=[Depends(require_roles("superadmin", "operations_manager"))],
)
async def assign_container_to_site(
    container_id: uuid.UUID,
    payload: ContainerAssignSite,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Assign a container to a client site."""
    container = await db.get(Container, container_id)
    if not container:
        raise HTTPException(status_code=404, detail="Container not found")
    if container.status != "available":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Container is not available. Current status: {container.status} at {container.current_site_address}",
        )

    container.current_client_id = payload.client_id
    container.current_site_address = payload.site_address
    container.current_compactor_id = payload.compactor_id
    container.target_material_type = payload.target_material_type
    container.assigned_date = payload.assigned_date or date.today()
    container.status = "at_site"
    container.fill_level = 0

    # Log transport transition
    log = ContainerTransportLog(
        container_id=container_id,
        from_status="available",
        to_status="at_site",
        responsible_user_id=current_user.id,
    )
    db.add(log)
    await db.flush()
    await db.refresh(container)
    return container


@router.post(
    "/containers/{container_id}/fill-level",
    response_model=FillReadingRead,
    status_code=status.HTTP_201_CREATED,
)
async def update_fill_level(
    container_id: uuid.UUID,
    payload: FillLevelUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Record a fill-level reading. Auto-creates pickup trigger at threshold."""
    container = await db.get(Container, container_id)
    if not container:
        raise HTTPException(status_code=404, detail="Container not found")

    reading = ContainerFillReading(
        container_id=container_id,
        fill_level=payload.fill_level,
        reported_by=current_user.id,
        photo_url=payload.photo_url,
        notes=payload.notes,
    )
    db.add(reading)

    # Update current fill level on container
    container.fill_level = payload.fill_level

    # Auto-create pickup trigger if threshold reached and no active trigger
    if payload.fill_level >= container.pickup_threshold:
        active_trigger_q = select(PickupTrigger).where(
            and_(
                PickupTrigger.container_id == container_id,
                PickupTrigger.is_active == True,
            )
        )
        result = await db.execute(active_trigger_q)
        existing = result.scalar_one_or_none()
        if not existing:
            trigger = PickupTrigger(
                container_id=container_id,
                fill_level_at_trigger=payload.fill_level,
            )
            db.add(trigger)

    await db.flush()
    await db.refresh(reading)
    return reading


@router.get(
    "/containers/{container_id}/fill-history",
    response_model=List[FillReadingRead],
)
async def get_fill_history(
    container_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = (
        select(ContainerFillReading)
        .where(ContainerFillReading.container_id == container_id)
        .order_by(ContainerFillReading.recorded_at.desc())
    )
    result = await db.execute(q)
    return result.scalars().all()


@router.get(
    "/containers/{container_id}/transport-log",
    response_model=List[dict],
)
async def get_transport_log(
    container_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = (
        select(ContainerTransportLog)
        .where(ContainerTransportLog.container_id == container_id)
        .order_by(ContainerTransportLog.transitioned_at.desc())
    )
    result = await db.execute(q)
    logs = result.scalars().all()
    return [
        {
            "id": str(log.id),
            "from_status": log.from_status,
            "to_status": log.to_status,
            "transitioned_at": log.transitioned_at.isoformat(),
            "responsible_user_id": str(log.responsible_user_id) if log.responsible_user_id else None,
            "vehicle_id": str(log.vehicle_id) if log.vehicle_id else None,
            "notes": log.notes,
        }
        for log in logs
    ]


@router.post(
    "/containers/{container_id}/transport",
    response_model=ContainerRead,
)
async def update_container_transport_status(
    container_id: uuid.UUID,
    payload: ContainerTransportUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Driver updates container status during transport."""
    container = await db.get(Container, container_id)
    if not container:
        raise HTTPException(status_code=404, detail="Container not found")

    allowed_transitions = {
        "at_site": ["in_transit"],
        "in_transit": ["at_recycler"],
        "at_recycler": ["available"],
    }
    valid_next = allowed_transitions.get(container.status, [])
    if payload.to_status not in valid_next:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot transition from '{container.status}' to '{payload.to_status}'",
        )

    log = ContainerTransportLog(
        container_id=container_id,
        from_status=container.status,
        to_status=payload.to_status,
        responsible_user_id=current_user.id,
        vehicle_id=payload.vehicle_id,
        notes=payload.notes,
    )
    db.add(log)

    container.status = payload.to_status

    # If returned to available, reset fill level and close active triggers
    if payload.to_status == "available":
        container.fill_level = 0
        container.current_client_id = None
        container.current_site_address = None
        container.current_compactor_id = None
        # Close active pickup triggers
        trigger_q = select(PickupTrigger).where(
            and_(
                PickupTrigger.container_id == container_id,
                PickupTrigger.is_active == True,
            )
        )
        result = await db.execute(trigger_q)
        for trigger in result.scalars().all():
            trigger.is_active = False
            trigger.closed_at = datetime.now(timezone.utc)

    await db.flush()
    await db.refresh(container)
    return container


@router.post(
    "/containers/{container_id}/pickup-triggers/{trigger_id}/acknowledge",
    response_model=PickupTriggerRead,
    dependencies=[Depends(require_roles("superadmin", "operations_manager"))],
)
async def acknowledge_pickup_trigger(
    container_id: uuid.UUID,
    trigger_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Acknowledge a pickup trigger and create a collection job."""
    trigger = await db.get(PickupTrigger, trigger_id)
    if not trigger or trigger.container_id != container_id:
        raise HTTPException(status_code=404, detail="Pickup trigger not found")
    if not trigger.is_active:
        raise HTTPException(status_code=409, detail="Trigger already closed")

    container = await db.get(Container, container_id)

    # Create a general_collection job
    import random
    job_number = f"JOB-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
    job = Job(
        job_number=job_number,
        client_id=container.current_client_id,
        job_type="general_collection",
        status="confirmed",
        collection_address=container.current_site_address,
        notes=f"Container pickup triggered: {container.container_code} at {container.fill_level}% fill",
        created_by=current_user.id,
    )
    db.add(job)
    await db.flush()

    trigger.acknowledged_at = datetime.now(timezone.utc)
    trigger.acknowledged_by = current_user.id
    trigger.linked_job_id = job.id

    await db.flush()
    await db.refresh(trigger)
    return trigger
