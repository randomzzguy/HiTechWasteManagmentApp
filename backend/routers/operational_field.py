# =============================================================
# Hi-Tech Waste Management — Operational Field Summary Router
# Unified summary endpoint for the operations dashboard.
# Also exposes GET /jobs/{id}/disruptions.
# =============================================================

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from database import get_db
from fastapi import APIRouter, Depends, HTTPException
from models.disruption import DisruptionLog, DisruptionLogRead
from models.equipment import CompactionMachine, Container, PickupTrigger
from models.labour import StaffProfile
from models.recycler_delivery import RecyclerDelivery
from models.user import User
from routers.auth import get_current_user
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.get("/summary")
async def get_operational_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Aggregated operational field summary for the dashboard.
    Returns counts by status and active alerts.
    """
    now = datetime.now(timezone.utc)

    # ── Compaction machine counts by status ───────────────────
    compactor_q = select(
        CompactionMachine.status, func.count(CompactionMachine.id)
    ).group_by(CompactionMachine.status)
    result = await db.execute(compactor_q)
    compactor_counts = {row[0]: row[1] for row in result.all()}

    # ── Container counts by status ────────────────────────────
    container_q = select(
        Container.status, func.count(Container.id)
    ).group_by(Container.status)
    result = await db.execute(container_q)
    container_counts = {row[0]: row[1] for row in result.all()}

    # ── Staff counts by assignment status ─────────────────────
    staff_q = select(
        StaffProfile.assignment_status, func.count(StaffProfile.id)
    ).group_by(StaffProfile.assignment_status)
    result = await db.execute(staff_q)
    staff_counts = {row[0]: row[1] for row in result.all()}

    # ── Open disruption counts by severity ────────────────────
    disruption_q = select(
        DisruptionLog.severity, func.count(DisruptionLog.id)
    ).where(DisruptionLog.status == "open").group_by(DisruptionLog.severity)
    result = await db.execute(disruption_q)
    disruption_counts = {row[0]: row[1] for row in result.all()}

    # ── Delivery counts by status ─────────────────────────────
    delivery_q = select(
        RecyclerDelivery.status, func.count(RecyclerDelivery.id)
    ).group_by(RecyclerDelivery.status)
    result = await db.execute(delivery_q)
    delivery_counts = {row[0]: row[1] for row in result.all()}

    # ── Active alerts ─────────────────────────────────────────
    alerts = []

    # Alert: compaction machine service overdue
    overdue_q = select(func.count(CompactionMachine.id)).where(
        and_(
            CompactionMachine.next_service_date <= now.date(),
            CompactionMachine.status != "decommissioned",
        )
    )
    result = await db.execute(overdue_q)
    overdue_count = result.scalar() or 0
    if overdue_count > 0:
        alerts.append({
            "type": "compactor_service_overdue",
            "severity": "critical",
            "message": f"{overdue_count} compaction machine(s) have overdue service",
        })

    # Alert: unacknowledged pickup triggers older than 2 hours
    two_hours_ago = now - timedelta(hours=2)
    stale_trigger_q = select(func.count(PickupTrigger.id)).where(
        and_(
            PickupTrigger.is_active == True,
            PickupTrigger.acknowledged_at.is_(None),
            PickupTrigger.triggered_at <= two_hours_ago,
        )
    )
    result = await db.execute(stale_trigger_q)
    stale_triggers = result.scalar() or 0
    if stale_triggers > 0:
        alerts.append({
            "type": "stale_pickup_trigger",
            "severity": "warning",
            "message": f"{stale_triggers} container pickup trigger(s) unacknowledged for >2 hours",
        })

    # Alert: disruptions open for more than 4 hours
    four_hours_ago = now - timedelta(hours=4)
    stale_disruption_q = select(func.count(DisruptionLog.id)).where(
        and_(
            DisruptionLog.status == "open",
            DisruptionLog.occurred_at <= four_hours_ago,
        )
    )
    result = await db.execute(stale_disruption_q)
    stale_disruptions = result.scalar() or 0
    if stale_disruptions > 0:
        alerts.append({
            "type": "stale_disruption",
            "severity": "critical",
            "message": f"{stale_disruptions} disruption(s) unresolved for >4 hours",
        })

    # Alert: deliveries with reconciliation discrepancy
    discrepancy_q = select(func.count(RecyclerDelivery.id)).where(
        RecyclerDelivery.status == "reconciliation_discrepancy"
    )
    result = await db.execute(discrepancy_q)
    discrepancies = result.scalar() or 0
    if discrepancies > 0:
        alerts.append({
            "type": "delivery_reconciliation_discrepancy",
            "severity": "warning",
            "message": f"{discrepancies} recycler delivery/deliveries have weight discrepancies",
        })

    return {
        "generated_at": now.isoformat(),
        "compaction_machines": compactor_counts,
        "containers": container_counts,
        "staff": staff_counts,
        "disruptions_open": disruption_counts,
        "recycler_deliveries": delivery_counts,
        "alerts": alerts,
        "alert_count": len(alerts),
    }


@router.get("/jobs/{job_id}/disruptions", response_model=List[DisruptionLogRead])
async def get_job_disruptions(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all disruption logs linked to a specific job."""
    from sqlalchemy import cast
    from sqlalchemy.dialects.postgresql import ARRAY, TEXT

    # affected_job_ids is stored as ARRAY(String) — filter by job_id string
    job_id_str = str(job_id)
    q = select(DisruptionLog).where(
        DisruptionLog.affected_job_ids.contains([job_id_str])
    ).order_by(DisruptionLog.occurred_at.desc())
    result = await db.execute(q)
    return result.scalars().all()
