# =============================================================
# Hi-Tech Waste Management — Compliance Router
# Scheduled Waste batch management, consignment notes, deadline alerts
# =============================================================

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from config import get_settings
from database import get_db
from fastapi import APIRouter, Depends, HTTPException, Query, status
from models.scheduled_waste import (
    BATCH_STATUSES,
    CN_STATUSES,
    ConsignmentNote,
    ConsignmentNoteCreate,
    ConsignmentNoteRead,
    ScheduledWasteBatch,
    ScheduledWasteBatchCreate,
    ScheduledWasteBatchRead,
    ScheduledWasteBatchStatusUpdate,
    ScheduledWasteBatchUpdate,
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

COMPLIANCE_ROLES = [
    "superadmin",
    "management",
    "operations_manager",
    "compliance_officer",
]
ALL_STAFF = [
    "superadmin",
    "management",
    "operations_manager",
    "field_supervisor",
    "compliance_officer",
]

# =============================================================
# In-memory SW Code library (seed data)
# In production this should be loaded from DB or a config file.
# =============================================================

SW_CODE_LIBRARY: List[Dict[str, Any]] = [
    {
        "sw_code": "SW 102",
        "description": "Waste that contains cyanide",
        "examples": "Cyanide plating bath, cyanide stripping solution",
        "physical_state": "liquid",
        "category": "inorganic",
    },
    {
        "sw_code": "SW 104",
        "description": "Waste that contains mercury or mercury compounds",
        "examples": "Mercury-contaminated equipment, fluorescent lamps",
        "physical_state": "solid",
        "category": "inorganic",
    },
    {
        "sw_code": "SW 204",
        "description": "Waste mineral oil/water mixtures or emulsions",
        "examples": "Cutting fluids, rolling emulsions",
        "physical_state": "liquid",
        "category": "organic",
    },
    {
        "sw_code": "SW 305",
        "description": "Used lubricating oil",
        "examples": "Used engine oil, hydraulic oil, gear oil",
        "physical_state": "liquid",
        "category": "organic",
    },
    {
        "sw_code": "SW 306",
        "description": "Waste fuel (petrol, diesel, fuel oil, spent fuel)",
        "examples": "Off-spec fuel, contaminated diesel",
        "physical_state": "liquid",
        "category": "organic",
    },
    {
        "sw_code": "SW 322",
        "description": "Waste that contains polychlorinated biphenyls (PCBs)",
        "examples": "PCB-containing transformers, capacitors",
        "physical_state": "solid",
        "category": "organic",
    },
    {
        "sw_code": "SW 401",
        "description": "Clinical waste",
        "examples": "Sharps, pathological waste, contaminated dressings",
        "physical_state": "solid",
        "category": "clinical",
    },
    {
        "sw_code": "SW 408",
        "description": "Asbestos waste",
        "examples": "Asbestos-containing materials, insulation",
        "physical_state": "solid",
        "category": "inorganic",
    },
    {
        "sw_code": "SW 409",
        "description": "Used tyres",
        "examples": "End-of-life tyres from vehicles",
        "physical_state": "solid",
        "category": "organic",
    },
    {
        "sw_code": "SW 410",
        "description": "Batteries",
        "examples": "Lead-acid batteries, lithium batteries, NiCd batteries",
        "physical_state": "solid",
        "category": "inorganic",
    },
    {
        "sw_code": "SW 420",
        "description": "Electronic waste",
        "examples": "Computers, phones, circuit boards, CRT monitors",
        "physical_state": "solid",
        "category": "electronic",
    },
    {
        "sw_code": "SW 422",
        "description": "Waste photographic chemicals",
        "examples": "Developer, fixer, bleach-fix solutions",
        "physical_state": "liquid",
        "category": "organic",
    },
    {
        "sw_code": "SW 440",
        "description": "Pharmaceutical waste",
        "examples": "Expired medicines, cytotoxic drugs, vaccines",
        "physical_state": "solid",
        "category": "clinical",
    },
    {
        "sw_code": "SW 501",
        "description": "Leachate from scheduled waste disposal facility",
        "examples": "Landfill leachate",
        "physical_state": "liquid",
        "category": "inorganic",
    },
    {
        "sw_code": "SW 503",
        "description": "Contaminated soil",
        "examples": "Hydrocarbon-contaminated soil from spills",
        "physical_state": "solid",
        "category": "inorganic",
    },
]

# =============================================================
# Helpers
# =============================================================


async def _get_batch_or_404(
    batch_id: uuid.UUID, db: AsyncSession
) -> ScheduledWasteBatch:
    result = await db.execute(
        select(ScheduledWasteBatch).where(ScheduledWasteBatch.id == batch_id)
    )
    batch = result.scalar_one_or_none()
    if batch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scheduled waste batch {batch_id} not found",
        )
    return batch


