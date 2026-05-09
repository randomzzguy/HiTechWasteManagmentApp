# =============================================================
# Hi-Tech Waste Management — Destruction Router
# Witnessed destruction jobs, dual sign-off, and certificate generation
# =============================================================

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from config import get_settings
from database import get_db
from fastapi import APIRouter, Depends, HTTPException, Query, status
from models.destruction import (
    DESTRUCTION_METHODS,
    DestructionJob,
    DestructionJobCreate,
    DestructionJobListItem,
    DestructionJobRead,
    DestructionJobUpdate,
    DestructionSignOffRequest,
)
from models.document import Certificate
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from routers.auth import get_current_user, require_roles

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()

# =============================================================
# Role sets
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


async def _get_destruction_job_or_404(
    job_id: uuid.UUID, db: AsyncSession
) -> DestructionJob:
    result = await db.execute(select(DestructionJob).where(DestructionJob.id == job_id))
    dj = result.scalar_one_or_none()
    if dj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Destruction job {job_id} not found",
        )
    return dj


# =============================================================
# GET /jobs — list destruction jobs
# =============================================================


@router.get(
    "/jobs",
    response_model=Dict[str, Any],
    summary="List destruction jobs",
    description=(
        "Returns a paginated list of destruction jobs. "
        "Filter by destruction_method, certificate_issued status, "
        "or job_id (parent job)."
    ),
)
async def list_destruction_jobs(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    destruction_method: Optional[str] = Query(
        default=None,
        description="shredding | incineration | landfill_compaction",
    ),
    certificate_issued: Optional[bool] = Query(
        default=None,
        description="Filter by whether the certificate has been issued",
    ),
    job_id: Optional[uuid.UUID] = Query(
        default=None,
        description="Filter by parent job UUID",
    ),
    search: Optional[str] = Query(
        default=None,
        description="Partial match on goods_description or witness_client_name",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    """Returns a paginated list of destruction jobs with optional filters."""

    if destruction_method and destruction_method not in DESTRUCTION_METHODS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid destruction_method. Must be one of: {sorted(DESTRUCTION_METHODS)}",
        )

    filters: list = []

    if destruction_method:
        filters.append(DestructionJob.destruction_method == destruction_method)
    if certificate_issued is not None:
        filters.append(DestructionJob.certificate_issued == certificate_issued)
    if job_id:
        filters.append(DestructionJob.job_id == job_id)
    if search:
        like = f"%{search}%"
        filters.append(
            or_(
                DestructionJob.goods_description.ilike(like),
                DestructionJob.witness_client_name.ilike(like),
                DestructionJob.destruction_location.ilike(like),
            )
        )

    base_stmt = select(DestructionJob)
    if filters:
        base_stmt = base_stmt.where(and_(*filters))

    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total_result = await db.execute(count_stmt)
    total: int = total_result.scalar_one()

    stmt = (
        base_stmt.order_by(
            DestructionJob.destruction_date.desc().nulls_last(),
            DestructionJob.created_at.desc(),
        )
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    jobs = result.scalars().all()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": [DestructionJobListItem.model_validate(j) for j in jobs],
    }


# =============================================================
# POST /jobs — create destruction job
# =============================================================


@router.post(
    "/jobs",
    response_model=DestructionJobRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a destruction job record",
    description=(
        "Creates a new witnessed destruction job record. "
        "The record tracks goods details, the destruction method, "
        "and will later capture dual sign-off signatures."
    ),
)
async def create_destruction_job(
    payload: DestructionJobCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> DestructionJobRead:
    """
    Creates a new destruction job record.

    - Validates the destruction_method against the allowed enumeration.
    - If a parent job_id is provided, verifies the job exists.
    - certificate_issued defaults to False until dual sign-off is completed.
    """
    # Validate parent job if provided
    if payload.job_id is not None:
        from models.job import Job

        job_result = await db.execute(select(Job).where(Job.id == payload.job_id))
        if job_result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Parent job {payload.job_id} not found",
            )

    # Validate witness_hitech_id if provided
    if payload.witness_hitech_id is not None:
        from models.user import User

        user_result = await db.execute(
            select(User).where(User.id == payload.witness_hitech_id)
        )
        if user_result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Witness user {payload.witness_hitech_id} not found",
            )

    now = datetime.now(timezone.utc)
    dj = DestructionJob(
        id=uuid.uuid4(),
        job_id=payload.job_id,
        goods_description=payload.goods_description,
        quantity_units=payload.quantity_units,
        weight_kg=payload.weight_kg,
        destruction_method=payload.destruction_method,
        destruction_date=payload.destruction_date,
        destruction_location=payload.destruction_location,
        witness_hitech_id=payload.witness_hitech_id,
        witness_client_name=payload.witness_client_name,
        witness_client_designation=payload.witness_client_designation,
        media_files=payload.media_files,
        certificate_issued=False,
        certificate_id=None,
        reason_codes=payload.reason_codes,
        created_at=now,
        updated_at=now,
    )
    db.add(dj)
    await db.flush()
    await db.refresh(dj)

    logger.info(
        "DestructionJob created id=%s method=%s by user=%s",
        dj.id,
        dj.destruction_method,
        current_user.get("sub"),
    )
    return DestructionJobRead.model_validate(dj)


