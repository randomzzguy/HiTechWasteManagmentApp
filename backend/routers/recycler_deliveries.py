# =============================================================
# Hi-Tech Waste Management — Recycler Deliveries Router
# Container-to-recycler delivery: manifest, proof of delivery,
# weight reconciliation, buyer confirmation.
# =============================================================

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

from database import get_db
from fastapi import APIRouter, Depends, HTTPException, Query, status
from models.equipment import Container, PickupTrigger
from models.recyclable import DownstreamBuyer, RecyclableRecord
from models.recycler_delivery import (
    BuyerConfirmationSubmit,
    ProofOfDeliverySubmit,
    ReconciliationRead,
    ReconciliationReview,
    RecyclerDelivery,
    RecyclerDeliveryCreate,
    RecyclerDeliveryRead,
)
from models.user import User
from routers.auth import get_current_user, require_roles
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.get("/", response_model=List[RecyclerDeliveryRead])
async def list_deliveries(
    status: Optional[str] = Query(None),
    buyer_id: Optional[uuid.UUID] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List recycler deliveries with optional filters."""
    q = select(RecyclerDelivery)
    if status:
        q = q.where(RecyclerDelivery.status == status)
    if buyer_id:
        q = q.where(RecyclerDelivery.buyer_id == buyer_id)
    if date_from:
        q = q.where(RecyclerDelivery.planned_departure_at >= date_from)
    if date_to:
        q = q.where(RecyclerDelivery.planned_departure_at <= date_to)
    q = q.order_by(RecyclerDelivery.planned_departure_at.desc())
    result = await db.execute(q)
    return result.scalars().all()


@router.post(
    "/",
    response_model=RecyclerDeliveryRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles("superadmin", "operations_manager"))],
)
async def create_delivery(
    payload: RecyclerDeliveryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Initiate a recycler delivery with a formal manifest."""
    # Validate buyer is active
    buyer = await db.get(DownstreamBuyer, payload.buyer_id)
    if not buyer:
        raise HTTPException(status_code=404, detail="Downstream buyer not found")
    if not buyer.is_active:
        raise HTTPException(
            status_code=422,
            detail="Downstream buyer is inactive. Cannot create delivery.",
        )

    # Validate container exists
    container = await db.get(Container, payload.container_id)
    if not container:
        raise HTTPException(status_code=404, detail="Container not found")

    # Validate declared total weight matches breakdown sum (within 0.5 kg tolerance)
    breakdown_sum = Decimal(str(sum(payload.declared_material_breakdown.values())))
    variance = abs(payload.declared_total_weight_kg - breakdown_sum)
    if variance > Decimal("0.5"):
        raise HTTPException(
            status_code=422,
            detail=f"Declared total weight ({payload.declared_total_weight_kg} kg) does not match "
                   f"material breakdown sum ({breakdown_sum} kg). Variance: {variance} kg",
        )

    delivery = RecyclerDelivery(
        container_id=payload.container_id,
        buyer_id=payload.buyer_id,
        vehicle_id=payload.vehicle_id,
        driver_id=payload.driver_id,
        declared_material_breakdown=payload.declared_material_breakdown,
        declared_total_weight_kg=payload.declared_total_weight_kg,
        planned_departure_at=payload.planned_departure_at,
        status="pending_departure",
        created_by=current_user.id,
    )
    db.add(delivery)
    await db.flush()
    await db.refresh(delivery)
    return delivery


@router.get("/{delivery_id}", response_model=RecyclerDeliveryRead)
async def get_delivery(
    delivery_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    delivery = await db.get(RecyclerDelivery, delivery_id)
    if not delivery:
        raise HTTPException(status_code=404, detail="Recycler delivery not found")
    return delivery


@router.post(
    "/{delivery_id}/depart",
    response_model=RecyclerDeliveryRead,
)
async def mark_departed(
    delivery_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Driver marks departure from client site."""
    delivery = await db.get(RecyclerDelivery, delivery_id)
    if not delivery:
        raise HTTPException(status_code=404, detail="Recycler delivery not found")
    if delivery.status != "pending_departure":
        raise HTTPException(
            status_code=409,
            detail=f"Cannot depart from status '{delivery.status}'",
        )

    delivery.status = "in_transit"
    delivery.departed_at = datetime.now(timezone.utc)

    # Update container status
    container = await db.get(Container, delivery.container_id)
    if container:
        container.status = "in_transit"

    await db.flush()
    await db.refresh(delivery)
    return delivery


@router.post(
    "/{delivery_id}/arrive",
    response_model=RecyclerDeliveryRead,
)
async def mark_arrived(
    delivery_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Driver marks arrival at recycler facility."""
    delivery = await db.get(RecyclerDelivery, delivery_id)
    if not delivery:
        raise HTTPException(status_code=404, detail="Recycler delivery not found")
    if delivery.status != "in_transit":
        raise HTTPException(
            status_code=409,
            detail=f"Cannot mark arrived from status '{delivery.status}'",
        )

    delivery.status = "arrived"
    delivery.arrived_at = datetime.now(timezone.utc)

    # Update container status
    container = await db.get(Container, delivery.container_id)
    if container:
        container.status = "at_recycler"

    await db.flush()
    await db.refresh(delivery)
    return delivery


@router.post(
    "/{delivery_id}/proof",
    response_model=RecyclerDeliveryRead,
)
async def submit_proof_of_delivery(
    delivery_id: uuid.UUID,
    payload: ProofOfDeliverySubmit,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Driver submits proof of delivery. Requires at least one photo URL.
    Automatically triggers weight reconciliation.
    """
    allowed_roles = {"superadmin", "operations_manager", "driver"}
    if current_user.role not in allowed_roles:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    delivery = await db.get(RecyclerDelivery, delivery_id)
    if not delivery:
        raise HTTPException(status_code=404, detail="Recycler delivery not found")
    if delivery.status != "arrived":
        raise HTTPException(
            status_code=409,
            detail=f"Cannot submit proof from status '{delivery.status}'",
        )

    if not payload.proof_photos:
        raise HTTPException(
            status_code=422,
            detail="At least one photo URL is required for proof of delivery",
        )

    delivery.proof_photos = payload.proof_photos
    delivery.weight_ticket_ref = payload.weight_ticket_ref
    delivery.recycler_recorded_weight_kg = payload.recycler_recorded_weight_kg
    delivery.proof_submitted_at = datetime.now(timezone.utc)
    delivery.status = "proof_submitted"

    # Auto-reconcile: compare recycler weight vs declared weight
    if delivery.declared_total_weight_kg:
        variance_kg = abs(
            payload.recycler_recorded_weight_kg - delivery.declared_total_weight_kg
        )
        variance_pct = (variance_kg / delivery.declared_total_weight_kg) * 100
        delivery.weight_variance_kg = variance_kg
        delivery.weight_variance_pct = variance_pct

        if variance_pct > Decimal("5"):
            delivery.status = "reconciliation_discrepancy"
            delivery.reconciliation_status = "discrepancy_pending_review"
        else:
            delivery.reconciliation_status = "ok"

    await db.flush()
    await db.refresh(delivery)
    return delivery


@router.get(
    "/{delivery_id}/reconciliation",
    response_model=ReconciliationRead,
)
async def get_reconciliation(
    delivery_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return reconciliation details for a delivery."""
    delivery = await db.get(RecyclerDelivery, delivery_id)
    if not delivery:
        raise HTTPException(status_code=404, detail="Recycler delivery not found")

    return ReconciliationRead(
        delivery_id=delivery.id,
        declared_total_weight_kg=delivery.declared_total_weight_kg,
        recycler_recorded_weight_kg=delivery.recycler_recorded_weight_kg,
        variance_kg=delivery.weight_variance_kg,
        variance_pct=delivery.weight_variance_pct,
        reconciliation_status=delivery.reconciliation_status,
    )


@router.post(
    "/{delivery_id}/reconciliation-review",
    response_model=RecyclerDeliveryRead,
    dependencies=[Depends(require_roles("superadmin", "operations_manager"))],
)
async def review_reconciliation(
    delivery_id: uuid.UUID,
    payload: ReconciliationReview,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Operations manager accepts or rejects a weight discrepancy."""
    delivery = await db.get(RecyclerDelivery, delivery_id)
    if not delivery:
        raise HTTPException(status_code=404, detail="Recycler delivery not found")
    if delivery.status != "reconciliation_discrepancy":
        raise HTTPException(
            status_code=409,
            detail="Delivery is not in reconciliation_discrepancy status",
        )

    if payload.action == "accept":
        if not payload.justification:
            raise HTTPException(
                status_code=422,
                detail="justification is required when accepting a discrepancy",
            )
        delivery.reconciliation_status = "discrepancy_accepted"
        delivery.reconciliation_justification = payload.justification
        delivery.status = "proof_submitted"
    elif payload.action == "reject":
        delivery.reconciliation_status = "discrepancy_rejected"
        delivery.status = "arrived"  # Reset to allow re-submission
    else:
        raise HTTPException(status_code=422, detail="action must be 'accept' or 'reject'")

    await db.flush()
    await db.refresh(delivery)
    return delivery


@router.post(
    "/{delivery_id}/buyer-confirmation",
    response_model=RecyclerDeliveryRead,
    dependencies=[Depends(require_roles("superadmin", "operations_manager"))],
)
async def submit_buyer_confirmation(
    delivery_id: uuid.UUID,
    payload: BuyerConfirmationSubmit,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Record buyer confirmation and close the delivery."""
    delivery = await db.get(RecyclerDelivery, delivery_id)
    if not delivery:
        raise HTTPException(status_code=404, detail="Recycler delivery not found")
    if delivery.status == "reconciliation_discrepancy":
        raise HTTPException(
            status_code=409,
            detail="Cannot confirm delivery with unresolved reconciliation discrepancy",
        )
    if delivery.status not in {"proof_submitted", "arrived"}:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot confirm delivery from status '{delivery.status}'",
        )

    delivery.buyer_rep_name = payload.buyer_rep_name
    delivery.buyer_confirmed_breakdown = payload.buyer_confirmed_breakdown
    delivery.buyer_reference_number = payload.buyer_reference_number
    delivery.buyer_confirmed_at = datetime.now(timezone.utc)
    delivery.status = "completed"

    # Update container: reset fill level and mark available
    container = await db.get(Container, delivery.container_id)
    if container:
        container.status = "available"
        container.fill_level = 0
        container.current_client_id = None
        container.current_site_address = None
        # Close any active pickup triggers
        from sqlalchemy import and_
        trigger_q = select(PickupTrigger).where(
            and_(
                PickupTrigger.container_id == delivery.container_id,
                PickupTrigger.is_active == True,
            )
        )
        result = await db.execute(trigger_q)
        for trigger in result.scalars().all():
            trigger.is_active = False
            trigger.closed_at = datetime.now(timezone.utc)

    # Update linked recyclable record if exists
    if delivery.recyclable_record_id:
        record = await db.get(RecyclableRecord, delivery.recyclable_record_id)
        if record:
            record.buyer_id = delivery.buyer_id

    await db.flush()
    await db.refresh(delivery)
    return delivery
