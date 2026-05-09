# =============================================================
# Hi-Tech Waste Management — Operational Field Celery Tasks
# Scheduled background jobs for:
#   1. Compactor service due date escalation
#   2. Foreign worker permit expiry alerts
#   3. Disruption log escalation (open > 4 hours)
# =============================================================

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from celery.exceptions import SoftTimeLimitExceeded

from tasks.celery_app import celery_app
from tasks.agent_tasks import AgentBaseTask

logger = logging.getLogger(__name__)


# =============================================================
# Task 1 — Compactor Service Due Date Check
# Runs daily at 07:30 MST (23:30 UTC previous day).
# Escalates overdue machines to 'maintenance' status and
# generates alerts for machines due within 14 days.
# =============================================================


@celery_app.task(
    bind=True,
    base=AgentBaseTask,
    name="tasks.operational_field_tasks.check_compactor_service",
    queue="default",
)
def check_compactor_service(
    self: AgentBaseTask, context: dict | None = None
) -> dict[str, Any]:
    """
    Daily compactor maintenance check.

    - Machines whose next_service_date has passed → status = 'maintenance',
      severity = 'critical' alert
    - Machines within 14 days of service → severity = 'warning' alert
    """
    logger.info("Compactor service check starting")
    start_time = datetime.now(tz=timezone.utc)
    results: dict[str, Any] = {
        "task": "check_compactor_service",
        "started_at": start_time.isoformat(),
        "overdue_count": 0,
        "warning_count": 0,
        "events_created": [],
    }

    try:
        from sqlalchemy import text

        with self._get_db_session() as session:
            # Fetch machines that are overdue or due within 14 days
            rows = (
                session.execute(
                    text(
                        """
                        SELECT
                            id::text            AS machine_id,
                            asset_tag,
                            model_name,
                            status,
                            next_service_date,
                            (next_service_date - CURRENT_DATE) AS days_until_service
                        FROM compaction_machines
                        WHERE status NOT IN ('decommissioned')
                          AND (
                              next_service_date IS NULL
                              OR next_service_date <= CURRENT_DATE + INTERVAL '14 days'
                          )
                        ORDER BY next_service_date ASC NULLS FIRST
                        """
                    )
                )
                .mappings()
                .all()
            )

            for row in rows:
                days = row.get("days_until_service")
                is_overdue = days is not None and int(days) <= 0
                no_date = days is None

                if is_overdue:
                    # Escalate to maintenance status
                    session.execute(
                        text(
                            """
                            UPDATE compaction_machines
                            SET status = 'maintenance', updated_at = NOW()
                            WHERE id = :machine_id::uuid
                              AND status = 'deployed'
                            """
                        ),
                        {"machine_id": row["machine_id"]},
                    )
                    session.commit()

                    severity = "critical"
                    title = (
                        f"OVERDUE Service: {row['asset_tag']} ({row['model_name']})"
                    )
                    body = (
                        f"Compaction machine {row['asset_tag']} ({row['model_name']}) "
                        f"is {abs(int(days or 0))} day(s) overdue for scheduled maintenance "
                        f"(due {row['next_service_date']}). "
                        "Machine status has been set to 'maintenance'. "
                        "Please arrange servicing before redeployment."
                    )
                    results["overdue_count"] += 1

                elif no_date:
                    severity = "warning"
                    title = f"No Service Date: {row['asset_tag']} ({row['model_name']})"
                    body = (
                        f"Compaction machine {row['asset_tag']} ({row['model_name']}) "
                        "has no next service date recorded. "
                        "Please log a maintenance service to set the next service date."
                    )
                    results["warning_count"] += 1

                else:
                    severity = "warning"
                    title = (
                        f"Service Due in {int(days)} day(s): "
                        f"{row['asset_tag']} ({row['model_name']})"
                    )
                    body = (
                        f"Compaction machine {row['asset_tag']} ({row['model_name']}) "
                        f"is due for scheduled maintenance in {int(days)} day(s) "
                        f"(due {row['next_service_date']}). "
                        "Please arrange servicing to avoid unplanned downtime at client sites."
                    )
                    results["warning_count"] += 1

                event_id = self._persist_event(
                    agent_name="operations",
                    event_type="alert",
                    severity=severity,
                    title=title,
                    body=body,
                    reference_type="compaction_machine",
                    reference_id=row["machine_id"],
                )
                if event_id:
                    results["events_created"].append(event_id)

                if is_overdue:
                    self._broadcast_alert(
                        {
                            "event": "alert",
                            "agent": "operations",
                            "severity": "critical",
                            "title": title,
                            "body": body,
                            "reference_type": "compaction_machine",
                            "reference_id": row["machine_id"],
                        }
                    )

        logger.info(
            "Compactor service check completed | overdue=%d | warning=%d",
            results["overdue_count"],
            results["warning_count"],
        )

    except SoftTimeLimitExceeded:
        logger.warning("Compactor service check soft time limit exceeded")
    except Exception as exc:
        logger.error("Compactor service check error: %s", exc, exc_info=True)
        raise self.retry(exc=exc)

    results["completed_at"] = datetime.now(tz=timezone.utc).isoformat()
    return results