# =============================================================
# GET /jobs/{id} — destruction job detail
# =============================================================


@router.get(
    "/jobs/{job_id}",
    response_model=DestructionJobRead,
    summary="Get destruction job detail",
)
async def get_destruction_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> DestructionJobRead:
    """Returns full details of a single destruction job."""
    dj = await _get_destruction_job_or_404(job_id, db)
    return DestructionJobRead.model_validate(dj)


# =============================================================
# PUT /jobs/{id} — update destruction job
# =============================================================


@router.put(
    "/jobs/{job_id}",
    response_model=DestructionJobRead,
    summary="Update a destruction job",
    dependencies=[Depends(require_roles(*STAFF_ROLES))],
)
async def update_destruction_job(
    job_id: uuid.UUID,
    payload: DestructionJobUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> DestructionJobRead:
    """
    Partially updates a destruction job record.

    Destruction jobs with a certificate already issued are locked —
    only management roles can override via the admin interface.
    """
    dj = await _get_destruction_job_or_404(job_id, db)

    # Lock completed destruction jobs with issued certificates
    if dj.certificate_issued and current_user.get("role") not in {
        "superadmin",
        "management",
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This destruction job has a Certificate of Destruction issued. "
                "Only management or superadmin can modify it."
            ),
        )

    update_data = payload.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(dj, field, value)

    dj.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(dj)

    logger.info("DestructionJob %s updated by user %s", job_id, current_user.get("sub"))
    return DestructionJobRead.model_validate(dj)


# =============================================================
# POST /jobs/{id}/sign — dual sign-off
# =============================================================


@router.post(
    "/jobs/{job_id}/sign",
    response_model=DestructionJobRead,
    summary="Record dual sign-off for a destruction job",
    description=(
        "Records the dual witness sign-off required before a Certificate of Destruction "
        "can be issued. Captures the Hi-Tech witness (by user ID) and the client "
        "representative (by name and designation)."
    ),
    dependencies=[Depends(require_roles(*STAFF_ROLES))],
)
async def sign_destruction_job(
    job_id: uuid.UUID,
    payload: DestructionSignOffRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> DestructionJobRead:
    """
    Records dual sign-off for a witnessed destruction job.

    **Requirements:**
    - The destruction job must exist.
    - A certificate must NOT already be issued (to prevent duplicate signing).
    - The Hi-Tech witness user must exist in the system.
    - Both witness fields (hitech + client) must be provided.

    After successful sign-off, the job is ready for certificate generation
    via `POST /destruction/jobs/{id}/certificate`.
    """
    dj = await _get_destruction_job_or_404(job_id, db)

    # Prevent re-signing if certificate already issued
    if dj.certificate_issued:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A Certificate of Destruction has already been issued for this job. "
                "Re-signing is not permitted."
            ),
        )

    # Validate Hi-Tech witness user exists and is active
    from models.user import User

    user_result = await db.execute(
        select(User).where(
            User.id == payload.witness_hitech_id,
            User.is_active == True,  # noqa: E712
        )
    )
    witness_user = user_result.scalar_one_or_none()
    if witness_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Hi-Tech witness user {payload.witness_hitech_id} not found or inactive",
        )

    # Validate that the Hi-Tech witness has an appropriate role
    allowed_witness_roles = {
        "superadmin",
        "management",
        "operations_manager",
        "field_supervisor",
        "compliance_officer",
    }
    if witness_user.role not in allowed_witness_roles:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"User {payload.witness_hitech_id} has role '{witness_user.role}' "
                f"which is not permitted to witness destruction events. "
                f"Allowed roles: {sorted(allowed_witness_roles)}"
            ),
        )

    # Record the sign-off
    dj.witness_hitech_id = payload.witness_hitech_id
    dj.witness_client_name = payload.witness_client_name
    dj.witness_client_designation = payload.witness_client_designation
    dj.destruction_date = payload.destruction_date
    dj.destruction_location = payload.destruction_location
    dj.updated_at = datetime.now(timezone.utc)

    # Append notes if provided
    if payload.notes:
        note_entry = (
            f"[{datetime.now(timezone.utc).isoformat()}] "
            f"Sign-off by {witness_user.full_name} + {payload.witness_client_name}: "
            f"{payload.notes}"
        )
        # Append to goods_description as an audit trail (no dedicated notes field on model)
        dj.goods_description = (
            f"{dj.goods_description}\n\n--- SIGN-OFF NOTE ---\n{note_entry}"
        )

    await db.flush()
    await db.refresh(dj)

    logger.info(
        "DestructionJob %s signed off: hitech=%s client=%s by user=%s",
        job_id,
        payload.witness_hitech_id,
        payload.witness_client_name,
        current_user.get("sub"),
    )
    return DestructionJobRead.model_validate(dj)


