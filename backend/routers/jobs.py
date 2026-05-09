# =============================================================
# Hi-Tech Waste Management — Jobs Router
# Full CRUD + status pipeline validation + document upload
# + recurring job templates
# =============================================================

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from config import get_settings
from database import get_db
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from models.job import (
    JOB_STATUSES,
    JOB_TYPES,
    STATUS_PIPELINE,
    Job,
    JobCreate,
    JobRead,
    JobStatusUpdate,
    JobUpdate,
    RecurringJobTemplate,
    RecurringJobTemplateCreate,
    RecurringJobTemplateRead,
    RecurringJobTemplateUpdate,
)
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from routers.auth import get_current_user, require_roles

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()

# =============================================================
# Constants
# =============================================================

MANAGEMENT_ROLES = ["superadmin", "management", "operations_manager"]
ALL_STAFF_ROLES = [
    "superadmin",
    "management",
    "operations_manager",
    "field_supervisor",
    "driver",
    "compliance_officer",
]


# =============================================================
# Helper — Auto-generate job number
# =============================================================


async def _generate_job_number(db: AsyncSession) -> str:
    """
    Generates a sequential job number in the format JOB-YYYY-NNNN.
    Uses a COUNT query against the jobs table to determine the next sequence number.
    Safe for concurrent requests due to unique constraint on job_number.
    """
    year = datetime.now(timezone.utc).year
    result = await db.execute(
        select(func.count())
        .select_from(Job)
        .where(Job.job_number.like(f"JOB-{year}-%"))
    )
    count = result.scalar_one() or 0
    return f"JOB-{year}-{count + 1:04d}"


# =============================================================
# Recurring Template Schemas (in-memory store for now)
# =============================================================





# =============================================================
# Routes — Job CRUD
# =============================================================