# =============================================================
# Task 2 — Foreign Worker Permit Expiry Check
# Runs daily at 08:00 MST (00:00 UTC).
# Alerts 30 days before work permit expiry.
# =============================================================


@celery_app.task(
    bind=True,
    base=AgentBaseTask,
    name="tasks.operational_field_tasks.check_work_permit_expiry",
    queue="default",
)
def check_work_permit_expiry(
    self: AgentBaseTask, context: dict | None = None
) -> dict[str, Any]:
    """
    Daily work permit expiry check for foreign workers.

    Generates alerts for permits expiring within 30 days.
    """
    logger.info("Work permit expiry check starting")
    start_time = datetime.now(tz=timezone.utc)
    results: dict[str, Any] = {
        "task": "check_work_permit_expiry",
        "started_at": start_time.isoformat(),
        "expiring_count": 0,
        "expired_count": 0,
        "events_created": [],
    }

    try:
        from sqlalchemy import text

        with self._get_db_session() as session:
            rows = (
                session.execute(
                    text(
                        """
                        SELECT
                            sp.id::text             AS profile_id,
                            sp.work_permit_expiry,
                            sp.labour_agent_name,
                            u.full_name,
                            u.email,
                            (sp.work_permit_expiry - CURRENT_DATE) AS days_remaining
                        FROM staff_profiles sp
                        JOIN users u ON u.id = sp.user_id
                        WHERE sp.employment_type = 'foreign_worker'
                          AND sp.assignment_status != 'inactive'
                          AND sp.work_permit_expiry IS NOT NULL
                          AND sp.work_permit_expiry <= CURRENT_DATE + INTERVAL '30 days'
                        ORDER BY sp.work_permit_expiry ASC
                        """
                    )
                )
                .mappings()
                .all()
            )

            for row in rows:
                days = int(row["days_remaining"]) if row["days_remaining"] is not None else 0
                is_expired = days <= 0

                if is_expired:
                    severity = "critical"
                    title = f"EXPIRED Work Permit: {row['full_name']}"
                    body = (
                        f"Work permit for {row['full_name']} "
                        f"(agent: {row['labour_agent_name'] or 'N/A'}) "
                        f"expired on {row['work_permit_expiry']}. "
                        "This worker must not be deployed until the permit is renewed. "
                        "Please contact the labour agent immediately."
                    )
                    results["expired_count"] += 1
                else:
                    severity = "warning" if days > 7 else "critical"
                    title = (
                        f"Work Permit Expiring in {days} day(s): {row['full_name']}"
                    )
                    body = (
                        f"Work permit for {row['full_name']} "
                        f"(agent: {row['labour_agent_name'] or 'N/A'}) "
                        f"expires on {row['work_permit_expiry']} ({days} day(s) remaining). "
                        "Please initiate renewal with the labour agent to avoid disruption."
                    )
                    results["expiring_count"] += 1

                event_id = self._persist_event(
                    agent_name="operations",
                    event_type="alert",
                    severity=severity,
                    title=title,
                    body=body,
                    reference_type="staff_profile",
                    reference_id=row["profile_id"],
                )
                if event_id:
                    results["events_created"].append(event_id)

                if severity == "critical":
                    self._broadcast_alert(
                        {
                            "event": "alert",
                            "agent": "operations",
                            "severity": "critical",
                            "title": title,
                            "body": body,
                            "reference_type": "staff_profile",
                            "reference_id": row["profile_id"],
                        }
                    )

        logger.info(
            "Work permit check completed | expiring=%d | expired=%d",
            results["expiring_count"],
            results["expired_count"],
        )

    except SoftTimeLimitExceeded:
        logger.warning("Work permit check soft time limit exceeded")
    except Exception as exc:
        logger.error("Work permit check error: %s", exc, exc_info=True)
        raise self.retry(exc=exc)

    results["completed_at"] = datetime.now(tz=timezone.utc).isoformat()
    return results


