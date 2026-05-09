# =============================================================
# Hi-Tech Waste Management — Recyclables Router
# Material records, downstream buyers, stats, and certificate generation
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
from models.document import Certificate
from models.recyclable import (
    DownstreamBuyer,
    DownstreamBuyerCreate,
    DownstreamBuyerRead,
    DownstreamBuyerUpdate,
    MaterialBreakdown,
    RecyclableRecord,
    RecyclableRecordCreate,
    RecyclableRecordRead,
    RecyclableRecordUpdate,
    RecyclableStatsMaterial,
    RecyclableStatsResponse,
)
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


async def _get_record_or_404(
    record_id: uuid.UUID, db: AsyncSession
) -> RecyclableRecord:
    result = await db.execute(
        select(RecyclableRecord).where(RecyclableRecord.id == record_id)
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recyclable record {record_id} not found",
        )
    return record


async def _get_buyer_or_404(buyer_id: uuid.UUID, db: AsyncSession) -> DownstreamBuyer:
    result = await db.execute(
        select(DownstreamBuyer).where(DownstreamBuyer.id == buyer_id)
    )
    buyer = result.scalar_one_or_none()
    if buyer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Downstream buyer {buyer_id} not found",
        )
    return buyer


# =============================================================
# GET /records — list recyclable records
# =============================================================