# =============================================================
# POST /jobs/{id}/certificate — generate Certificate of Destruction
# =============================================================


@router.post(
    "/jobs/{job_id}/certificate",
    status_code=status.HTTP_201_CREATED,
    summary="Generate a Certificate of Destruction",
    description=(
        "Generates a Certificate of Destruction PDF for a destruction job. "
        "Requires dual sign-off (witness_hitech_id and witness_client_name) "
        "to be recorded before this endpoint can be called."
    ),
    dependencies=[Depends(require_roles(*STAFF_ROLES))],
)
async def generate_certificate(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Generates a Certificate of Destruction for the specified destruction job.

    **Pre-requisites (validated by this endpoint):**
    1. Both `witness_hitech_id` and `witness_client_name` must be set (dual sign-off).
    2. `destruction_date` and `destruction_location` must be recorded.
    3. No valid (non-void) certificate may already exist for this job.

    **Process:**
    1. Creates a Certificate DB record with cert_type='destruction'.
    2. Marks the DestructionJob as `certificate_issued=True` and stores the `certificate_id`.
    3. Queues a Celery task to render the PDF (falls back to inline ReportLab if unavailable).
    4. Returns certificate metadata and task_id for status polling.
    """
    dj = await _get_destruction_job_or_404(job_id, db)

    # ── Pre-requisite validation ──────────────────────────────

    # 1. Dual sign-off must be complete
    if dj.witness_hitech_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Dual sign-off is required before generating a Certificate of Destruction. "
                "Please complete sign-off via POST /destruction/jobs/{id}/sign first."
            ),
        )
    if not dj.witness_client_name or not dj.witness_client_designation:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Client witness name and designation must be recorded "
                "before generating the certificate. Use POST /destruction/jobs/{id}/sign."
            ),
        )

    # 2. Destruction details must be confirmed
    if dj.destruction_date is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="destruction_date must be recorded before generating the certificate",
        )
    if not dj.destruction_location:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="destruction_location must be recorded before generating the certificate",
        )

    # 3. Check for duplicate certificate
    if dj.certificate_issued and dj.certificate_id is not None:
        existing_cert = await db.execute(
            select(Certificate).where(
                Certificate.id == dj.certificate_id,
                Certificate.is_void == False,  # noqa: E712
            )
        )
        if existing_cert.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"A valid Certificate of Destruction already exists for this job "
                    f"(certificate_id={dj.certificate_id}). "
                    "Void the existing certificate before generating a new one."
                ),
            )

    # ── Retrieve client_id from the parent job (if available) ─
    client_id_for_cert: Optional[uuid.UUID] = None
    if dj.job_id is not None:
        from models.job import Job

        job_result = await db.execute(select(Job).where(Job.id == dj.job_id))
        parent_job = job_result.scalar_one_or_none()
        if parent_job is not None:
            client_id_for_cert = parent_job.client_id

    # ── Create Certificate record ─────────────────────────────
    cert_id = uuid.uuid4()
    certificate = Certificate(
        id=cert_id,
        cert_type="destruction",
        reference_id=dj.id,
        client_id=client_id_for_cert,
        issued_at=datetime.now(timezone.utc),
        issued_by=uuid.UUID(current_user["sub"]),
        is_void=False,
    )
    db.add(certificate)

    # ── Update destruction job ────────────────────────────────
    dj.certificate_issued = True
    dj.certificate_id = cert_id
    dj.updated_at = datetime.now(timezone.utc)

    await db.flush()
    await db.refresh(certificate)
    await db.refresh(dj)

    # ── Queue PDF generation ──────────────────────────────────
    task_id: Optional[str] = None
    pdf_url: Optional[str] = None

    try:
        from tasks.pdf_tasks import (  # type: ignore[import]
            generate_destruction_certificate_pdf,
        )

        task = generate_destruction_certificate_pdf.delay(
            certificate_id=str(cert_id),
            destruction_job_id=str(job_id),
        )
        task_id = task.id
        logger.info("PDF generation queued: task_id=%s cert_id=%s", task_id, cert_id)
    except Exception as exc:
        # Celery unavailable — attempt inline PDF generation
        logger.warning(
            "Could not queue PDF generation for cert %s: %s — trying inline",
            cert_id,
            exc,
        )
        try:
            import os

            output_dir = os.path.join(
                settings.REPORT_OUTPUT_DIR, "destruction-certificates"
            )
            os.makedirs(output_dir, exist_ok=True)
            pdf_path = os.path.join(output_dir, f"{cert_id}.pdf")
            _generate_destruction_cert_inline(dj, certificate, pdf_path)
            certificate.pdf_path = pdf_path
            await db.flush()
            await db.refresh(certificate)
            pdf_url = (
                f"{settings.BACKEND_URL}/static/destruction-certificates/{cert_id}.pdf"
            )
            logger.info("Inline PDF generated at %s", pdf_path)
        except Exception as gen_exc:
            logger.error("Inline PDF generation failed: %s", gen_exc)

    logger.info(
        "Certificate of Destruction %s issued for job %s by user %s",
        cert_id,
        job_id,
        current_user["sub"],
    )

    return {
        "certificate_id": str(cert_id),
        "destruction_job_id": str(job_id),
        "cert_type": "destruction",
        "client_id": str(client_id_for_cert) if client_id_for_cert else None,
        "issued_at": certificate.issued_at.isoformat(),
        "issued_by": current_user["sub"],
        "witness_hitech_id": str(dj.witness_hitech_id),
        "witness_client_name": dj.witness_client_name,
        "witness_client_designation": dj.witness_client_designation,
        "destruction_method": dj.destruction_method,
        "destruction_date": dj.destruction_date.isoformat()
        if dj.destruction_date
        else None,
        "destruction_location": dj.destruction_location,
        "goods_description": dj.goods_description,
        "weight_kg": float(dj.weight_kg) if dj.weight_kg else None,
        "quantity_units": dj.quantity_units,
        "reason_codes": dj.reason_codes,
        "is_void": False,
        "pdf_url": pdf_url,
        "task_id": task_id,
        "status": "ready" if pdf_url else ("queued" if task_id else "pending"),
        "message": (
            "Certificate of Destruction generated successfully."
            if pdf_url
            else (
                "Certificate created. PDF generation has been queued."
                if task_id
                else "Certificate created. PDF generation is pending."
            )
        ),
    }


def _generate_destruction_cert_inline(
    dj: DestructionJob,
    cert: Certificate,
    output_path: str,
) -> None:
    """
    Generates a minimal Certificate of Destruction PDF using ReportLab.
    Used as a fallback when the Celery PDF task worker is unavailable.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import cm
        from reportlab.pdfgen import canvas as rl_canvas

        c = rl_canvas.Canvas(output_path, pagesize=A4)
        width, height = A4

        # ── Header ────────────────────────────────────────────
        c.setFont("Helvetica-Bold", 18)
        c.drawCentredString(width / 2, height - 3 * cm, "CERTIFICATE OF DESTRUCTION")

        c.setFont("Helvetica-Bold", 12)
        c.drawCentredString(
            width / 2,
            height - 4 * cm,
            "HI-TECH WASTE MANAGEMENT SDN. BHD.",
        )

        # ── Certificate details ───────────────────────────────
        c.setFont("Helvetica", 11)
        y = height - 6 * cm
        line_height = 0.7 * cm

        details = [
            ("Certificate ID", str(cert.id)),
            ("Issued At", cert.issued_at.isoformat() if cert.issued_at else "N/A"),
            (
                "Goods Description",
                dj.goods_description[:120] + "..."
                if len(dj.goods_description) > 120
                else dj.goods_description,
            ),
            ("Quantity", str(dj.quantity_units) if dj.quantity_units else "N/A"),
            ("Weight (kg)", str(float(dj.weight_kg)) if dj.weight_kg else "N/A"),
            ("Destruction Method", dj.destruction_method),
            (
                "Destruction Date",
                dj.destruction_date.isoformat() if dj.destruction_date else "N/A",
            ),
            ("Destruction Location", (dj.destruction_location or "N/A")[:80]),
            ("Reason Codes", ", ".join(dj.reason_codes) if dj.reason_codes else "N/A"),
        ]

        for label, value in details:
            c.setFont("Helvetica-Bold", 10)
            c.drawString(2 * cm, y, f"{label}:")
            c.setFont("Helvetica", 10)
            c.drawString(7 * cm, y, value)
            y -= line_height

        # ── Witness signatures ────────────────────────────────
        y -= cm
        c.setFont("Helvetica-Bold", 11)
        c.drawString(2 * cm, y, "WITNESS SIGNATURES")
        y -= line_height

        c.setFont("Helvetica", 10)
        c.drawString(2 * cm, y, f"Hi-Tech Witness ID: {dj.witness_hitech_id or 'N/A'}")
        y -= line_height
        c.drawString(
            2 * cm,
            y,
            f"Client Witness: {dj.witness_client_name or 'N/A'} "
            f"({dj.witness_client_designation or 'N/A'})",
        )

        # ── Footer ────────────────────────────────────────────
        c.setFont("Helvetica-Oblique", 8)
        c.drawString(
            2 * cm,
            1.5 * cm,
            "This certificate is computer-generated and requires authorised signatures to be legally binding.",
        )

        c.save()

    except ImportError:
        # ReportLab not available — write a text fallback
        txt_path = output_path.replace(".pdf", ".txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(
                f"CERTIFICATE OF DESTRUCTION\n"
                f"Certificate ID: {cert.id}\n"
                f"Issued At: {cert.issued_at}\n"
                f"Goods: {dj.goods_description}\n"
                f"Method: {dj.destruction_method}\n"
                f"Date: {dj.destruction_date}\n"
                f"Location: {dj.destruction_location}\n"
                f"Hi-Tech Witness: {dj.witness_hitech_id}\n"
                f"Client Witness: {dj.witness_client_name} ({dj.witness_client_designation})\n"
            )


# =============================================================
# GET /jobs/{id}/certificate/download — download certificate PDF
# =============================================================


@router.get(
    "/jobs/{job_id}/certificate/download",
    summary="Download Certificate of Destruction PDF",
)
async def download_certificate(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> Any:
    """
    Downloads the Certificate of Destruction PDF for a destruction job.

    Returns 202 Accepted if the PDF is still being generated,
    or 200 OK with the PDF file content if ready.
    """
    import os

    from fastapi.responses import FileResponse, JSONResponse

    dj = await _get_destruction_job_or_404(job_id, db)

    if not dj.certificate_issued or dj.certificate_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "No certificate has been issued for this destruction job yet. "
                "Use POST /destruction/jobs/{id}/certificate to generate one."
            ),
        )

    cert_result = await db.execute(
        select(Certificate).where(
            Certificate.id == dj.certificate_id,
            Certificate.cert_type == "destruction",
        )
    )
    certificate = cert_result.scalar_one_or_none()

    if certificate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Certificate record {dj.certificate_id} not found",
        )

    if certificate.is_void:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=f"Certificate {dj.certificate_id} has been voided",
        )

    if not certificate.pdf_path or not os.path.exists(certificate.pdf_path):
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={
                "status": "pending",
                "certificate_id": str(dj.certificate_id),
                "destruction_job_id": str(job_id),
                "message": "PDF is still being generated. Please retry in a few seconds.",
            },
        )

    return FileResponse(
        path=certificate.pdf_path,
        media_type="application/pdf",
        filename=f"destruction_certificate_{dj.certificate_id}.pdf",
    )