# =============================================================
# Task 3 — Disruption Log Escalation
# Runs every 30 minutes.
# Escalates disruptions open > 4 hours to 'critical' severity
# and notifies management.
# =============================================================


@celery_app.task(
    bind=True,
    base=AgentBaseTask,
    name="tasks.operational_field_tasks.escalate_stale_disruptions",
    queue="default",
)
def escalate_stale_disruptions(
    self: AgentBaseTask, context: dict | None = None
) -> dict[str, Any]:
    """
    Every 30 minutes: escalate disruptions open > 4 hours to critical.
    """
    logger.info("Disruption escalation check starting")
    start_time = datetime.now(tz=timezone.utc)
    results: dict[str, Any] = {
        "task": "escalate_stale_disruptions",
        "started_at": start_time.isoformat(),
        "escalated_count": 0,
        "events_created": [],
    }

    try:
        from sqlalchemy import text

        with self._get_db_session() as session:
            # Find open disruptions older than 4 hours that are not yet critical
            rows = (
                session.execute(
                    text(
                        """
                        SELECT
                            id::text            AS disruption_id,
                            disruption_type,
                            description,
                            occurred_at,
                            severity,
                            EXTRACT(EPOCH FROM (NOW() - occurred_at)) / 3600 AS hours_open,
                            array_length(affected_job_ids, 1) AS affected_jobs_count
                        FROM disruption_logs
                        WHERE status = 'open'
                          AND occurred_at <= NOW() - INTERVAL '4 hours'
                          AND severity != 'critical'
                        ORDER BY occurred_at ASC
                        """
                    )
                )
                .mappings()
                .all()
            )

            for row in rows:
                hours = round(float(row["hours_open"] or 0), 1)

                # Escalate severity to critical
                session.execute(
                    text(
                        """
                        UPDATE disruption_logs
                        SET severity = 'critical', updated_at = NOW()
                        WHERE id = :disruption_id::uuid
                        """
                    ),
                    {"disruption_id": row["disruption_id"]},
                )
                session.commit()
                results["escalated_count"] += 1

                title = (
                    f"ESCALATED: {row['disruption_type'].replace('_', ' ').title()} "
                    f"unresolved for {hours}h"
                )
                body = (
                    f"Disruption ({row['disruption_type'].replace('_', ' ')}) "
                    f"logged {hours} hours ago has not been resolved. "
                    f"Affected jobs: {row['affected_jobs_count'] or 0}. "
                    f"Description: {row['description'][:200]}. "
                    "Immediate management attention required."
                )

                event_id = self._persist_event(
                    agent_name="operations",
                    event_type="alert",
                    severity="critical",
                    title=title,
                    body=body,
                    reference_type="disruption_log",
                    reference_id=row["disruption_id"],
                )
                if event_id:
                    results["events_created"].append(event_id)

                self._broadcast_alert(
                    {
                        "event": "alert",
                        "agent": "operations",
                        "severity": "critical",
                        "title": title,
                        "body": body,
                        "reference_type": "disruption_log",
                        "reference_id": row["disruption_id"],
                    }
                )

        logger.info(
            "Disruption escalation completed | escalated=%d",
            results["escalated_count"],
        )

    except SoftTimeLimitExceeded:
        logger.warning("Disruption escalation soft time limit exceeded")
    except Exception as exc:
        logger.error("Disruption escalation error: %s", exc, exc_info=True)
        raise self.retry(exc=exc)

    results["completed_at"] = datetime.now(tz=timezone.utc).isoformat()
    return results


# =============================================================
# Task 4 — Scheduled Waste 90-Day Storage Deadline Alerts
# Runs daily at 08:00 MST (00:00 UTC).
# Alerts at 75, 85, and 89 days — WhatsApp + email + in-app.
# =============================================================


