# =============================================================
# Hi-Tech Waste Management — Clients Router
# Full CRUD + sub-resource endpoints for the clients domain
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
from models.client import (
    Client,
    ClientCreate,
    ClientListItem,
    ClientRead,
    ClientUpdate,
    ClientWasteStream,
    ClientWasteStreamCreate,
    ClientWasteStreamRead,
)
from models.document import Certificate, CertificateRead
from models.esg import CarbonRecord
from models.job import Job, JobRead
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from routers.auth import get_current_user, require_roles

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()

# =============================================================
# Helper — fetch client or 404
# =============================================================


async def _get_client_or_404(client_id: uuid.UUID, db: AsyncSession) -> Client:
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client {client_id} not found",
        )
    return client


# =============================================================
# GET /  — list clients
# =============================================================


@router.get(
    "/",
    response_model=Dict[str, Any],
    summary="List clients",
    description=(
        "Returns a paginated list of clients. "
        "Optionally filter by company_name (partial match) and/or is_active status."
    ),
)
async def list_clients(
    skip: int = Query(default=0, ge=0, description="Number of records to skip"),
    limit: int = Query(default=50, ge=1, le=200, description="Max records to return"),
    search: Optional[str] = Query(
        default=None, description="Partial match on company_name"
    ),
    is_active: Optional[bool] = Query(
        default=None, description="Filter by active status"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    """List clients with pagination, search, and active-status filter."""

    # Build base query
    stmt = select(Client)
    count_stmt = select(func.count()).select_from(Client)

    filters = []
    if search:
        filters.append(Client.company_name.ilike(f"%{search}%"))
    if is_active is not None:
        filters.append(Client.is_active == is_active)

    if filters:
        stmt = stmt.where(and_(*filters))
        count_stmt = count_stmt.where(and_(*filters))

    stmt = stmt.order_by(Client.company_name).offset(skip).limit(limit)

    total_result = await db.execute(count_stmt)
    total: int = total_result.scalar_one()

    result = await db.execute(stmt)
    clients = result.scalars().all()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": [ClientListItem.model_validate(c) for c in clients],
    }


# =============================================================
# POST /  — create client
# =============================================================


@router.post(
    "/",
    response_model=ClientRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create client",
    dependencies=[
        Depends(require_roles("superadmin", "management", "operations_manager"))
    ],
)
async def create_client(
    payload: ClientCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> ClientRead:
    """Create a new client record, optionally with initial waste streams."""

    # Check SSM uniqueness if provided
    if payload.ssm_number:
        existing = await db.execute(
            select(Client).where(Client.ssm_number == payload.ssm_number)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A client with SSM number '{payload.ssm_number}' already exists",
            )

    waste_streams_data = payload.waste_streams or []
    client_data = payload.model_dump(exclude={"waste_streams"})
    client = Client(**client_data)
    db.add(client)
    await db.flush()  # get client.id before adding waste streams

    for ws_data in waste_streams_data:
        ws = ClientWasteStream(client_id=client.id, **ws_data.model_dump())
        db.add(ws)

    await db.flush()
    await db.refresh(client)
    logger.info("Created client %s by user %s", client.id, current_user.get("sub"))
    return ClientRead.model_validate(client)


# =============================================================
# GET /{id}  — client detail with waste streams
# =============================================================


@router.get(
    "/{client_id}",
    response_model=ClientRead,
    summary="Get client detail",
)
async def get_client(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> ClientRead:
    """Return full client details including waste streams."""
    client = await _get_client_or_404(client_id, db)
    return ClientRead.model_validate(client)


# =============================================================
# PUT /{id}  — update client
# =============================================================


@router.put(
    "/{client_id}",
    response_model=ClientRead,
    summary="Update client",
    dependencies=[
        Depends(require_roles("superadmin", "management", "operations_manager"))
    ],
)
async def update_client(
    client_id: uuid.UUID,
    payload: ClientUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> ClientRead:
    """Partially update a client record."""
    client = await _get_client_or_404(client_id, db)

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(client, field, value)

    await db.flush()
    await db.refresh(client)
    logger.info("Updated client %s by user %s", client_id, current_user.get("sub"))
    return ClientRead.model_validate(client)


# =============================================================
# POST /{id}/waste-streams  — add a waste stream
# =============================================================


@router.post(
    "/{client_id}/waste-streams",
    response_model=ClientWasteStreamRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add waste stream to client",
    dependencies=[
        Depends(require_roles("superadmin", "management", "operations_manager"))
    ],
)
async def add_waste_stream(
    client_id: uuid.UUID,
    payload: ClientWasteStreamCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> ClientWasteStreamRead:
    """Add a new waste stream to an existing client."""
    await _get_client_or_404(client_id, db)
    ws = ClientWasteStream(client_id=client_id, **payload.model_dump())
    db.add(ws)
    await db.flush()
    await db.refresh(ws)
    return ClientWasteStreamRead.model_validate(ws)


# =============================================================
# GET /{id}/jobs  — paginated jobs for client
# =============================================================


@router.get(
    "/{client_id}/jobs",
    response_model=Dict[str, Any],
    summary="List jobs for a client",
)
async def list_client_jobs(
    client_id: uuid.UUID,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    status_filter: Optional[str] = Query(
        default=None, alias="status", description="Filter by job status"
    ),
    job_type: Optional[str] = Query(default=None, description="Filter by job type"),
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return paginated jobs belonging to a specific client."""
    await _get_client_or_404(client_id, db)

    filters = [Job.client_id == client_id]
    if status_filter:
        filters.append(Job.status == status_filter)
    if job_type:
        filters.append(Job.job_type == job_type)

    count_stmt = select(func.count()).select_from(Job).where(and_(*filters))
    total_result = await db.execute(count_stmt)
    total: int = total_result.scalar_one()

    stmt = (
        select(Job)
        .where(and_(*filters))
        .order_by(Job.scheduled_date.desc().nulls_last(), Job.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    jobs = result.scalars().all()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "client_id": str(client_id),
        "items": [JobRead.model_validate(j) for j in jobs],
    }


# =============================================================
# GET /{id}/esg-summary  — aggregate ESG/carbon data
# =============================================================


@router.get(
    "/{client_id}/esg-summary",
    response_model=Dict[str, Any],
    summary="ESG summary for a client",
    description=(
        "Aggregate carbon data for a client over an optional date range. "
        "Returns total CO₂ avoided, diversion rate, and recycling percentage."
    ),
)
async def client_esg_summary(
    client_id: uuid.UUID,
    date_from: Optional[date] = Query(
        default=None, description="Start date for the reporting period (inclusive)"
    ),
    date_to: Optional[date] = Query(
        default=None, description="End date for the reporting period (inclusive)"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Aggregate ESG metrics for a client:
    - total_co2_avoided_kgco2e : sum of carbon credits minus transport emissions
    - total_transport_kgco2e   : total transport emissions
    - total_landfill_avoided   : landfill avoidance credits
    - total_recycling_credit   : recycling credits
    - total_wte_credit         : waste-to-energy credits
    - record_count             : number of carbon records in the period
    """
    await _get_client_or_404(client_id, db)

    filters: list = [CarbonRecord.client_id == client_id]
    if date_from:
        dt_from = datetime(
            date_from.year, date_from.month, date_from.day, tzinfo=timezone.utc
        )
        filters.append(CarbonRecord.calculated_at >= dt_from)
    if date_to:
        dt_to = datetime(
            date_to.year, date_to.month, date_to.day, 23, 59, 59, tzinfo=timezone.utc
        )
        filters.append(CarbonRecord.calculated_at <= dt_to)

    stmt = select(
        func.count(CarbonRecord.id).label("record_count"),
        func.coalesce(func.sum(CarbonRecord.transport_emissions_kgco2e), 0).label(
            "total_transport"
        ),
        func.coalesce(func.sum(CarbonRecord.landfill_avoidance_kgco2e), 0).label(
            "total_landfill"
        ),
        func.coalesce(func.sum(CarbonRecord.recycling_credit_kgco2e), 0).label(
            "total_recycling"
        ),
        func.coalesce(func.sum(CarbonRecord.wte_credit_kgco2e), 0).label("total_wte"),
        func.coalesce(func.sum(CarbonRecord.net_carbon_impact_kgco2e), 0).label(
            "total_net"
        ),
    ).where(and_(*filters))

    result = await db.execute(stmt)
    row = result.one()

    total_transport = Decimal(str(row.total_transport))
    total_landfill = Decimal(str(row.total_landfill))
    total_recycling = Decimal(str(row.total_recycling))
    total_wte = Decimal(str(row.total_wte))
    total_net = Decimal(str(row.total_net))

    # CO₂ avoided = credits sum (landfill + recycling + wte) - transport
    total_co2_avoided = total_landfill + total_recycling + total_wte - total_transport

    # Get total waste tonnage from weighbridge records for diversion rate
    from models.recyclable import RecyclableRecord
    from models.weighbridge import WeighbridgeRecord

    wb_stmt = select(
        func.coalesce(func.sum(WeighbridgeRecord.net_weight_kg), 0).label(
            "total_waste"
        ),
    ).where(WeighbridgeRecord.client_id == client_id)
    if date_from:
        wb_stmt = wb_stmt.where(WeighbridgeRecord.recorded_at >= dt_from)  # type: ignore[possibly-undefined]
    if date_to:
        wb_stmt = wb_stmt.where(WeighbridgeRecord.recorded_at <= dt_to)  # type: ignore[possibly-undefined]

    wb_result = await db.execute(wb_stmt)
    wb_row = wb_result.one()
    total_waste_kg = Decimal(str(wb_row.total_waste))

    # Recyclable total for recycling percentage
    rec_stmt = select(
        func.coalesce(func.sum(RecyclableRecord.total_recyclable_kg), 0).label(
            "total_rec"
        ),
    ).where(RecyclableRecord.client_id == client_id)
    if date_from:
        rec_stmt = rec_stmt.where(RecyclableRecord.recorded_at >= dt_from)  # type: ignore[possibly-undefined]
    if date_to:
        rec_stmt = rec_stmt.where(RecyclableRecord.recorded_at <= dt_to)  # type: ignore[possibly-undefined]

    rec_result = await db.execute(rec_stmt)
    rec_row = rec_result.one()
    total_recyclable_kg = Decimal(str(rec_row.total_rec))

    # Compute rates
    diversion_rate_pct: Optional[Decimal] = None
    recycling_pct: Optional[Decimal] = None
    if total_waste_kg > 0:
        diversion_rate_pct = (total_recyclable_kg / total_waste_kg * 100).quantize(
            Decimal("0.01")
        )
        recycling_pct = (
            diversion_rate_pct  # simplified; can refine with SW + WtE diverted
        )

    return {
        "client_id": str(client_id),
        "period_from": date_from.isoformat() if date_from else None,
        "period_to": date_to.isoformat() if date_to else None,
        "record_count": row.record_count,
        "total_co2_avoided_kgco2e": float(total_co2_avoided),
        "total_transport_emissions_kgco2e": float(total_transport),
        "total_landfill_avoidance_kgco2e": float(total_landfill),
        "total_recycling_credit_kgco2e": float(total_recycling),
        "total_wte_credit_kgco2e": float(total_wte),
        "total_net_carbon_impact_kgco2e": float(total_net),
        "total_waste_processed_kg": float(total_waste_kg),
        "total_recyclable_kg": float(total_recyclable_kg),
        "diversion_rate_pct": float(diversion_rate_pct)
        if diversion_rate_pct is not None
        else None,
        "recycling_pct": float(recycling_pct) if recycling_pct is not None else None,
    }


# =============================================================
# GET /{id}/certificates  — list certificates for client
# =============================================================


@router.get(
    "/{client_id}/certificates",
    response_model=Dict[str, Any],
    summary="List certificates for a client",
)
async def list_client_certificates(
    client_id: uuid.UUID,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    cert_type: Optional[str] = Query(
        default=None,
        description="Filter by certificate type: recycling | destruction | esg_report",
    ),
    include_void: bool = Query(
        default=False, description="Include voided certificates"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return all certificates issued for a specific client."""
    await _get_client_or_404(client_id, db)

    filters: list = [Certificate.client_id == client_id]
    if cert_type:
        filters.append(Certificate.cert_type == cert_type)
    if not include_void:
        filters.append(Certificate.is_void == False)

    count_stmt = select(func.count()).select_from(Certificate).where(and_(*filters))
    total_result = await db.execute(count_stmt)
    total: int = total_result.scalar_one()

    stmt = (
        select(Certificate)
        .where(and_(*filters))
        .order_by(Certificate.issued_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    certs = result.scalars().all()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "client_id": str(client_id),
        "items": [CertificateRead.model_validate(c) for c in certs],
    }


# =============================================================
# DELETE /{id}  — soft-delete (deactivate) client
# =============================================================


@router.delete(
    "/{client_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Deactivate (soft-delete) a client",
    dependencies=[Depends(require_roles("superadmin", "management"))],
)
async def deactivate_client(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> None:
    """
    Soft-deletes a client by setting is_active=False.
    The record is retained for historical reporting and audit purposes.
    """
    client = await _get_client_or_404(client_id, db)
    client.is_active = False
    await db.flush()
    logger.info("Deactivated client %s by user %s", client_id, current_user.get("sub"))