# =============================================================
# PATCH /jobs/{id}/certificate/void — void an issued certificate
# =============================================================


@router.patch(
    "/jobs/{job_id}/certificate/void",
    summary="Void an issued Certificate of Destruction",
    description=(
        "Marks the Certificate of Destruction as void. "
        "Voided certificates are retained in the database for audit purposes "
        "but are excluded from active reports. "
        "Only superadmin and management roles can void certificates."
    ),
    dependencies=[Depends(require_roles("superadmin", "management"))],
)
async def void_certificate(
    job_id: uuid.UUID,
    reason: str = Query(
        ..., min_length=5, description="Reason for voiding the certificate"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    """Voids the Certificate of Destruction for a destruction job."""
    dj = await _get_destruction_job_or_404(job_id, db)

    if not dj.certificate_issued or dj.certificate_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No certificate has been issued for this destruction job",
        )

    cert_result = await db.execute(
        select(Certificate).where(
            Certificate.id == dj.certificate_id,
            Certificate.cert_type == "destruction",
        )
    )
    certificate = cert_result.scalar_one_or_none()

    if certificate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Certificate {dj.certificate_id} not found",
        )

    if certificate.is_void:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Certificate {dj.certificate_id} is already voided",
        )

    certificate.is_void = True
    dj.certificate_issued = False
    dj.updated_at = datetime.now(timezone.utc)

    await db.flush()

    logger.warning(
        "Certificate %s VOIDED for destruction job %s | reason=%s | by user=%s",
        dj.certificate_id,
        job_id,
        reason,
        current_user["sub"],
    )

    return {
        "message": f"Certificate {dj.certificate_id} has been voided.",
        "certificate_id": str(dj.certificate_id),
        "destruction_job_id": str(job_id),
        "voided_by": current_user["sub"],
        "reason": reason,
    }