@router.get(
    "/",
    summary="List jobs with filters and pagination",
    response_model=Dict[str, Any],
)
async def list_jobs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    status_filter: Optional[str] = Query(None, alias="status"),
    job_type: Optional[str] = Query(None),
    client_id: Optional[uuid.UUID] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    search: Optional[str] = Query(None, description="Search job_number or notes"),
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Returns a paginated list of jobs with optional filters.

    - **status** filter: draft | confirmed | dispatched | in_progress | completed | invoiced
    - **job_type** filter: general_collection | scheduled_waste | witnessed_destruction | ...
    - **client_id**: restrict to a single client
    - **date_from / date_to**: filter by scheduled_date range
    - **search**: free-text match against job_number or notes
    """
    if status_filter and status_filter not in JOB_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid status. Must be one of: {sorted(JOB_STATUSES)}",
        )
    if job_type and job_type not in JOB_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid job_type. Must be one of: {sorted(JOB_TYPES)}",
        )

    # Client-role users can only see their own jobs
    effective_client_id = client_id
    if current_user.get("role") == "client":
        # Resolve client record linked to portal_user_id
        from models.client import Client as ClientModel

        client_result = await db.execute(
            select(ClientModel).where(
                ClientModel.portal_user_id == uuid.UUID(current_user["id"])
            )
        )
        client_obj = client_result.scalar_one_or_none()
        if client_obj is None:
            return {"items": [], "total": 0, "skip": skip, "limit": limit}
        effective_client_id = client_obj.id

    stmt = select(Job)

    if status_filter:
        stmt = stmt.where(Job.status == status_filter)
    if job_type:
        stmt = stmt.where(Job.job_type == job_type)
    if effective_client_id:
        stmt = stmt.where(Job.client_id == effective_client_id)
    if date_from:
        stmt = stmt.where(Job.scheduled_date >= date_from)
    if date_to:
        stmt = stmt.where(Job.scheduled_date <= date_to)
    if search:
        like_expr = f"%{search}%"
        stmt = stmt.where(
            or_(
                Job.job_number.ilike(like_expr),
                Job.notes.ilike(like_expr),
                Job.collection_address.ilike(like_expr),
            )
        )

    # Count total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    # Paginate
    stmt = stmt.order_by(Job.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    jobs = result.scalars().all()

    return {
        "items": [JobRead.model_validate(j) for j in jobs],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.post(
    "/",
    summary="Create a new job",
    response_model=JobRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(*MANAGEMENT_ROLES))],
)
async def create_job(
    payload: JobCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> JobRead:
    """
    Creates a new job record.

    - Auto-generates `job_number` in the format `JOB-YYYY-NNNN`.
    - Initial status is always `draft`.
    - Only management / operations_manager / superadmin can create jobs.
    """
    if payload.job_type not in JOB_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid job_type. Must be one of: {sorted(JOB_TYPES)}",
        )

    # Verify client exists
    from models.client import Client as ClientModel

    client_check = await db.execute(
        select(ClientModel).where(ClientModel.id == payload.client_id)
    )
    if client_check.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client {payload.client_id} not found",
        )

    # Generate unique job number with retry on collision
    max_retries = 5
    job_number = None
    for _ in range(max_retries):
        candidate = await _generate_job_number(db)
        exists = await db.execute(select(Job.id).where(Job.job_number == candidate))
        if exists.scalar_one_or_none() is None:
            job_number = candidate
            break

    if job_number is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not generate a unique job number. Please retry.",
        )

    job = Job(
        id=uuid.uuid4(),
        job_number=job_number,
        client_id=payload.client_id,
        job_type=payload.job_type,
        status="draft",
        scheduled_date=payload.scheduled_date,
        scheduled_time_start=payload.scheduled_time_start,
        collection_address=payload.collection_address,
        assigned_vehicle_id=payload.assigned_vehicle_id,
        assigned_driver_id=payload.assigned_driver_id,
        assigned_supervisor_id=payload.assigned_supervisor_id,
        estimated_weight_kg=payload.estimated_weight_kg,
        disposal_route=payload.disposal_route,
        notes=payload.notes,
        created_by=uuid.UUID(current_user["id"]),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(job)
    await db.flush()
    await db.refresh(job)
    logger.info(
        "Job created: %s (type=%s) by user %s",
        job.job_number,
        job.job_type,
        current_user["id"],
    )
    return JobRead.model_validate(job)


@router.get(
    "/{job_id}/",
    summary="Get full job detail (alias)",
    response_model=JobRead,
    include_in_schema=False,
)
async def get_job_alias(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> JobRead:
    """Alias for /{job_id} with trailing slash."""
    return await get_job(job_id, db, current_user)


@router.get(
    "/{job_id}",
    summary="Get full job detail",
    response_model=JobRead,
)
async def get_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> JobRead:
    """Returns the full details of a single job including related entity names."""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    # Client-role access check
    if current_user.get("role") == "client":
        from models.client import Client as ClientModel

        client_result = await db.execute(
            select(ClientModel).where(
                ClientModel.portal_user_id == uuid.UUID(current_user["id"])
            )
        )
        client_obj = client_result.scalar_one_or_none()
        if client_obj is None or client_obj.id != job.client_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this job",
            )

    return JobRead.model_validate(job)


@router.put(
    "/{job_id}",
    summary="Update a job",
    response_model=JobRead,
    dependencies=[Depends(require_roles(*MANAGEMENT_ROLES))],
)
async def update_job(
    job_id: uuid.UUID,
    payload: JobUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> JobRead:
    """
    Updates mutable fields on a job.
    Status changes must use the PATCH /{id}/status endpoint.
    Invoiced jobs cannot be modified.
    """
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )
    if job.status == "invoiced":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Invoiced jobs cannot be modified",
        )

    update_data = payload.model_dump(exclude_unset=True)

    if "job_type" in update_data and update_data["job_type"] not in JOB_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid job_type. Must be one of: {sorted(JOB_TYPES)}",
        )

    for field, value in update_data.items():
        setattr(job, field, value)
    job.updated_at = datetime.now(timezone.utc)

    await db.flush()
    await db.refresh(job)
    logger.info("Job %s updated by user %s", job.job_number, current_user["id"])
    return JobRead.model_validate(job)


# =============================================================
# Route — Status Pipeline Update
# =============================================================


@router.post(
    "/{job_id}/status/",
    summary="Advance job status through pipeline (POST alias)",
    response_model=JobRead,
    dependencies=[Depends(require_roles(*ALL_STAFF_ROLES))],
    include_in_schema=False,
)
async def update_job_status_post_alias(
    job_id: uuid.UUID,
    payload: JobStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> JobRead:
    """Alias for PATCH /{job_id}/status with trailing slash."""
    return await update_job_status(job_id, payload, db, current_user)


@router.patch(
    "/{job_id}/status",
    summary="Advance job status through pipeline",
    response_model=JobRead,
    dependencies=[Depends(require_roles(*ALL_STAFF_ROLES))],
)
async def update_job_status(
    job_id: uuid.UUID,
    payload: JobStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> JobRead:
    """
    Advances the job through its status pipeline.

    **Valid pipeline**: draft → confirmed → dispatched → in_progress → completed → invoiced

    Rules:
    - Status can only move **forward** (no backward transitions).
    - Drivers can only mark `in_progress` or `completed`.
    - Setting `completed` automatically records `completed_at`.
    """
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    new_status = payload.status
    if new_status not in JOB_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid status. Must be one of: {sorted(JOB_STATUSES)}",
        )

    # Validate pipeline direction
    try:
        current_idx = STATUS_PIPELINE.index(job.status)
        new_idx = STATUS_PIPELINE.index(new_status)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown status value encountered: {job.status} or {new_status}",
        )

    if new_idx <= current_idx:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot move status from '{job.status}' to '{new_status}'. "
                f"Status can only advance forward in the pipeline: "
                f"{' → '.join(STATUS_PIPELINE)}"
            ),
        )

    # Role-based status restrictions
    role = current_user.get("role")
    if role == "driver" and new_status not in {"in_progress", "completed"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Drivers may only set status to 'in_progress' or 'completed'",
        )
    if role == "field_supervisor" and new_status == "invoiced":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Field supervisors cannot mark jobs as 'invoiced'",
        )

    job.status = new_status
    job.updated_at = datetime.now(timezone.utc)

    if new_status == "completed":
        job.completed_at = datetime.now(timezone.utc)

    if payload.notes:
        job.notes = (
            f"{job.notes}\n[{datetime.now(timezone.utc).isoformat()}] "
            f"Status → {new_status}: {payload.notes}"
            if job.notes
            else f"[{datetime.now(timezone.utc).isoformat()}] "
            f"Status → {new_status}: {payload.notes}"
        )

    await db.flush()
    await db.refresh(job)
    logger.info(
        "Job %s status changed to %s by user %s",
        job.job_number,
        new_status,
        current_user["id"],
    )

    # Fire-and-forget WhatsApp + email notifications for key status transitions
    import asyncio
    from services.notification_service import send_whatsapp_job_status, send_job_status_email

    NOTIFY_STATUSES = {"confirmed", "dispatched", "in_progress", "completed"}
    if new_status in NOTIFY_STATUSES:
        try:
            # Resolve client PIC contact details
            from models.client import Client as ClientModel
            client_result = await db.execute(
                select(ClientModel).where(ClientModel.id == job.client_id)
            )
            client = client_result.scalar_one_or_none()

            if client:
                # Resolve driver name if assigned
                driver_name: str | None = None
                if job.assigned_driver_id:
                    from models.user import User as UserModel
                    driver_result = await db.execute(
                        select(UserModel).where(UserModel.id == job.assigned_driver_id)
                    )
                    driver = driver_result.scalar_one_or_none()
                    if driver:
                        driver_name = driver.full_name

                scheduled_date_str = (
                    job.scheduled_date.isoformat() if job.scheduled_date else None
                )

                # WhatsApp to client PIC
                if client.pic_phone:
                    asyncio.create_task(
                        send_whatsapp_job_status(
                            phone_number=client.pic_phone,
                            client_name=client.company_name,
                            job_number=job.job_number,
                            new_status=new_status,
                            driver_name=driver_name,
                            scheduled_date=scheduled_date_str,
                        )
                    )

                # Email to client PIC
                if client.pic_email:
                    asyncio.create_task(
                        send_job_status_email(
                            to=client.pic_email,
                            client_name=client.company_name,
                            job_number=job.job_number,
                            status=new_status,
                            scheduled_date=scheduled_date_str,
                            driver_name=driver_name,
                        )
                    )
        except Exception as notify_exc:
            logger.warning("Notification dispatch failed for job %s: %s", job.job_number, notify_exc)

    return JobRead.model_validate(job)


# =============================================================
# GET /status-counts — Job counts by status
# =============================================================


@router.get(
    "/status-counts",
    # response_model removed to avoid Pydantic validation issues
    summary="Job counts by status",
    description="Returns the count of jobs grouped by status for dashboard widgets.",
)
async def get_job_status_counts(
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Returns job counts grouped by status for dashboard visualizations.

    Includes counts for each job status and total count.
    Applies same filtering as list_jobs endpoint (client users see only their jobs).
    """
    try:
        # Build base query - apply same filtering as list_jobs
        stmt = select(Job)

        # Client-role users can only see their own jobs
        if current_user.get("role") == "client":
            from models.client import Client as ClientModel

            client_result = await db.execute(
                select(ClientModel).where(
                    ClientModel.portal_user_id == uuid.UUID(current_user["id"])
                )
            )
            client_obj = client_result.scalar_one_or_none()
            if client_obj is None:
                return {
                    "total": 0,
                    "by_status": {status: 0 for status in JOB_STATUSES},
                }
            stmt = stmt.where(Job.client_id == client_obj.id)

        # Get all jobs matching the filter and count them in Python
        result = await db.execute(stmt)
        jobs = result.scalars().all()

        # Count by status in Python to avoid SQL complexity
        status_counts: Dict[str, int] = {status: 0 for status in JOB_STATUSES}
        total = 0
        for job in jobs:
            status_counts[str(job.status)] += 1
            total += 1

        # Debug logging
        logger.info(
            "Job status counts - user=%s role=%s total=%d by_status=%s",
            current_user.get("id"),
            current_user.get("role"),
            total,
            status_counts,
        )

        return {
            "total": total,
            "by_status": status_counts,
        }
    except Exception as e:
        logger.error("Error in get_job_status_counts: %s", str(e), exc_info=True)
        # Return empty counts on error so frontend doesn't crash
        return {
            "total": 0,
            "by_status": {status: 0 for status in JOB_STATUSES},
            "error": str(e),
        }