@router.get(
    "/records",
    response_model=Dict[str, Any],
    summary="List recyclable material records",
    description=(
        "Returns a paginated list of recyclable collection records. "
        "Filter by client, date range, buyer, or material type."
    ),
)
async def list_records(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    client_id: Optional[uuid.UUID] = Query(None, description="Filter by client UUID"),
    job_id: Optional[uuid.UUID] = Query(None, description="Filter by job UUID"),
    buyer_id: Optional[uuid.UUID] = Query(
        None, description="Filter by downstream buyer UUID"
    ),
    date_from: Optional[date] = Query(
        None, description="Filter from this date (inclusive)"
    ),
    date_to: Optional[date] = Query(
        None, description="Filter to this date (inclusive)"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    """Returns paginated recyclable records with optional filters."""

    filters: list = []

    # Client portal users see only their own records
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
        filters.append(RecyclableRecord.client_id == client_obj.id)
    elif client_id is not None:
        filters.append(RecyclableRecord.client_id == client_id)

    if job_id is not None:
        filters.append(RecyclableRecord.job_id == job_id)
    if buyer_id is not None:
        filters.append(RecyclableRecord.buyer_id == buyer_id)

    if date_from:
        dt_from = datetime(
            date_from.year, date_from.month, date_from.day, tzinfo=timezone.utc
        )
        filters.append(RecyclableRecord.recorded_at >= dt_from)
    if date_to:
        dt_to = datetime(
            date_to.year, date_to.month, date_to.day, 23, 59, 59, tzinfo=timezone.utc
        )
        filters.append(RecyclableRecord.recorded_at <= dt_to)

    base_stmt = select(RecyclableRecord)
    if filters:
        base_stmt = base_stmt.where(and_(*filters))

    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total_result = await db.execute(count_stmt)
    total: int = total_result.scalar_one()

    stmt = (
        base_stmt.order_by(RecyclableRecord.recorded_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    records = result.scalars().all()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": [RecyclableRecordRead.model_validate(r) for r in records],
    }


# =============================================================
# POST /records — create recyclable record
# =============================================================


@router.post(
    "/records",
    response_model=RecyclableRecordRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a recyclable material record",
    description=(
        "Creates a new recyclable collection record. "
        "total_recyclable_kg is auto-computed from material_breakdown if not provided."
    ),
    dependencies=[Depends(require_roles(*STAFF_ROLES))],
)
async def create_record(
    payload: RecyclableRecordCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> RecyclableRecordRead:
    """
    Creates a new recyclable record.

    - If `material_breakdown` is provided and `total_recyclable_kg` is omitted,
      the total is computed as the sum of all material weights.
    - If a `buyer_id` is provided, validates that the buyer exists and is active.
    """
    # Validate buyer if provided
    if payload.buyer_id is not None:
        buyer = await _get_buyer_or_404(payload.buyer_id, db)
        if not buyer.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Downstream buyer {payload.buyer_id} is inactive",
            )

    # Validate job if provided
    if payload.job_id is not None:
        from models.job import Job

        job_result = await db.execute(select(Job).where(Job.id == payload.job_id))
        if job_result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {payload.job_id} not found",
            )

    # Resolve total_recyclable_kg from breakdown if not provided
    total_recyclable_kg = payload.total_recyclable_kg
    material_breakdown_dict: Optional[Dict[str, Any]] = None

    if payload.material_breakdown is not None:
        material_breakdown_dict = payload.material_breakdown.to_dict()
        if total_recyclable_kg is None:
            total_recyclable_kg = payload.material_breakdown.total_kg()

    recorded_at = payload.recorded_at or datetime.now(timezone.utc)

    record = RecyclableRecord(
        id=uuid.uuid4(),
        job_id=payload.job_id,
        client_id=payload.client_id,
        recorded_at=recorded_at,
        material_breakdown=material_breakdown_dict,
        total_recyclable_kg=total_recyclable_kg,
        buyer_id=payload.buyer_id,
        sale_value_myr=payload.sale_value_myr,
    )
    db.add(record)
    await db.flush()
    await db.refresh(record)

    logger.info(
        "RecyclableRecord created id=%s total_kg=%s by user=%s",
        record.id,
        record.total_recyclable_kg,
        current_user.get("sub"),
    )
    return RecyclableRecordRead.model_validate(record)


# =============================================================
# GET /records/{id} — get single record
# =============================================================


@router.get(
    "/records/{record_id}",
    response_model=RecyclableRecordRead,
    summary="Get a recyclable record by ID",
)
async def get_record(
    record_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> RecyclableRecordRead:
    """Returns full details of a single recyclable record."""
    record = await _get_record_or_404(record_id, db)
    return RecyclableRecordRead.model_validate(record)


# =============================================================
# PUT /records/{id} — update record
# =============================================================


@router.put(
    "/records/{record_id}",
    response_model=RecyclableRecordRead,
    summary="Update a recyclable record",
    dependencies=[Depends(require_roles(*STAFF_ROLES))],
)
async def update_record(
    record_id: uuid.UUID,
    payload: RecyclableRecordUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> RecyclableRecordRead:
    """Partially updates a recyclable record."""
    record = await _get_record_or_404(record_id, db)

    update_data = payload.model_dump(exclude_unset=True)

    # Handle material_breakdown specially — convert to dict for JSON storage
    if (
        "material_breakdown" in update_data
        and update_data["material_breakdown"] is not None
    ):
        mb: MaterialBreakdown = update_data["material_breakdown"]
        update_data["material_breakdown"] = mb.to_dict()
        if payload.total_recyclable_kg is None:
            update_data["total_recyclable_kg"] = mb.total_kg()

    for field, value in update_data.items():
        setattr(record, field, value)

    await db.flush()
    await db.refresh(record)
    return RecyclableRecordRead.model_validate(record)


# =============================================================
# DELETE /records/{id} — delete record
# =============================================================


@router.delete(
    "/records/{record_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Delete a recyclable record",
    dependencies=[Depends(require_roles(*MANAGEMENT_ROLES))],
)
async def delete_record(
    record_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> None:
    """Hard-deletes a recyclable record. Management roles only."""
    record = await _get_record_or_404(record_id, db)
    await db.delete(record)
    await db.flush()
    logger.info(
        "RecyclableRecord %s deleted by user %s", record_id, current_user["sub"]
    )


# =============================================================
# GET /stats — material breakdown stats and revenue
# =============================================================


@router.get(
    "/stats",
    response_model=RecyclableStatsResponse,
    summary="Recyclables aggregate statistics",
    description=(
        "Returns aggregate totals by material type, total revenue from sales, "
        "and the top performing materials by volume."
    ),
)
async def get_stats(
    client_id: Optional[uuid.UUID] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> RecyclableStatsResponse:
    """
    Aggregate recyclable stats:
    - Per-material totals (paper, PET, HDPE, aluminium, ferrous, glass, e-waste)
    - Total revenue from downstream buyer sales (MYR)
    - Top material by weight
    - Period summary
    """
    filters: list = []

    if current_user.get("role") == "client":
        from models.client import Client as ClientModel

        client_result = await db.execute(
            select(ClientModel).where(
                ClientModel.portal_user_id == uuid.UUID(current_user["sub"])
            )
        )
        client_obj = client_result.scalar_one_or_none()
        if client_obj is None:
            return RecyclableStatsResponse(
                total_recyclable_kg=Decimal("0"),
                total_revenue_myr=Decimal("0"),
                material_breakdown=[],
                record_count=0,
            )
        filters.append(RecyclableRecord.client_id == client_obj.id)
    elif client_id is not None:
        filters.append(RecyclableRecord.client_id == client_id)

    if date_from:
        dt_from = datetime(
            date_from.year, date_from.month, date_from.day, tzinfo=timezone.utc
        )
        filters.append(RecyclableRecord.recorded_at >= dt_from)
    if date_to:
        dt_to = datetime(
            date_to.year, date_to.month, date_to.day, 23, 59, 59, tzinfo=timezone.utc
        )
        filters.append(RecyclableRecord.recorded_at <= dt_to)

    # Fetch all matching records
    stmt = select(RecyclableRecord)
    if filters:
        stmt = stmt.where(and_(*filters))

    result = await db.execute(stmt)
    records = result.scalars().all()

    # Aggregate totals
    total_recyclable_kg = Decimal("0")
    total_revenue_myr = Decimal("0")

    material_totals: Dict[str, Decimal] = {
        "paper": Decimal("0"),
        "pet": Decimal("0"),
        "hdpe": Decimal("0"),
        "aluminium": Decimal("0"),
        "ferrous": Decimal("0"),
        "glass": Decimal("0"),
        "ewaste": Decimal("0"),
    }
    material_revenue: Dict[str, Decimal] = {k: Decimal("0") for k in material_totals}

    for rec in records:
        if rec.total_recyclable_kg:
            total_recyclable_kg += Decimal(str(rec.total_recyclable_kg))
        if rec.sale_value_myr:
            total_revenue_myr += Decimal(str(rec.sale_value_myr))

        if rec.material_breakdown:
            mb = rec.material_breakdown
            for key in material_totals:
                json_key = f"{key}_kg"
                if json_key in mb and mb[json_key] is not None:
                    kg_val = Decimal(str(mb[json_key]))
                    material_totals[key] += kg_val

                    # Prorate revenue across materials if total_recyclable_kg known
                    if (
                        rec.sale_value_myr
                        and rec.total_recyclable_kg
                        and Decimal(str(rec.total_recyclable_kg)) > 0
                    ):
                        share = kg_val / Decimal(str(rec.total_recyclable_kg))
                        material_revenue[key] += share * Decimal(
                            str(rec.sale_value_myr)
                        )

    # Build material breakdown list sorted by kg descending
    breakdown: List[RecyclableStatsMaterial] = []
    for mat, total_kg in sorted(
        material_totals.items(), key=lambda x: x[1], reverse=True
    ):
        if total_kg > 0:
            breakdown.append(
                RecyclableStatsMaterial(
                    material=mat,
                    total_kg=total_kg.quantize(Decimal("0.001")),
                    revenue_myr=material_revenue[mat].quantize(Decimal("0.01"))
                    if material_revenue[mat] > 0
                    else None,
                )
            )

    top_material = breakdown[0].material if breakdown else None

    return RecyclableStatsResponse(
        period_from=date_from.isoformat() if date_from else None,
        period_to=date_to.isoformat() if date_to else None,
        total_recyclable_kg=total_recyclable_kg.quantize(Decimal("0.001")),
        total_revenue_myr=total_revenue_myr.quantize(Decimal("0.01")),
        material_breakdown=breakdown,
        top_material=top_material,
        record_count=len(records),
    )


# =============================================================
# GET /buyers — list downstream buyers
# =============================================================


@router.get(
    "/buyers",
    response_model=Dict[str, Any],
    summary="List downstream buyers",
    description="Returns a paginated list of licensed downstream recyclables buyers.",
)
async def list_buyers(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    material_type: Optional[str] = Query(
        None,
        description="Filter buyers who accept a specific material type, e.g. 'paper'",
    ),
    search: Optional[str] = Query(
        None, description="Partial match on company_name or license_number"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    """Returns a paginated list of downstream buyers with optional filters."""

    filters: list = []
    if is_active is not None:
        filters.append(DownstreamBuyer.is_active == is_active)
    if search:
        like = f"%{search}%"
        filters.append(
            or_(
                DownstreamBuyer.company_name.ilike(like),
                DownstreamBuyer.license_number.ilike(like),
            )
        )
    # material_type filter: check if the ARRAY contains the material
    if material_type:
        # PostgreSQL ARRAY contains check: material_types @> ARRAY['paper']
        from sqlalchemy.dialects.postgresql import array as pg_array

        filters.append(DownstreamBuyer.material_types.contains([material_type]))

    base_stmt = select(DownstreamBuyer)
    if filters:
        base_stmt = base_stmt.where(and_(*filters))

    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total_result = await db.execute(count_stmt)
    total: int = total_result.scalar_one()

    stmt = base_stmt.order_by(DownstreamBuyer.company_name).offset(skip).limit(limit)
    result = await db.execute(stmt)
    buyers = result.scalars().all()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": [DownstreamBuyerRead.model_validate(b) for b in buyers],
    }


# =============================================================
# POST /buyers — create downstream buyer
# =============================================================


@router.post(
    "/buyers",
    response_model=DownstreamBuyerRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new downstream buyer",
    dependencies=[Depends(require_roles(*MANAGEMENT_ROLES))],
)
async def create_buyer(
    payload: DownstreamBuyerCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> DownstreamBuyerRead:
    """Registers a new licensed downstream recyclables buyer."""

    # Check license_number uniqueness if provided
    if payload.license_number:
        existing = await db.execute(
            select(DownstreamBuyer).where(
                DownstreamBuyer.license_number == payload.license_number
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A buyer with license number '{payload.license_number}' already exists",
            )

    buyer = DownstreamBuyer(
        id=uuid.uuid4(),
        company_name=payload.company_name,
        material_types=payload.material_types,
        contact_name=payload.contact_name,
        contact_phone=payload.contact_phone,
        address=payload.address,
        license_number=payload.license_number,
        is_active=payload.is_active,
    )
    db.add(buyer)
    await db.flush()
    await db.refresh(buyer)

    logger.info(
        "DownstreamBuyer '%s' registered by user %s",
        buyer.company_name,
        current_user.get("sub"),
    )
    return DownstreamBuyerRead.model_validate(buyer)


# =============================================================
# GET /buyers/{id} — buyer detail
# =============================================================


@router.get(
    "/buyers/{buyer_id}",
    response_model=DownstreamBuyerRead,
    summary="Get downstream buyer detail",
)
async def get_buyer(
    buyer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> DownstreamBuyerRead:
    """Returns full details of a single downstream buyer."""
    buyer = await _get_buyer_or_404(buyer_id, db)
    return DownstreamBuyerRead.model_validate(buyer)


# =============================================================
# PUT /buyers/{id} — update buyer
# =============================================================


@router.put(
    "/buyers/{buyer_id}",
    response_model=DownstreamBuyerRead,
    summary="Update a downstream buyer",
    dependencies=[Depends(require_roles(*MANAGEMENT_ROLES))],
)
async def update_buyer(
    buyer_id: uuid.UUID,
    payload: DownstreamBuyerUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> DownstreamBuyerRead:
    """Partially updates a downstream buyer record."""
    buyer = await _get_buyer_or_404(buyer_id, db)

    # Validate new license_number uniqueness
    if payload.license_number and payload.license_number != buyer.license_number:
        existing = await db.execute(
            select(DownstreamBuyer).where(
                DownstreamBuyer.license_number == payload.license_number,
                DownstreamBuyer.id != buyer_id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"License number '{payload.license_number}' is already in use",
            )

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(buyer, field, value)

    await db.flush()
    await db.refresh(buyer)
    return DownstreamBuyerRead.model_validate(buyer)


# =============================================================
# POST /{id}/certificate — generate recycling certificate
# =============================================================


@router.post(
    "/{record_id}/certificate",
    status_code=status.HTTP_201_CREATED,
    summary="Generate a Certificate of Recycling",
    description=(
        "Generates a Certificate of Recycling PDF for a specific recyclable record. "
        "Creates a Certificate DB entry, marks the record with the certificate_id, "
        "and queues the PDF generation as a Celery task."
    ),
    dependencies=[Depends(require_roles(*STAFF_ROLES))],
)
async def generate_certificate(
    record_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Generates a Certificate of Recycling for the specified recyclable record.

    Steps:
    1. Validates the record exists and has a non-zero total_recyclable_kg.
    2. Checks no valid (non-void) certificate already exists for this record.
    3. Creates a Certificate DB entry with cert_type='recycling'.
    4. Links the certificate back to the RecyclableRecord.
    5. Queues a Celery task to render the PDF (returns task_id for status polling).
    6. Returns certificate metadata including the task_id.
    """
    record = await _get_record_or_404(record_id, db)

    # Validate the record has data worth certifying
    if not record.total_recyclable_kg or record.total_recyclable_kg <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot generate certificate: total_recyclable_kg is zero or not set",
        )

    # Check if a certificate already exists for this record
    if record.certificate_id is not None:
        existing_cert = await db.execute(
            select(Certificate).where(
                Certificate.id == record.certificate_id,
                Certificate.is_void == False,  # noqa: E712
            )
        )
        if existing_cert.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"A valid recycling certificate already exists for this record "
                    f"(certificate_id={record.certificate_id}). "
                    "Void the existing certificate before generating a new one."
                ),
            )

    # Create certificate record
    cert_id = uuid.uuid4()
    certificate = Certificate(
        id=cert_id,
        cert_type="recycling",
        reference_id=record.id,
        client_id=record.client_id,
        issued_at=datetime.now(timezone.utc),
        issued_by=uuid.UUID(current_user["sub"]),
        is_void=False,
    )
    db.add(certificate)

    # Link certificate back to the recyclable record
    record.certificate_id = cert_id
    await db.flush()
    await db.refresh(certificate)

    # ── Queue Celery PDF generation task ─────────────────────
    task_id: Optional[str] = None
    pdf_url: Optional[str] = None

    try:
        from tasks.pdf_tasks import (
            generate_recycling_certificate_pdf,  # type: ignore[import]
        )

        task = generate_recycling_certificate_pdf.delay(
            certificate_id=str(cert_id),
            record_id=str(record.id),
            client_id=str(record.client_id) if record.client_id else None,
        )
        task_id = task.id
        logger.info(
            "PDF generation task queued: task_id=%s cert_id=%s", task_id, cert_id
        )
    except Exception as celery_exc:
        # Celery may not be available in dev — log but don't fail the endpoint
        logger.warning(
            "Could not queue PDF generation task for certificate %s: %s",
            cert_id,
            celery_exc,
        )

    logger.info(
        "Recycling certificate %s created for record %s by user %s",
        cert_id,
        record_id,
        current_user["sub"],
    )

    return {
        "certificate_id": str(cert_id),
        "record_id": str(record_id),
        "cert_type": "recycling",
        "client_id": str(record.client_id) if record.client_id else None,
        "issued_at": certificate.issued_at.isoformat(),
        "issued_by": current_user["sub"],
        "is_void": False,
        "pdf_url": pdf_url,
        "task_id": task_id,
        "status": "queued" if task_id else "pending",
        "message": (
            "Certificate created. PDF generation has been queued."
            if task_id
            else "Certificate created. PDF generation could not be queued — retry later."
        ),
    }


# =============================================================
# GET /certificates/{cert_id}/download — download cert PDF
# =============================================================


@router.get(
    "/certificates/{cert_id}/download",
    summary="Download a recycling certificate PDF",
)
async def download_certificate(
    cert_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> Any:
    """
    Returns the generated PDF for a recycling certificate.

    If the PDF is not yet ready (Celery task still running), returns a 202
    Accepted response with the task status instead.
    """
    import os

    from fastapi.responses import FileResponse

    cert_result = await db.execute(
        select(Certificate).where(
            Certificate.id == cert_id,
            Certificate.cert_type == "recycling",
        )
    )
    certificate = cert_result.scalar_one_or_none()
    if certificate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recycling certificate {cert_id} not found",
        )

    if certificate.is_void:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=f"Certificate {cert_id} has been voided",
        )

    # Check client-portal access
    if current_user.get("role") == "client":
        from models.client import Client as ClientModel

        client_result = await db.execute(
            select(ClientModel).where(
                ClientModel.portal_user_id == uuid.UUID(current_user["sub"])
            )
        )
        client_obj = client_result.scalar_one_or_none()
        if client_obj is None or client_obj.id != certificate.client_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this certificate",
            )

    if not certificate.pdf_path or not os.path.exists(certificate.pdf_path):
        # PDF not ready yet
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={
                "status": "pending",
                "certificate_id": str(cert_id),
                "message": "PDF is still being generated. Please retry in a few seconds.",
            },
        )

    return FileResponse(
        path=certificate.pdf_path,
        media_type="application/pdf",
        filename=f"recycling_certificate_{cert_id}.pdf",
    )