# =============================================================
# GET /stats/summary — destruction statistics
# =============================================================


@router.get(
    "/stats/summary",
    response_model=Dict[str, Any],
    summary="Destruction job statistics",
    description=(
        "Returns aggregate statistics for destruction jobs: "
        "total jobs, breakdown by method, total weight destroyed, "
        "certificate issuance rate."
    ),
)
async def destruction_stats(
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    """Aggregate statistics for destruction jobs."""

    # Total jobs by destruction method
    method_stmt = select(
        DestructionJob.destruction_method,
        func.count(DestructionJob.id).label("cnt"),
        func.coalesce(func.sum(DestructionJob.weight_kg), 0).label("total_kg"),
    ).group_by(DestructionJob.destruction_method)
    method_result = await db.execute(method_stmt)
    by_method: Dict[str, Any] = {}
    total_weight = 0.0
    total_jobs = 0
    for row in method_result:
        by_method[row.destruction_method] = {
            "count": row.cnt,
            "total_kg": float(row.total_kg),
        }
        total_weight += float(row.total_kg)
        total_jobs += row.cnt

    # Certificate issuance rate
    cert_stmt = select(
        func.count(DestructionJob.id).label("total"),
        func.count(DestructionJob.id)
        .filter(DestructionJob.certificate_issued == True)  # noqa: E712
        .label("with_cert"),
    )
    cert_result = await db.execute(cert_stmt)
    cert_row = cert_result.one()
    cert_rate = (
        round(cert_row.with_cert / cert_row.total * 100, 2)
        if cert_row.total > 0
        else 0.0
    )

    # Most common reason codes (aggregate from ARRAY column)
    # This requires a more complex query — approximated here
    reason_stmt = select(DestructionJob.reason_codes).where(
        DestructionJob.reason_codes != None  # noqa: E711
    )
    reason_result = await db.execute(reason_stmt)
    reason_counts: Dict[str, int] = {}
    for row in reason_result:
        codes = row.reason_codes or []
        for code in codes:
            reason_counts[code] = reason_counts.get(code, 0) + 1

    top_reason_codes = sorted(reason_counts.items(), key=lambda x: x[1], reverse=True)[
        :5
    ]

    return {
        "total_jobs": total_jobs,
        "total_weight_destroyed_kg": total_weight,
        "by_destruction_method": by_method,
        "certificate_issuance_rate_pct": cert_rate,
        "jobs_with_certificate": cert_row.with_cert,
        "jobs_without_certificate": cert_row.total - cert_row.with_cert,
        "top_reason_codes": [
            {"code": code, "count": count} for code, count in top_reason_codes
        ],
    }