# =============================================================
# Route — Document Attachment Upload
# =============================================================


@router.post(
    "/{job_id}/documents",
    summary="Attach a document to a job",
    status_code=status.HTTP_201_CREATED,
)
async def upload_job_document(
    job_id: uuid.UUID,
    file: UploadFile = File(...),
    doc_type: str = Query(
        default="report",
        description="regulation | contract | sop | report | manual",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Uploads a document and attaches it to a job.

    The file is saved to the configured REPORT_OUTPUT_DIR, and a Document
    record is created in the database. Returns the created Document metadata.
    """
    import os
    import shutil

    from models.document import Document

    # Verify job exists
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    # Validate file type (accept PDF, images, Office docs)
    ALLOWED_MIME_TYPES = {
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/webp",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/plain",
        "text/csv",
    }
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Unsupported file type: {file.content_type}. "
                f"Allowed types: {', '.join(sorted(ALLOWED_MIME_TYPES))}"
            ),
        )

    # Build storage path
    upload_dir = os.path.join(settings.REPORT_OUTPUT_DIR, "job_documents", str(job_id))
    os.makedirs(upload_dir, exist_ok=True)

    safe_filename = f"{uuid.uuid4()}_{file.filename}"
    file_path = os.path.join(upload_dir, safe_filename)

    try:
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
    except OSError as exc:
        logger.error("Failed to save document for job %s: %s", job_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save uploaded file",
        )

    # Retrieve client_id from job for document record
    from models.client import Client as ClientModel

    client_result = await db.execute(
        select(ClientModel.id).where(ClientModel.id == job.client_id)
    )
    client_id = client_result.scalar_one_or_none()

    doc = Document(
        id=uuid.uuid4(),
        title=file.filename or safe_filename,
        doc_type=doc_type,
        client_id=client_id,
        file_path=file_path,
        mime_type=file.content_type,
        uploaded_by=uuid.UUID(current_user["id"]),
        uploaded_at=datetime.now(timezone.utc),
    )
    db.add(doc)
    await db.flush()
    await db.refresh(doc)

    logger.info(
        "Document '%s' attached to job %s by user %s",
        file.filename,
        job.job_number,
        current_user["id"],
    )

    return {
        "id": str(doc.id),
        "title": doc.title,
        "doc_type": doc.doc_type,
        "file_path": doc.file_path,
        "mime_type": doc.mime_type,
        "uploaded_at": doc.uploaded_at.isoformat(),
        "job_id": str(job_id),
    }


# =============================================================
# Routes — Recurring Templates
# =============================================================


@router.get(
    "/recurring/templates",
    summary="List recurring job templates",
    response_model=Dict[str, Any],
)
async def list_recurring_templates(
    client_id: Optional[uuid.UUID] = Query(None),
    is_active: Optional[bool] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Lists all recurring job templates.

    Templates define a job configuration plus an iCal RRULE recurrence
    rule (e.g. FREQ=WEEKLY;BYDAY=MO,WE,FR) so that the scheduler can
    automatically create job instances on the defined schedule.
    """
    query = select(RecurringJobTemplate)
    
    if client_id is not None:
        query = query.where(RecurringJobTemplate.client_id == client_id)
    if is_active is not None:
        query = query.where(RecurringJobTemplate.is_active == is_active)
    
    # Get total count
    count_result = await db.execute(
        select(func.count()).select_from(RecurringJobTemplate).where(
            (RecurringJobTemplate.client_id == client_id) if client_id else True
        )
    )
    total = count_result.scalar_one() or 0
    
    # Get paginated results
    query = query.offset(skip).limit(limit).order_by(RecurringJobTemplate.created_at.desc())
    result = await db.execute(query)
    templates = result.scalars().all()
    
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": [RecurringJobTemplateRead.model_validate(t) for t in templates],
    }


@router.post(
    "/recurring/templates",
    summary="Create a recurring job template",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(*MANAGEMENT_ROLES))],
)
async def create_recurring_template(
    payload: RecurringJobTemplateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> RecurringJobTemplateRead:
    """
    Creates a recurring job template.

    The template stores a job configuration alongside an iCal RRULE
    string (e.g. `FREQ=WEEKLY;BYDAY=MO`) which can be consumed by
    the scheduler (Celery Beat) to generate concrete job instances.
    """
    if payload.job_type not in JOB_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid job_type. Must be one of: {sorted(JOB_TYPES)}",
        )

    # Verify client exists
    from models.client import Client as ClientModel

    client_check = await db.execute(
        select(ClientModel).where(ClientModel.id == payload.client_id)
    )
    if client_check.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client {payload.client_id} not found",
        )

    template = RecurringJobTemplate(
        name=payload.name,
        client_id=payload.client_id,
        job_type=payload.job_type,
        collection_address=payload.collection_address,
        assigned_vehicle_id=payload.assigned_vehicle_id,
        assigned_driver_id=payload.assigned_driver_id,
        assigned_supervisor_id=payload.assigned_supervisor_id,
        estimated_weight_kg=payload.estimated_weight_kg,
        disposal_route=payload.disposal_route,
        notes=payload.notes,
        recurrence_rule=payload.recurrence_rule,
        is_active=payload.is_active,
    )
    
    db.add(template)
    await db.flush()
    await db.refresh(template)

    logger.info(
        "Recurring template '%s' created by user %s",
        payload.name,
        current_user["id"],
    )
    return RecurringJobTemplateRead.model_validate(template)