@celery_app.task(
    bind=True,
    base=AgentBaseTask,
    name="tasks.operational_field_tasks.check_sw_storage_deadlines",
    queue="default",
)
def check_sw_storage_deadlines(
    self: AgentBaseTask, context: dict | None = None
) -> dict[str, Any]:
    """
    Daily check for scheduled waste batches approaching the 90-day
    DOE storage limit (EQA Act 127 / Scheduled Wastes Regulations 2005).

    Alert thresholds: 15 days remaining (75d), 5 days (85d), 1 day (89d).
    Sends WhatsApp + email to client PIC and creates in-app alert.
    """
    logger.info("SW storage deadline check starting")
    start_time = datetime.now(tz=timezone.utc)
    results: dict[str, Any] = {
        "task": "check_sw_storage_deadlines",
        "started_at": start_time.isoformat(),
        "alerts_sent": 0,
        "events_created": [],
    }

    ALERT_THRESHOLDS = {15, 5, 1}  # days remaining

    try:
        from sqlalchemy import text
        import asyncio

        with self._get_db_session() as session:
            rows = (
                session.execute(
                    text(
                        """
                        SELECT
                            sb.id::text             AS batch_id,
                            sb.sw_code,
                            sb.quantity_kg,
                            sb.storage_start_date,
                            sb.storage_deadline,
                            (sb.storage_deadline - CURRENT_DATE) AS days_remaining,
                            c.company_name          AS client_name,
                            c.pic_name,
                            c.pic_email,
                            c.pic_phone
                        FROM sw_batches sb
                        JOIN clients c ON c.id = sb.client_id
                        WHERE sb.status NOT IN ('disposed', 'cancelled')
                          AND sb.storage_deadline IS NOT NULL
                          AND (sb.storage_deadline - CURRENT_DATE) IN (15, 5, 1)
                        ORDER BY sb.storage_deadline ASC
                        """
                    )
                )
                .mappings()
                .all()
            )

            for row in rows:
                days = int(row["days_remaining"])
                is_critical = days <= 5

                severity = "critical" if is_critical else "warning"
                title = (
                    f"{'URGENT: ' if is_critical else ''}"
                    f"SW {row['sw_code']} — {days} day(s) until disposal deadline"
                )
                body = (
                    f"Client: {row['client_name']}\n"
                    f"SW Code: {row['sw_code']}\n"
                    f"Quantity: {float(row['quantity_kg']):.1f} kg\n"
                    f"Storage deadline: {row['storage_deadline']}\n"
                    f"Days remaining: {days}\n"
                    "Please arrange immediate disposal and generate a consignment note."
                )

                # In-app alert
                event_id = self._persist_event(
                    agent_name="compliance",
                    event_type="alert",
                    severity=severity,
                    title=title,
                    body=body,
                    reference_type="sw_batch",
                    reference_id=row["batch_id"],
                )
                if event_id:
                    results["events_created"].append(event_id)

                if is_critical:
                    self._broadcast_alert(
                        {
                            "event": "alert",
                            "agent": "compliance",
                            "severity": "critical",
                            "title": title,
                            "body": body,
                            "reference_type": "sw_batch",
                            "reference_id": row["batch_id"],
                        }
                    )

                # WhatsApp + email notifications
                from services.notification_service import (
                    send_whatsapp_sw_deadline_alert,
                    send_compliance_deadline_alert,
                )

                if row["pic_phone"]:
                    try:
                        loop = asyncio.new_event_loop()
                        loop.run_until_complete(
                            send_whatsapp_sw_deadline_alert(
                                phone_number=row["pic_phone"],
                                pic_name=row["pic_name"] or row["client_name"],
                                client_name=row["client_name"],
                                sw_code=row["sw_code"],
                                days_remaining=days,
                                storage_deadline=str(row["storage_deadline"]),
                                quantity_kg=float(row["quantity_kg"]),
                            )
                        )
                        loop.close()
                    except Exception as wa_exc:
                        logger.warning("WhatsApp SW alert failed: %s", wa_exc)

                if row["pic_email"]:
                    send_compliance_deadline_alert(
                        pic_email=row["pic_email"],
                        pic_name=row["pic_name"] or row["client_name"],
                        client_name=row["client_name"],
                        sw_code=row["sw_code"],
                        days_remaining=days,
                        storage_deadline=str(row["storage_deadline"]),
                        quantity_kg=float(row["quantity_kg"]),
                    )

                results["alerts_sent"] += 1
                logger.info(
                    "SW deadline alert sent | client=%s | sw_code=%s | days=%d",
                    row["client_name"],
                    row["sw_code"],
                    days,
                )

        logger.info(
            "SW storage deadline check completed | alerts_sent=%d",
            results["alerts_sent"],
        )

    except SoftTimeLimitExceeded:
        logger.warning("SW storage deadline check soft time limit exceeded")
    except Exception as exc:
        logger.error("SW storage deadline check error: %s", exc, exc_info=True)
        raise self.retry(exc=exc)

    results["completed_at"] = datetime.now(tz=timezone.utc).isoformat()
    return results