async def _get_cn_or_404(cn_id: uuid.UUID, db: AsyncSession) -> ConsignmentNote:
    result = await db.execute(
        select(ConsignmentNote).where(ConsignmentNote.id == cn_id)
    )
    cn = result.scalar_one_or_none()
    if cn is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Consignment note {cn_id} not found",
        )
    return cn


def _generate_cn_number(db_count: int) -> str:
    """
    Generates a human-readable consignment note number.
    Format: CN-YYYY-NNNNN
    """
    year = datetime.now(timezone.utc).year
    return f"CN-{year}-{db_count + 1:05d}"


# =============================================================
# GET /sw-batches  — list scheduled waste batches
# =============================================================


@router.get(
    "/sw-batches",
    response_model=Dict[str, Any],
    summary="List scheduled waste batches",
    description=(
        "Returns a paginated list of scheduled waste batches. "
        "Optionally filter by status, client_id, and sw_code. "
        "Each record includes days_remaining until the 90-day storage deadline."
    ),
)
async def list_sw_batches(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    status_filter: Optional[str] = Query(
        default=None,
        alias="status",
        description="in_storage | dispatched | processed",
    ),
    client_id: Optional[uuid.UUID] = Query(default=None),
    sw_code: Optional[str] = Query(
        default=None, description="Filter by DOE scheduled waste code"
    ),
    expiring_soon: Optional[bool] = Query(
        default=None,
        description="If true, return only batches expiring within 14 days",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    """List all scheduled waste batches with optional filters."""

    if status_filter and status_filter not in BATCH_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid status. Must be one of: {sorted(BATCH_STATUSES)}",
        )

    filters: list = []
    if status_filter:
        filters.append(ScheduledWasteBatch.status == status_filter)
    if client_id:
        filters.append(ScheduledWasteBatch.client_id == client_id)
    if sw_code:
        filters.append(ScheduledWasteBatch.sw_code.ilike(f"%{sw_code}%"))
    if expiring_soon:
        # deadline = storage_start_date + 90 days
        # expiring within 14 days: deadline <= today + 14
        today = date.today()
        cutoff = today + timedelta(days=14)
        # storage_deadline column stores the computed date
        filters.append(ScheduledWasteBatch._storage_deadline_db <= cutoff)
        filters.append(ScheduledWasteBatch.status == "in_storage")

    base_stmt = select(ScheduledWasteBatch)
    if filters:
        base_stmt = base_stmt.where(and_(*filters))

    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total_result = await db.execute(count_stmt)
    total: int = total_result.scalar_one()

    stmt = (
        base_stmt.order_by(
            ScheduledWasteBatch._storage_deadline_db.asc().nulls_last(),
            ScheduledWasteBatch.created_at.desc(),
        )
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    batches = result.scalars().all()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": [ScheduledWasteBatchRead.from_orm_with_computed(b) for b in batches],
    }


# =============================================================
# POST /sw-batches  — create a new SW batch
# =============================================================


@router.post(
    "/sw-batches",
    response_model=ScheduledWasteBatchRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a scheduled waste batch",
    dependencies=[Depends(require_roles(*COMPLIANCE_ROLES))],
)
async def create_sw_batch(
    payload: ScheduledWasteBatchCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> ScheduledWasteBatchRead:
    """
    Creates a new scheduled waste storage batch.

    The `storage_deadline` (storage_start_date + 90 days) is automatically
    computed and stored in the `storage_deadline` column for efficient
    deadline query filtering.
    """
    from datetime import timedelta

    # Validate sw_code exists in library (soft validation — allow custom codes)
    known_codes = {sw["sw_code"] for sw in SW_CODE_LIBRARY}
    if payload.sw_code.upper() not in known_codes:
        logger.warning(
            "SW batch created with non-library code: %s (user=%s)",
            payload.sw_code,
            current_user.get("sub"),
        )

    # Compute storage deadline
    deadline = payload.storage_start_date + timedelta(days=90)

    batch = ScheduledWasteBatch(
        id=uuid.uuid4(),
        job_id=payload.job_id,
        client_id=payload.client_id,
        sw_code=payload.sw_code.upper(),
        waste_description=payload.waste_description,
        quantity_kg=payload.quantity_kg,
        physical_state=payload.physical_state,
        container_type=payload.container_type,
        container_count=payload.container_count,
        storage_start_date=payload.storage_start_date,
        _storage_deadline_db=deadline,
        status="in_storage",
        created_at=datetime.now(timezone.utc),
    )
    db.add(batch)
    await db.flush()
    await db.refresh(batch)

    logger.info(
        "SW batch created id=%s sw_code=%s client=%s by user=%s",
        batch.id,
        batch.sw_code,
        batch.client_id,
        current_user.get("sub"),
    )
    return ScheduledWasteBatchRead.from_orm_with_computed(batch)


# =============================================================
# GET /sw-batches/{id}  — batch detail
# =============================================================


@router.get(
    "/sw-batches/{batch_id}",
    response_model=ScheduledWasteBatchRead,
    summary="Get scheduled waste batch detail",
)
async def get_sw_batch(
    batch_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> ScheduledWasteBatchRead:
    """Returns full detail of a single scheduled waste batch."""
    batch = await _get_batch_or_404(batch_id, db)
    return ScheduledWasteBatchRead.from_orm_with_computed(batch)


# =============================================================
# PUT /sw-batches/{id}  — update batch
# =============================================================


@router.put(
    "/sw-batches/{batch_id}",
    response_model=ScheduledWasteBatchRead,
    summary="Update a scheduled waste batch",
    dependencies=[Depends(require_roles(*COMPLIANCE_ROLES))],
)
async def update_sw_batch(
    batch_id: uuid.UUID,
    payload: ScheduledWasteBatchUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> ScheduledWasteBatchRead:
    """Partially updates a scheduled waste batch record."""
    batch = await _get_batch_or_404(batch_id, db)

    update_data = payload.model_dump(exclude_unset=True)

    # Recompute storage_deadline if storage_start_date is being updated
    if "storage_start_date" in update_data:
        from datetime import timedelta

        update_data["_storage_deadline_db"] = update_data[
            "storage_start_date"
        ] + timedelta(days=90)

    for field, value in update_data.items():
        setattr(batch, field, value)

    await db.flush()
    await db.refresh(batch)
    logger.info("SW batch %s updated by user %s", batch_id, current_user.get("sub"))
    return ScheduledWasteBatchRead.from_orm_with_computed(batch)


# =============================================================
# PATCH /sw-batches/{id}/status  — update batch status
# =============================================================


@router.patch(
    "/sw-batches/{batch_id}/status",
    response_model=ScheduledWasteBatchRead,
    summary="Update scheduled waste batch status",
    dependencies=[Depends(require_roles(*COMPLIANCE_ROLES))],
)
async def update_sw_batch_status(
    batch_id: uuid.UUID,
    payload: ScheduledWasteBatchStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> ScheduledWasteBatchRead:
    """
    Updates the status of a scheduled waste batch.

    Valid transitions:
    - `in_storage` → `dispatched` (when collection vehicle departs)
    - `dispatched` → `processed` (when processing facility confirms receipt)

    Once a batch reaches `processed`, no further status changes are allowed.
    """
    batch = await _get_batch_or_404(batch_id, db)

    # Validate transition
    VALID_TRANSITIONS: Dict[str, List[str]] = {
        "in_storage": ["dispatched"],
        "dispatched": ["processed"],
        "processed": [],  # terminal state
    }

    allowed = VALID_TRANSITIONS.get(batch.status, [])
    if payload.status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot transition batch from '{batch.status}' to '{payload.status}'. "
                f"Allowed transitions from '{batch.status}': {allowed or ['none (terminal state)']}"
            ),
        )

    batch.status = payload.status
    if payload.notes:
        note_prefix = (
            f"[{datetime.now(timezone.utc).isoformat()}] Status → {payload.status}: "
        )
        batch.waste_description = (
            f"{batch.waste_description}\n{note_prefix}{payload.notes}"
            if batch.waste_description
            else f"{note_prefix}{payload.notes}"
        )

    await db.flush()
    await db.refresh(batch)
    logger.info(
        "SW batch %s status changed to %s by user %s",
        batch_id,
        payload.status,
        current_user.get("sub"),
    )
    return ScheduledWasteBatchRead.from_orm_with_computed(batch)


# =============================================================
# GET /deadlines  — batches expiring soon sorted by urgency
# =============================================================


@router.get(
    "/deadlines",
    response_model=Dict[str, Any],
    summary="Scheduled waste storage deadlines",
    description=(
        "Returns in-storage batches approaching or past their 90-day storage deadline, "
        "sorted by urgency. "
        "Severity: warning at ≤80 days remaining, critical at ≤88 days remaining "
        "(i.e. within the final 10/2 days before the 90-day limit)."
    ),
)
async def get_deadline_alerts(
    days_ahead: int = Query(
        default=30,
        ge=1,
        le=90,
        description="Look-ahead window — only show batches expiring within this many days",
    ),
    client_id: Optional[uuid.UUID] = Query(
        default=None, description="Restrict to a single client"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Returns scheduled waste batches that are approaching their 90-day storage deadline.

    Severity rules (days_remaining):
    - **critical** : ≤ 2 days  (≥ 88 days stored)
    - **warning**  : ≤ 10 days (≥ 80 days stored)
    - **info**     : > 10 days but within the look-ahead window
    - **overdue**  : deadline already passed (days_remaining < 0)
    """
    today = date.today()
    cutoff = today + timedelta(days=days_ahead)

    filters: list = [
        ScheduledWasteBatch.status == "in_storage",
        ScheduledWasteBatch._storage_deadline_db <= cutoff,
    ]
    if client_id:
        filters.append(ScheduledWasteBatch.client_id == client_id)

    stmt = (
        select(ScheduledWasteBatch)
        .where(and_(*filters))
        .order_by(ScheduledWasteBatch._storage_deadline_db.asc().nulls_last())
    )
    result = await db.execute(stmt)
    batches = result.scalars().all()

    items: List[Dict[str, Any]] = []
    critical_count = 0
    warning_count = 0
    overdue_count = 0

    for batch in batches:
        days_remaining = batch.days_remaining
        deadline = batch.storage_deadline

        if days_remaining is None:
            severity = "info"
        elif days_remaining < 0:
            severity = "critical"
            overdue_count += 1
        elif days_remaining <= 2:
            severity = "critical"
            critical_count += 1
        elif days_remaining <= 10:
            severity = "warning"
            warning_count += 1
        else:
            severity = "info"

        items.append(
            {
                "batch_id": str(batch.id),
                "client_id": str(batch.client_id),
                "sw_code": batch.sw_code,
                "waste_description": batch.waste_description,
                "quantity_kg": float(batch.quantity_kg),
                "physical_state": batch.physical_state,
                "storage_start_date": batch.storage_start_date.isoformat(),
                "storage_deadline": deadline.isoformat() if deadline else None,
                "days_remaining": days_remaining,
                "status": batch.status,
                "severity": severity,
                "is_overdue": days_remaining is not None and days_remaining < 0,
                "consignment_note_id": str(batch.consignment_note_id)
                if batch.consignment_note_id
                else None,
            }
        )

    return {
        "total": len(items),
        "days_ahead": days_ahead,
        "as_of_date": today.isoformat(),
        "summary": {
            "critical": critical_count,
            "warning": warning_count,
            "overdue": overdue_count,
            "info": len(items) - critical_count - warning_count - overdue_count,
        },
        "items": items,
    }


# =============================================================
# POST /consignment-notes  — create consignment note from batch
# =============================================================


@router.post(
    "/consignment-notes",
    response_model=ConsignmentNoteRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create consignment note for a scheduled waste batch",
    dependencies=[Depends(require_roles(*COMPLIANCE_ROLES))],
)
async def create_consignment_note(
    payload: ConsignmentNoteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> ConsignmentNoteRead:
    """
    Creates an official consignment note (CN) for a scheduled waste batch.

    Rules:
    - The batch must exist and be in `in_storage` or `dispatched` status.
    - Each batch can have at most one consignment note.
    - A unique CN number in the format `CN-YYYY-NNNNN` is auto-generated.
    - The batch's `consignment_note_id` is updated to link to the new CN.
    """
    # Validate batch exists
    batch = await _get_batch_or_404(payload.batch_id, db)

    if batch.status == "processed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot create a consignment note for a batch that has already been processed",
        )

    # Check for existing CN for this batch
    existing_cn = await db.execute(
        select(ConsignmentNote).where(ConsignmentNote.batch_id == payload.batch_id)
    )
    if existing_cn.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Batch {payload.batch_id} already has a consignment note",
        )

    # Generate CN number
    count_result = await db.execute(select(func.count()).select_from(ConsignmentNote))
    cn_count: int = count_result.scalar_one()
    cn_number = _generate_cn_number(cn_count)

    # Verify uniqueness (race condition guard)
    existing_number = await db.execute(
        select(ConsignmentNote).where(ConsignmentNote.note_number == cn_number)
    )
    if existing_number.scalar_one_or_none() is not None:
        cn_number = _generate_cn_number(cn_count + 1)

    cn = ConsignmentNote(
        id=uuid.uuid4(),
        batch_id=payload.batch_id,
        note_number=cn_number,
        generated_at=datetime.now(timezone.utc),
        cenviro_reference=payload.cenviro_reference,
        transport_date=payload.transport_date,
        transporter_name=payload.transporter_name,
        vehicle_registration=payload.vehicle_registration,
        processing_facility=payload.processing_facility,
        status="draft",
    )
    db.add(cn)
    await db.flush()

    # Link the CN back to the batch
    batch.consignment_note_id = cn.id
    await db.flush()
    await db.refresh(cn)

    logger.info(
        "ConsignmentNote %s created for batch %s by user %s",
        cn.note_number,
        payload.batch_id,
        current_user.get("sub"),
    )
    return ConsignmentNoteRead.model_validate(cn)


# =============================================================
# GET /consignment-notes  — list all consignment notes
# =============================================================


@router.get(
    "/consignment-notes",
    response_model=Dict[str, Any],
    summary="List consignment notes",
)
async def list_consignment_notes(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    status_filter: Optional[str] = Query(
        default=None,
        alias="status",
        description="draft | submitted | confirmed | processed",
    ),
    batch_id: Optional[uuid.UUID] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    """List all consignment notes with optional filters."""

    if status_filter and status_filter not in CN_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid status. Must be one of: {sorted(CN_STATUSES)}",
        )

    filters: list = []
    if status_filter:
        filters.append(ConsignmentNote.status == status_filter)
    if batch_id:
        filters.append(ConsignmentNote.batch_id == batch_id)

    base_stmt = select(ConsignmentNote)
    if filters:
        base_stmt = base_stmt.where(and_(*filters))

    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total_result = await db.execute(count_stmt)
    total: int = total_result.scalar_one()

    stmt = (
        base_stmt.order_by(ConsignmentNote.generated_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    notes = result.scalars().all()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": [ConsignmentNoteRead.model_validate(cn) for cn in notes],
    }


# =============================================================
# GET /consignment-notes/{id}  — single CN
# =============================================================


@router.get(
    "/consignment-notes/{cn_id}",
    response_model=ConsignmentNoteRead,
    summary="Get consignment note detail",
)
async def get_consignment_note(
    cn_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> ConsignmentNoteRead:
    """Returns the full detail of a single consignment note."""
    cn = await _get_cn_or_404(cn_id, db)
    return ConsignmentNoteRead.model_validate(cn)


# =============================================================
# PUT /consignment-notes/{id}  — update CN
# =============================================================


@router.put(
    "/consignment-notes/{cn_id}",
    response_model=ConsignmentNoteRead,
    summary="Update a consignment note",
    dependencies=[Depends(require_roles(*COMPLIANCE_ROLES))],
)
async def update_consignment_note(
    cn_id: uuid.UUID,
    payload: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> ConsignmentNoteRead:
    """Partially updates a consignment note. Processed CNs cannot be modified."""
    cn = await _get_cn_or_404(cn_id, db)

    if cn.status == "processed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Processed consignment notes cannot be modified",
        )

    allowed_fields = {
        "cenviro_reference",
        "transport_date",
        "transporter_name",
        "vehicle_registration",
        "processing_facility",
        "status",
        "pdf_path",
        "signed_by_hitech",
        "signed_by_client",
    }

    if "status" in payload and payload["status"] not in CN_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid status. Must be one of: {sorted(CN_STATUSES)}",
        )

    for field, value in payload.items():
        if field in allowed_fields:
            setattr(cn, field, value)

    await db.flush()
    await db.refresh(cn)
    return ConsignmentNoteRead.model_validate(cn)


# =============================================================
# GET /consignment-notes/{id}/pdf  — trigger/return PDF
# =============================================================


@router.get(
    "/consignment-notes/{cn_id}/pdf",
    response_model=Dict[str, Any],
    summary="Generate or retrieve consignment note PDF",
    description=(
        "Triggers PDF generation for the consignment note if it hasn't been generated yet, "
        "or returns the existing PDF URL if already available."
    ),
)
async def get_cn_pdf(
    cn_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Returns the PDF URL for a consignment note.

    If the PDF hasn't been generated yet, queues a Celery task to generate it
    and returns a `status: queued` response with a `task_id`.

    If the PDF already exists, returns `status: ready` with the `pdf_url`.
    """
    cn = await _get_cn_or_404(cn_id, db)

    # If PDF already exists, return immediately
    if cn.pdf_path:
        pdf_url = f"{settings.BACKEND_URL}/static/consignment-notes/{cn_id}.pdf"
        return {
            "cn_id": str(cn_id),
            "note_number": cn.note_number,
            "status": "ready",
            "pdf_url": pdf_url,
            "pdf_path": cn.pdf_path,
        }

    # Try to queue Celery task for PDF generation
    task_id: Optional[str] = None
    try:
        from tasks.pdf_tasks import (
            generate_consignment_note_pdf,  # type: ignore[import]
        )

        task = generate_consignment_note_pdf.delay(str(cn_id))
        task_id = task.id
        logger.info(
            "Queued PDF generation for CN %s task_id=%s", cn.note_number, task_id
        )
    except Exception as exc:
        logger.warning(
            "Could not queue PDF generation for CN %s: %s — generating inline",
            cn.note_number,
            exc,
        )
        # Fallback: generate inline (synchronous, basic)
        import os

        output_dir = os.path.join(settings.REPORT_OUTPUT_DIR, "consignment-notes")
        os.makedirs(output_dir, exist_ok=True)
        pdf_path = os.path.join(output_dir, f"{cn_id}.pdf")

        try:
            _generate_cn_pdf_inline(cn, pdf_path)
            cn.pdf_path = pdf_path
            await db.flush()
            await db.refresh(cn)

            return {
                "cn_id": str(cn_id),
                "note_number": cn.note_number,
                "status": "ready",
                "pdf_url": f"{settings.BACKEND_URL}/static/consignment-notes/{cn_id}.pdf",
                "pdf_path": pdf_path,
            }
        except Exception as gen_exc:
            logger.error("Inline PDF generation failed: %s", gen_exc)

    return {
        "cn_id": str(cn_id),
        "note_number": cn.note_number,
        "status": "queued" if task_id else "error",
        "task_id": task_id,
        "pdf_url": None,
        "message": (
            "PDF generation has been queued. Poll this endpoint to check status."
            if task_id
            else "PDF generation failed. Please try again."
        ),
    }


def _generate_cn_pdf_inline(cn: ConsignmentNote, output_path: str) -> None:
    """
    Generates a minimal consignment note PDF using ReportLab.
    Used as a fallback when the Celery task worker is unavailable.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import cm
        from reportlab.pdfgen import canvas

        c = canvas.Canvas(output_path, pagesize=A4)
        width, height = A4

        c.setFont("Helvetica-Bold", 16)
        c.drawString(2 * cm, height - 3 * cm, "CONSIGNMENT NOTE")
        c.setFont("Helvetica", 12)
        c.drawString(2 * cm, height - 4 * cm, f"Note Number: {cn.note_number}")
        c.drawString(
            2 * cm,
            height - 5 * cm,
            f"Generated At: {cn.generated_at.isoformat() if cn.generated_at else 'N/A'}",
        )
        c.drawString(
            2 * cm,
            height - 6 * cm,
            f"Status: {cn.status}",
        )
        c.drawString(
            2 * cm,
            height - 7 * cm,
            f"Transporter: {cn.transporter_name or 'N/A'}",
        )
        c.drawString(
            2 * cm,
            height - 8 * cm,
            f"Vehicle Registration: {cn.vehicle_registration or 'N/A'}",
        )
        c.drawString(
            2 * cm,
            height - 9 * cm,
            f"Processing Facility: {cn.processing_facility or 'N/A'}",
        )
        c.drawString(
            2 * cm,
            height - 10 * cm,
            f"Transport Date: {cn.transport_date.isoformat() if cn.transport_date else 'N/A'}",
        )
        c.drawString(
            2 * cm,
            height - 11 * cm,
            f"Cenviro Reference: {cn.cenviro_reference or 'N/A'}",
        )

        c.setFont("Helvetica-Oblique", 9)
        c.drawString(
            2 * cm,
            2 * cm,
            "This document is computer-generated. Printed copies require authorised signatures.",
        )
        c.save()
    except ImportError:
        # ReportLab not available — write a placeholder text file
        with open(output_path.replace(".pdf", ".txt"), "w") as f:
            f.write(
                f"CONSIGNMENT NOTE\n"
                f"Note Number: {cn.note_number}\n"
                f"Generated At: {cn.generated_at}\n"
                f"Status: {cn.status}\n"
            )


# =============================================================
# GET /sw-codes/search  — search SW code library
# =============================================================


@router.get(
    "/sw-codes/search",
    response_model=Dict[str, Any],
    summary="Search scheduled waste code library",
    description=(
        "Searches the in-memory DOE Scheduled Waste Code library. "
        "Supports partial matching on sw_code, description, examples, and category."
    ),
)
async def search_sw_codes(
    q: str = Query(
        default="",
        description="Search query — partial match on sw_code, description, or examples",
    ),
    category: Optional[str] = Query(
        default=None,
        description="Filter by category: organic | inorganic | clinical | electronic",
    ),
    physical_state: Optional[str] = Query(
        default=None,
        description="Filter by physical state: solid | liquid | sludge | gas",
    ),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Searches the DOE Scheduled Waste Code library.

    The library contains common scheduled waste codes used in Malaysia
    under the Environmental Quality (Scheduled Wastes) Regulations 2005.

    Results support partial matching on:
    - `sw_code`       : e.g. "SW 3" matches SW 305, SW 306, SW 322
    - `description`   : e.g. "oil" matches lubricating oil, fuel oil
    - `examples`      : e.g. "battery" matches lead-acid batteries
    - `category`      : exact filter
    - `physical_state`: exact filter
    """
    query_lower = q.lower().strip()

    results = SW_CODE_LIBRARY

    # Text search
    if query_lower:
        results = [
            sw
            for sw in results
            if (
                query_lower in sw["sw_code"].lower()
                or query_lower in sw["description"].lower()
                or query_lower in sw["examples"].lower()
            )
        ]

    # Category filter
    if category:
        results = [
            sw for sw in results if sw.get("category", "").lower() == category.lower()
        ]

    # Physical state filter
    if physical_state:
        results = [
            sw
            for sw in results
            if sw.get("physical_state", "").lower() == physical_state.lower()
        ]

    total = len(results)
    paginated = results[skip : skip + limit]

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "query": q,
        "filters": {"category": category, "physical_state": physical_state},
        "items": paginated,
    }


# =============================================================
# GET /summary — compliance summary alias
# =============================================================


@router.get(
    "/summary",
    response_model=Dict[str, Any],
    summary="Compliance summary (alias)",
    description="Alias for /stats/summary for frontend compatibility.",
    include_in_schema=False,
)
async def compliance_summary_alias(
    client_id: Optional[uuid.UUID] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    """Compliance summary alias endpoint."""
    return await compliance_summary(client_id, db, current_user)


# =============================================================
# GET /stats/summary  — compliance dashboard summary
# =============================================================


@router.get(
    "/stats/summary",
    response_model=Dict[str, Any],
    summary="Compliance dashboard summary",
    description=(
        "Returns key compliance KPIs: active SW batches, "
        "upcoming deadlines, overdue batches, and CN status breakdown."
    ),
)
async def compliance_summary(
    client_id: Optional[uuid.UUID] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    """High-level compliance KPI summary for dashboard tiles."""

    today = date.today()

    # Base filters
    batch_filters: list = []
    if client_id:
        batch_filters.append(ScheduledWasteBatch.client_id == client_id)

    # Total batches by status
    status_stmt = select(
        ScheduledWasteBatch.status,
        func.count(ScheduledWasteBatch.id).label("cnt"),
    ).group_by(ScheduledWasteBatch.status)
    if batch_filters:
        status_stmt = status_stmt.where(and_(*batch_filters))
    status_result = await db.execute(status_stmt)
    status_dist = {row.status: row.cnt for row in status_result}

    # Batches expiring within 30 days
    cutoff_30 = today + timedelta(days=30)
    expiring_stmt = select(func.count()).where(
        and_(
            ScheduledWasteBatch.status == "in_storage",
            ScheduledWasteBatch._storage_deadline_db <= cutoff_30,
            *(batch_filters),
        )
    )
    expiring_result = await db.execute(expiring_stmt)
    expiring_30d: int = expiring_result.scalar_one()

    # Overdue batches (deadline has passed)
    overdue_stmt = select(func.count()).where(
        and_(
            ScheduledWasteBatch.status == "in_storage",
            ScheduledWasteBatch._storage_deadline_db < today,
            *(batch_filters),
        )
    )
    overdue_result = await db.execute(overdue_stmt)
    overdue_count: int = overdue_result.scalar_one()

    # CN status breakdown
    cn_stmt = select(
        ConsignmentNote.status,
        func.count(ConsignmentNote.id).label("cnt"),
    ).group_by(ConsignmentNote.status)
    cn_result = await db.execute(cn_stmt)
    cn_dist = {row.status: row.cnt for row in cn_result}

    total_batches = sum(status_dist.values())
    in_storage = status_dist.get("in_storage", 0)
    compliance_rate: Optional[float] = None
    if total_batches > 0:
        non_overdue = in_storage - overdue_count
        compliance_rate = round(non_overdue / max(in_storage, 1) * 100, 2)

    return {
        "as_of_date": today.isoformat(),
        "client_id": str(client_id) if client_id else None,
        "batches": {
            "total": total_batches,
            "by_status": status_dist,
            "expiring_within_30_days": expiring_30d,
            "overdue": overdue_count,
            "compliance_rate_pct": compliance_rate,
        },
        "consignment_notes": {
            "total": sum(cn_dist.values()),
            "by_status": cn_dist,
        },
    }