@router.get(
    "/recurring/templates/{template_id}",
    summary="Get a recurring job template by ID",
    response_model=RecurringJobTemplateRead,
)
async def get_recurring_template(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> RecurringJobTemplateRead:
    """Returns a single recurring job template by its ID."""
    result = await db.execute(
        select(RecurringJobTemplate).where(RecurringJobTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recurring template {template_id!r} not found",
        )
    return RecurringJobTemplateRead.model_validate(template)


@router.patch(
    "/recurring/templates/{template_id}",
    summary="Update a recurring job template",
    response_model=RecurringJobTemplateRead,
    dependencies=[Depends(require_roles(*MANAGEMENT_ROLES))],
)
async def update_recurring_template(
    template_id: uuid.UUID,
    payload: RecurringJobTemplateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> RecurringJobTemplateRead:
    """Partially updates a recurring job template."""
    result = await db.execute(
        select(RecurringJobTemplate).where(RecurringJobTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recurring template {template_id!r} not found",
        )

    # Update only provided fields
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(template, key, value)
    
    template.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(template)

    return RecurringJobTemplateRead.model_validate(template)


@router.delete(
    "/recurring/templates/{template_id}",
    summary="Delete a recurring job template",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    dependencies=[Depends(require_roles(*MANAGEMENT_ROLES))],
)
async def delete_recurring_template(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> None:
    """Removes a recurring job template."""
    result = await db.execute(
        select(RecurringJobTemplate).where(RecurringJobTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recurring template {template_id!r} not found",
        )
    
    await db.delete(template)
    await db.flush()
    
    logger.info(
        "Recurring template %s deleted by user %s",
        template_id,
        current_user["id"],
    )