# =============================================================
# Task 5 — Client Contract Expiry Alerts
# Runs daily at 08:00 MST (00:00 UTC).
# Alerts management at 90, 60, and 30 days before expiry.
# =============================================================


@celery_app.task(
    bind=True,
    base=AgentBaseTask,
    name="tasks.operational_field_tasks.check_contract_expiry",
    queue="default",
)
def check_contract_expiry(
    self: AgentBaseTask, context: dict | None = None
) -> dict[str, Any]:
    """
    Daily check for client contracts expiring within 90 days.
    Alerts management at 90, 60, and 30 days before expiry.
    Sends WhatsApp to management and creates in-app alert.
    """
    logger.info("Contract expiry check starting")
    start_time = datetime.now(tz=timezone.utc)
    results: dict[str, Any] = {
        "task": "check_contract_expiry",
        "started_at": start_time.isoformat(),
        "alerts_sent": 0,
        "events_created": [],
    }

    ALERT_THRESHOLDS = {90, 60, 30}

    try:
        from sqlalchemy import text
        import asyncio

        with self._get_db_session() as session:
            rows = (
                session.execute(
                    text(
                        """
                        SELECT
                            c.id::text           AS client_id,
                            c.company_name,
                            c.contract_end,
                            (c.contract_end - CURRENT_DATE) AS days_remaining
                        FROM clients c
                        WHERE c.is_active = TRUE
                          AND c.contract_end IS NOT NULL
                          AND (c.contract_end - CURRENT_DATE) IN (90, 60, 30)
                        ORDER BY c.contract_end ASC
                        """
                    )
                )
                .mappings()
                .all()
            )

            # Get management phone numbers for WhatsApp alerts
            mgmt_rows = (
                session.execute(
                    text(
                        """
                        SELECT u.email
                        FROM users u
                        WHERE u.role IN ('superadmin', 'management')
                          AND u.is_active = TRUE
                        LIMIT 5
                        """
                    )
                )
                .mappings()
                .all()
            )

            for row in rows:
                days = int(row["days_remaining"])
                severity = "critical" if days <= 30 else "warning"

                title = (
                    f"Contract Expiry: {row['company_name']} — {days} days remaining"
                )
                body = (
                    f"Client contract for {row['company_name']} expires on "
                    f"{row['contract_end']} ({days} days remaining). "
                    "Please initiate renewal discussions to avoid service disruption."
                )

                event_id = self._persist_event(
                    agent_name="client_intelligence",
                    event_type="alert",
                    severity=severity,
                    title=title,
                    body=body,
                    reference_type="client",
                    reference_id=row["client_id"],
                )
                if event_id:
                    results["events_created"].append(event_id)

                if severity == "critical":
                    self._broadcast_alert(
                        {
                            "event": "alert",
                            "agent": "client_intelligence",
                            "severity": "critical",
                            "title": title,
                            "body": body,
                            "reference_type": "client",
                            "reference_id": row["client_id"],
                        }
                    )

                results["alerts_sent"] += 1
                logger.info(
                    "Contract expiry alert | client=%s | days=%d",
                    row["company_name"],
                    days,
                )

        logger.info(
            "Contract expiry check completed | alerts_sent=%d",
            results["alerts_sent"],
        )

    except SoftTimeLimitExceeded:
        logger.warning("Contract expiry check soft time limit exceeded")
    except Exception as exc:
        logger.error("Contract expiry check error: %s", exc, exc_info=True)
        raise self.retry(exc=exc)

    results["completed_at"] = datetime.now(tz=timezone.utc).isoformat()
    return results
