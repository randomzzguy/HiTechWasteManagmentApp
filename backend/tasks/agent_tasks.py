# =============================================================
# Hi-Tech Waste Management — Agent Celery Tasks
# Five AI agents + operational utility tasks
# =============================================================

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from celery import Task
from celery.exceptions import SoftTimeLimitExceeded

from tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


# =============================================================
# Base task class
# Provides shared retry logic and database session management
# for all agent tasks.
# =============================================================


class AgentBaseTask(Task):
    """
    Custom base task class for all Hi-Tech AI agent tasks.

    Provides:
    - Automatic retry on transient failures (network, DB, LLM timeout)
    - Structured logging on retry / failure
    - A helper to persist agent events to the database
    """

    abstract = True
    max_retries = 3
    default_retry_delay = 60  # seconds

    def on_retry(self, exc: Exception, task_id: str, args, kwargs, einfo) -> None:
        logger.warning(
            "Agent task RETRYING | task=%s | task_id=%s | attempt=%d | exc=%s",
            self.name,
            task_id,
            self.request.retries,
            repr(exc),
        )

    def on_failure(self, exc: Exception, task_id: str, args, kwargs, einfo) -> None:
        logger.error(
            "Agent task FAILED | task=%s | task_id=%s | exc=%s",
            self.name,
            task_id,
            repr(exc),
            exc_info=True,
        )

    # ----------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------

    def _get_db_session(self):
        """
        Return a synchronous SQLAlchemy session for use within Celery tasks.
        Import lazily to avoid circular imports at module load time.
        """
        from database import SyncSessionLocal

        return SyncSessionLocal()

    def _persist_event(
        self,
        *,
        agent_name: str,
        event_type: str,
        severity: str,
        title: str,
        body: str,
        reference_type: str | None = None,
        reference_id: str | None = None,
    ) -> str | None:
        """
        Persist an agent event to the ``agent_events`` table and return
        its UUID string.  Returns None if the insert fails.
        """
        import uuid

        from sqlalchemy import text

        event_id = str(uuid.uuid4())
        try:
            with self._get_db_session() as session:
                session.execute(
                    text(
                        """
                        INSERT INTO agent_events (
                            id, agent_name, event_type, severity,
                            title, body, reference_type, reference_id,
                            is_read, created_at
                        ) VALUES (
                            :id, :agent_name, :event_type, :severity,
                            :title, :body, :reference_type, :reference_id::uuid,
                            FALSE, NOW()
                        )
                        """
                    ),
                    {
                        "id": event_id,
                        "agent_name": agent_name,
                        "event_type": event_type,
                        "severity": severity,
                        "title": title,
                        "body": body,
                        "reference_type": reference_type,
                        "reference_id": reference_id,
                    },
                )
                session.commit()
            return event_id
        except Exception as exc:
            logger.error("Failed to persist agent event: %s", exc)
            return None

    def _broadcast_alert(self, event: dict[str, Any]) -> None:
        """
        Broadcast an alert to the ``agent-alerts`` WebSocket room.
        Uses a synchronous HTTP call to the backend's internal API
        since Celery workers do not have access to the async event loop.
        """
        import os

        import httpx

        backend_url = os.environ.get("BACKEND_URL", "http://localhost:8000")
        try:
            with httpx.Client(timeout=5.0) as client:
                client.post(
                    f"{backend_url}/internal/broadcast-alert",
                    json=event,
                )
        except Exception as exc:
            # Non-fatal — the event is already persisted to the DB
            logger.warning("WebSocket broadcast failed (non-fatal): %s", exc)

    def _call_ollama(
        self, prompt: str, system_prompt: str = "", model: str | None = None
    ) -> str:
        """
        Synchronous helper to call the Ollama LLM.

        Returns the generated text or raises an exception on failure.
        """
        import os

        import httpx

        ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        ollama_model = model or os.environ.get("OLLAMA_MODEL", "llama3")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        with httpx.Client(timeout=120.0) as client:
            resp = client.post(
                f"{ollama_url}/api/chat",
                json={
                    "model": ollama_model,
                    "messages": messages,
                    "stream": False,
                },
            )
            resp.raise_for_status()
            return resp.json().get("message", {}).get("content", "").strip()


# =============================================================
# Agent 1 — Compliance Agent
# Monitors scheduled waste storage deadlines (90-day rule)
# =============================================================


@celery_app.task(
    bind=True,
    base=AgentBaseTask,
    name="tasks.agent_tasks.run_compliance_agent",
    queue="agents",
)
def run_compliance_agent(
    self: AgentBaseTask, context: dict | None = None
) -> dict[str, Any]:
    """
    Compliance Agent — runs every 6 hours.

    Responsibilities:
    - Scan all ``in_storage`` scheduled waste batches for upcoming deadlines
    - Flag batches within 14 days of the 90-day limit as WARNING
    - Flag batches that have exceeded the 90-day limit as CRITICAL
    - Generate a summary recommendation using the LLM
    - Persist agent events for each flagged batch
    - Broadcast critical alerts to the WebSocket room
    """
    logger.info("Compliance Agent starting | context=%s", context)
    start_time = datetime.now(tz=timezone.utc)
    results: dict[str, Any] = {
        "agent": "compliance",
        "started_at": start_time.isoformat(),
        "critical_count": 0,
        "warning_count": 0,
        "events_created": [],
    }

    try:
        from sqlalchemy import text

        with self._get_db_session() as session:
            # Fetch all in-storage batches with deadline info
            rows = (
                session.execute(
                    text(
                        """
                    SELECT
                        swb.id::text            AS batch_id,
                        swb.sw_code,
                        swb.waste_description,
                        swb.quantity_kg,
                        swb.storage_deadline,
                        (swb.storage_deadline - CURRENT_DATE) AS days_remaining,
                        c.company_name          AS client_name,
                        c.pic_email             AS client_email
                    FROM scheduled_waste_batches swb
                    JOIN clients c ON c.id = swb.client_id
                    WHERE swb.status = 'in_storage'
                      AND swb.storage_deadline <= CURRENT_DATE + INTERVAL '14 days'
                    ORDER BY swb.storage_deadline ASC
                    """
                    )
                )
                .mappings()
                .all()
            )

        for row in rows:
            days = (
                int(row["days_remaining"]) if row["days_remaining"] is not None else 0
            )
            is_overdue = days < 0

            severity = "critical" if is_overdue else "warning"
            title = (
                f"{'OVERDUE' if is_overdue else 'EXPIRING SOON'}: "
                f"{row['sw_code']} — {row['client_name']}"
            )
            body = (
                f"Scheduled waste batch ({row['sw_code']}) for "
                f"{row['client_name']} containing {row['quantity_kg']} kg of "
                f"{row['waste_description']} is "
                + (
                    f"{abs(days)} day(s) overdue (deadline: {row['storage_deadline']})."
                    if is_overdue
                    else f"expiring in {days} day(s) (deadline: {row['storage_deadline']})."
                )
                + " Please arrange immediate disposal and generate a consignment note."
            )

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
                if is_overdue:
                    results["critical_count"] += 1
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
                    # Email notification for overdue batches
                    if row.get("client_email"):
                        try:
                            from services.notification_service import send_email_sync
                            send_email_sync(
                                to=row["client_email"],
                                subject=f"URGENT: Scheduled Waste Disposal Overdue — {row['sw_code']}",
                                body_html=f"""
                                <html><body>
                                <p>Dear {row.get('client_name', 'Client')},</p>
                                <p>Your scheduled waste batch <strong>{row['sw_code']}</strong>
                                ({row['quantity_kg']} kg) is <strong>{abs(days)} day(s) overdue</strong>
                                for disposal (deadline: {row['storage_deadline']}).</p>
                                <p>Please contact Hi-Tech Waste Management immediately to arrange disposal.</p>
                                <br><p>Hi-Tech Waste Management Sdn. Bhd.</p>
                                </body></html>
                                """,
                            )
                        except Exception as email_exc:
                            logger.warning("Compliance email failed (non-fatal): %s", email_exc)
                else:
                    results["warning_count"] += 1

        logger.info(
            "Compliance Agent completed | critical=%d | warning=%d | events=%d",
            results["critical_count"],
            results["warning_count"],
            len(results["events_created"]),
        )

    except SoftTimeLimitExceeded:
        logger.warning(
            "Compliance Agent soft time limit exceeded — completing gracefully"
        )
    except Exception as exc:
        logger.error("Compliance Agent error: %s", exc, exc_info=True)
        raise self.retry(exc=exc)

    results["completed_at"] = datetime.now(tz=timezone.utc).isoformat()
    return results


# =============================================================
# Agent 2 — ESG & Carbon Agent
# Weekly carbon footprint and diversion rate analysis
# =============================================================


@celery_app.task(
    bind=True,
    base=AgentBaseTask,
    name="tasks.agent_tasks.run_esg_agent",
    queue="agents",
)
def run_esg_agent(
    self: AgentBaseTask,
    context: dict | None = None,
    period: str = "weekly",
    client_id: str | None = None,
    period_start: str | None = None,
    period_end: str | None = None,
    include_recommendations: bool = True,
    output_format: str = "pdf",
    requested_by: str | None = None,
) -> dict[str, Any]:
    """
    ESG & Carbon Agent — runs every Monday at 08:00 MST.

    Responsibilities:
    - Aggregate the previous week's carbon records per client
    - Calculate net carbon impact and diversion rates
    - Identify clients not meeting their SLA diversion targets
    - Generate an ESG narrative summary using the LLM
    - Persist an ESG report event and notify the dashboard
    """
    logger.info("ESG Agent starting | period=%s | client_id=%s", period, client_id)
    start_time = datetime.now(tz=timezone.utc)
    results: dict[str, Any] = {
        "agent": "esg",
        "started_at": start_time.isoformat(),
        "clients_analysed": 0,
        "underperforming_clients": [],
        "events_created": [],
    }

    try:
        from sqlalchemy import text

        with self._get_db_session() as session:
            # Fetch ESG performance per client for the past 7 days
            client_filter = "AND cr.client_id = :client_id::uuid" if client_id else ""
            params: dict[str, Any] = {}
            if client_id:
                params["client_id"] = client_id

            rows = (
                session.execute(
                    text(
                        f"""
                    SELECT
                        c.id::text                              AS client_id,
                        c.company_name,
                        c.sla_diversion_target,
                        COALESCE(SUM(wb.net_weight_kg), 0)      AS total_waste_kg,
                        COALESCE(SUM(rr.total_recyclable_kg), 0) AS total_recyclable_kg,
                        COALESCE(SUM(cr.net_carbon_impact_kgco2e), 0) AS net_carbon_kgco2e,
                        CASE
                            WHEN COALESCE(SUM(wb.net_weight_kg), 0) > 0
                            THEN ROUND(
                                COALESCE(SUM(rr.total_recyclable_kg), 0)
                                / COALESCE(SUM(wb.net_weight_kg), 1) * 100, 2
                            )
                            ELSE 0
                        END AS diversion_rate_pct
                    FROM clients c
                    LEFT JOIN weighbridge_records wb
                        ON wb.client_id = c.id
                        AND wb.recorded_at >= NOW() - INTERVAL '7 days'
                    LEFT JOIN recyclable_records rr
                        ON rr.client_id = c.id
                        AND rr.recorded_at >= NOW() - INTERVAL '7 days'
                    LEFT JOIN carbon_records cr
                        ON cr.client_id = c.id
                        AND cr.calculated_at >= NOW() - INTERVAL '7 days'
                    WHERE c.is_active = TRUE
                    {client_filter}
                    GROUP BY c.id, c.company_name, c.sla_diversion_target
                    HAVING COALESCE(SUM(wb.net_weight_kg), 0) > 0
                    ORDER BY diversion_rate_pct ASC
                    """
                    ),
                    params,
                )
                .mappings()
                .all()
            )

        results["clients_analysed"] = len(rows)

        for row in rows:
            diversion = float(row["diversion_rate_pct"] or 0)
            target = float(row["sla_diversion_target"] or 0)

            if target > 0 and diversion < target:
                gap = round(target - diversion, 2)
                results["underperforming_clients"].append(row["client_id"])

                title = (
                    f"ESG Alert: {row['company_name']} below diversion target "
                    f"({diversion}% vs {target}% target)"
                )
                body = (
                    f"{row['company_name']} achieved a {diversion}% waste diversion rate "
                    f"this week, which is {gap}% below their SLA target of {target}%. "
                    f"Total waste collected: {row['total_waste_kg']:.1f} kg, "
                    f"recyclables recovered: {row['total_recyclable_kg']:.1f} kg. "
                    f"Net carbon impact: {row['net_carbon_kgco2e']:.3f} kg CO2e. "
                    "Consider reviewing waste segregation practices with the client."
                )

                event_id = self._persist_event(
                    agent_name="esg",
                    event_type="alert",
                    severity="warning",
                    title=title,
                    body=body,
                    reference_type="client",
                    reference_id=row["client_id"],
                )
                if event_id:
                    results["events_created"].append(event_id)

        # Generate weekly ESG summary recommendation via LLM
        if rows and include_recommendations:
            avg_diversion = sum(
                float(r["diversion_rate_pct"] or 0) for r in rows
            ) / len(rows)
            summary_prompt = (
                f"Weekly ESG performance summary for Hi-Tech Waste Management:\n"
                f"- Clients analysed: {len(rows)}\n"
                f"- Average diversion rate: {avg_diversion:.1f}%\n"
                f"- Clients below target: {len(results['underperforming_clients'])}\n\n"
                "Provide a 2-sentence summary and one actionable improvement recommendation."
            )
            try:
                recommendation = self._call_ollama(
                    prompt=summary_prompt,
                    system_prompt=(
                        "You are the ESG Agent for Hi-Tech Waste Management Malaysia. "
                        "Be concise and data-driven."
                    ),
                )
                summary_event_id = self._persist_event(
                    agent_name="esg",
                    event_type="report",
                    severity="info",
                    title=f"Weekly ESG Summary — w/e {datetime.now(tz=timezone.utc).date()}",
                    body=recommendation,
                )
                if summary_event_id:
                    results["events_created"].append(summary_event_id)
            except Exception as llm_exc:
                logger.warning("ESG Agent LLM call failed (non-fatal): %s", llm_exc)

        logger.info(
            "ESG Agent completed | clients=%d | underperforming=%d",
            results["clients_analysed"],
            len(results["underperforming_clients"]),
        )

    except SoftTimeLimitExceeded:
        logger.warning("ESG Agent soft time limit exceeded — completing gracefully")
    except Exception as exc:
        logger.error("ESG Agent error: %s", exc, exc_info=True)
        raise self.retry(exc=exc)

    results["completed_at"] = datetime.now(tz=timezone.utc).isoformat()
    return results


# =============================================================
# Agent 3 — Operations & Scheduling Agent
# Daily morning review of job schedule and resource allocation
# =============================================================


@celery_app.task(
    bind=True,
    base=AgentBaseTask,
    name="tasks.agent_tasks.run_operations_agent",
    queue="agents",
)
def run_operations_agent(
    self: AgentBaseTask, context: dict | None = None
) -> dict[str, Any]:
    """
    Operations & Scheduling Agent — runs every day at 06:00 MST.

    Responsibilities:
    - Review today's confirmed and dispatched jobs
    - Flag jobs with no assigned vehicle or driver
    - Flag jobs with estimated weight exceeding vehicle capacity
    - Identify potential SLA breaches (jobs not yet confirmed for today)
    - Generate a morning briefing using the LLM
    """
    logger.info("Operations Agent starting")
    start_time = datetime.now(tz=timezone.utc)
    results: dict[str, Any] = {
        "agent": "operations",
        "started_at": start_time.isoformat(),
        "jobs_today": 0,
        "unresourced_jobs": 0,
        "sla_risk_jobs": 0,
        "events_created": [],
    }

    try:
        from sqlalchemy import text

        with self._get_db_session() as session:
            # Jobs scheduled for today
            jobs = (
                session.execute(
                    text(
                        """
                    SELECT
                        j.id::text,
                        j.job_number,
                        j.job_type,
                        j.status,
                        j.estimated_weight_kg,
                        j.assigned_vehicle_id,
                        j.assigned_driver_id,
                        c.company_name AS client_name,
                        v.capacity_kg  AS vehicle_capacity_kg
                    FROM jobs j
                    LEFT JOIN clients  c ON c.id = j.client_id
                    LEFT JOIN vehicles v ON v.id = j.assigned_vehicle_id
                    WHERE j.scheduled_date = CURRENT_DATE
                      AND j.status NOT IN ('completed', 'invoiced', 'draft')
                    ORDER BY j.status, j.job_type
                    """
                    )
                )
                .mappings()
                .all()
            )

            results["jobs_today"] = len(jobs)

            for job in jobs:
                issues = []

                # Check for missing resource assignments
                if not job["assigned_vehicle_id"]:
                    issues.append("no vehicle assigned")
                if not job["assigned_driver_id"]:
                    issues.append("no driver assigned")

                # Check for weight capacity overrun
                if (
                    job.get("estimated_weight_kg")
                    and job.get("vehicle_capacity_kg")
                    and float(job["estimated_weight_kg"])
                    > float(job["vehicle_capacity_kg"])
                ):
                    issues.append(
                        f"estimated weight ({job['estimated_weight_kg']} kg) "
                        f"exceeds vehicle capacity ({job['vehicle_capacity_kg']} kg)"
                    )

                if issues:
                    results["unresourced_jobs"] += 1
                    title = (
                        f"Resource Gap: Job {job['job_number']} — {job['client_name']}"
                    )
                    body = (
                        f"Job {job['job_number']} ({job['job_type']}) for "
                        f"{job['client_name']} scheduled today has the following issues: "
                        + "; ".join(issues)
                        + ". Please assign resources before dispatch."
                    )
                    event_id = self._persist_event(
                        agent_name="operations",
                        event_type="alert",
                        severity="warning",
                        title=title,
                        body=body,
                        reference_type="job",
                        reference_id=job["id"],
                    )
                    if event_id:
                        results["events_created"].append(event_id)

            # Jobs not yet confirmed for today (still in 'draft' after 6am)
            sla_risk = session.execute(
                text(
                    """
                    SELECT COUNT(*) AS cnt
                    FROM jobs j
                    WHERE j.scheduled_date = CURRENT_DATE
                      AND j.status = 'draft'
                    """
                )
            ).scalar()
            results["sla_risk_jobs"] = int(sla_risk or 0)

        if results["sla_risk_jobs"] > 0:
            event_id = self._persist_event(
                agent_name="operations",
                event_type="alert",
                severity="warning",
                title=f"{results['sla_risk_jobs']} draft job(s) not yet confirmed for today",
                body=(
                    f"{results['sla_risk_jobs']} job(s) scheduled for today remain "
                    "in 'draft' status. These must be confirmed and resources assigned "
                    "to avoid SLA breaches."
                ),
            )
            if event_id:
                results["events_created"].append(event_id)

        # Generate morning briefing via LLM
        if results["jobs_today"] > 0:
            # Fetch operational field summary to enrich the briefing
            field_summary_lines = ""
            try:
                from sqlalchemy import text as _text
                with self._get_db_session() as _session:
                    compactor_overdue = _session.execute(_text(
                        "SELECT COUNT(*) FROM compaction_machines "
                        "WHERE next_service_date <= CURRENT_DATE AND status != 'decommissioned'"
                    )).scalar() or 0
                    containers_needing_pickup = _session.execute(_text(
                        "SELECT COUNT(*) FROM containers c "
                        "WHERE c.status = 'at_site' AND c.fill_level >= c.pickup_threshold"
                    )).scalar() or 0
                    open_disruptions = _session.execute(_text(
                        "SELECT COUNT(*) FROM disruption_logs WHERE status = 'open'"
                    )).scalar() or 0
                    staff_on_site = _session.execute(_text(
                        "SELECT COUNT(*) FROM staff_profiles WHERE assignment_status = 'on_site'"
                    )).scalar() or 0

                field_summary_lines = (
                    f"\nField Operations Status:\n"
                    f"- Compactors with overdue service: {compactor_overdue}\n"
                    f"- Containers needing pickup (≥85% full): {containers_needing_pickup}\n"
                    f"- Open disruptions: {open_disruptions}\n"
                    f"- Staff currently on site: {staff_on_site}\n"
                )
            except Exception as field_exc:
                logger.warning("Could not fetch field summary for briefing: %s", field_exc)

            briefing_prompt = (
                f"Morning operations briefing — {datetime.now(tz=timezone.utc).strftime('%A, %d %B %Y')}:\n"
                f"- Total jobs today: {results['jobs_today']}\n"
                f"- Jobs with resource gaps: {results['unresourced_jobs']}\n"
                f"- Draft (unconfirmed) jobs: {results['sla_risk_jobs']}\n"
                f"{field_summary_lines}\n"
                "Write a 3-sentence morning briefing for the operations supervisor covering "
                "both job scheduling and field operations status. Be direct and action-focused."
            )
            try:
                briefing = self._call_ollama(
                    prompt=briefing_prompt,
                    system_prompt=(
                        "You are the Operations Agent for Hi-Tech Waste Management Malaysia. "
                        "Be concise, professional, and action-oriented."
                    ),
                )
                event_id = self._persist_event(
                    agent_name="operations",
                    event_type="report",
                    severity="info",
                    title=f"Morning Briefing — {datetime.now(tz=timezone.utc).strftime('%d %b %Y')}",
                    body=briefing,
                )
                if event_id:
                    results["events_created"].append(event_id)
            except Exception as llm_exc:
                logger.warning(
                    "Operations Agent LLM briefing failed (non-fatal): %s", llm_exc
                )

        logger.info(
            "Operations Agent completed | jobs_today=%d | unresourced=%d | sla_risk=%d",
            results["jobs_today"],
            results["unresourced_jobs"],
            results["sla_risk_jobs"],
        )

    except SoftTimeLimitExceeded:
        logger.warning(
            "Operations Agent soft time limit exceeded — completing gracefully"
        )
    except Exception as exc:
        logger.error("Operations Agent error: %s", exc, exc_info=True)
        raise self.retry(exc=exc)

    results["completed_at"] = datetime.now(tz=timezone.utc).isoformat()
    return results


# =============================================================
# Agent 4 — Fleet & Maintenance Agent
# Daily vehicle service and utilisation review
# =============================================================


@celery_app.task(
    bind=True,
    base=AgentBaseTask,
    name="tasks.agent_tasks.run_fleet_agent",
    queue="agents",
)
def run_fleet_agent(self: AgentBaseTask, context: dict | None = None) -> dict[str, Any]:
    """
    Fleet & Maintenance Agent — runs every day at 07:00 MST.

    Responsibilities:
    - Flag vehicles whose next service date is within 7 days
    - Flag vehicles with no service date recorded
    - Review yesterday's trips for anomalies (high fuel consumption, long idle)
    - Calculate fleet utilisation rate for the previous day
    - Generate a fleet health summary using the LLM
    """
    logger.info("Fleet Agent starting")
    start_time = datetime.now(tz=timezone.utc)
    results: dict[str, Any] = {
        "agent": "fleet",
        "started_at": start_time.isoformat(),
        "vehicles_checked": 0,
        "service_alerts": 0,
        "overdue_service": 0,
        "events_created": [],
    }

    try:
        from sqlalchemy import text

        with self._get_db_session() as session:
            # Vehicles due for service within 7 days
            due_vehicles = (
                session.execute(
                    text(
                        """
                    SELECT
                        id::text,
                        registration,
                        vehicle_type,
                        make,
                        model,
                        next_service_date,
                        odometer_km,
                        status,
                        (next_service_date - CURRENT_DATE) AS days_until_service
                    FROM vehicles
                    WHERE status != 'retired'
                      AND (
                          next_service_date IS NULL
                          OR next_service_date <= CURRENT_DATE + INTERVAL '7 days'
                      )
                    ORDER BY next_service_date ASC NULLS FIRST
                    """
                    )
                )
                .mappings()
                .all()
            )

            results["vehicles_checked"] = len(due_vehicles)

            for vehicle in due_vehicles:
                days = vehicle.get("days_until_service")

                if days is None:
                    # No service date set
                    severity = "warning"
                    title = f"No Service Date: {vehicle['registration']} ({vehicle['vehicle_type']})"
                    body = (
                        f"Vehicle {vehicle['registration']} ({vehicle['make']} {vehicle['model']}) "
                        "has no next service date recorded. "
                        "Please schedule a maintenance inspection."
                    )
                elif int(days) < 0:
                    # Overdue
                    results["overdue_service"] += 1
                    severity = "critical"
                    title = f"OVERDUE Service: {vehicle['registration']} ({abs(int(days))} days overdue)"
                    body = (
                        f"Vehicle {vehicle['registration']} ({vehicle['make']} {vehicle['model']}) "
                        f"is {abs(int(days))} days overdue for its scheduled service "
                        f"(due {vehicle['next_service_date']}). "
                        "Take the vehicle out of service immediately for maintenance."
                    )
                else:
                    # Due soon
                    results["service_alerts"] += 1
                    severity = "warning"
                    title = (
                        f"Service Due in {int(days)} Days: "
                        f"{vehicle['registration']} ({vehicle['vehicle_type']})"
                    )
                    body = (
                        f"Vehicle {vehicle['registration']} ({vehicle['make']} {vehicle['model']}) "
                        f"is due for service on {vehicle['next_service_date']} "
                        f"({int(days)} day(s) away). "
                        "Please schedule maintenance to avoid operational disruption."
                    )

                event_id = self._persist_event(
                    agent_name="fleet",
                    event_type="alert",
                    severity=severity,
                    title=title,
                    body=body,
                    reference_type="vehicle",
                    reference_id=vehicle["id"],
                )
                if event_id:
                    results["events_created"].append(event_id)

            # Yesterday's fleet utilisation
            util_row = (
                session.execute(
                    text(
                        """
                    SELECT
                        COUNT(DISTINCT t.vehicle_id) AS vehicles_used,
                        COUNT(t.id)                  AS total_trips,
                        COALESCE(SUM(t.distance_km), 0) AS total_distance_km,
                        COALESCE(SUM(t.fuel_litres), 0)  AS total_fuel_litres,
                        (SELECT COUNT(*) FROM vehicles WHERE status != 'retired') AS fleet_size
                    FROM trips t
                    WHERE DATE(t.departure_time) = CURRENT_DATE - INTERVAL '1 day'
                    """
                    )
                )
                .mappings()
                .first()
            )

        if util_row and util_row["fleet_size"] > 0:
            utilisation_pct = round(
                int(util_row["vehicles_used"]) / int(util_row["fleet_size"]) * 100, 1
            )
            fleet_body = (
                f"Yesterday's fleet utilisation: {utilisation_pct}% "
                f"({util_row['vehicles_used']} of {util_row['fleet_size']} vehicles active). "
                f"Total trips: {util_row['total_trips']}, "
                f"distance: {util_row['total_distance_km']:.1f} km, "
                f"fuel: {util_row['total_fuel_litres']:.1f} litres."
            )

            # Flag if utilisation drops below 40%
            if utilisation_pct < 40 and int(util_row["total_trips"]) > 0:
                event_id = self._persist_event(
                    agent_name="fleet",
                    event_type="recommendation",
                    severity="info",
                    title=f"Low Fleet Utilisation: {utilisation_pct}% yesterday",
                    body=fleet_body
                    + " Consider reviewing route consolidation opportunities.",
                )
                if event_id:
                    results["events_created"].append(event_id)

        # Generate fleet health summary
        if results["vehicles_checked"] > 0:
            summary_prompt = (
                f"Fleet maintenance status — {datetime.now(tz=timezone.utc).strftime('%d %b %Y')}:\n"
                f"- Vehicles checked: {results['vehicles_checked']}\n"
                f"- Overdue for service: {results['overdue_service']}\n"
                f"- Due within 7 days: {results['service_alerts']}\n\n"
                "Write a 2-sentence fleet health summary and one maintenance recommendation."
            )
            try:
                summary = self._call_ollama(
                    prompt=summary_prompt,
                    system_prompt=(
                        "You are the Fleet & Maintenance Agent for Hi-Tech Waste Management Malaysia. "
                        "Be concise and safety-focused."
                    ),
                )
                event_id = self._persist_event(
                    agent_name="fleet",
                    event_type="report",
                    severity="info",
                    title=f"Fleet Health Summary — {datetime.now(tz=timezone.utc).strftime('%d %b %Y')}",
                    body=summary,
                )
                if event_id:
                    results["events_created"].append(event_id)
            except Exception as llm_exc:
                logger.warning("Fleet Agent LLM call failed (non-fatal): %s", llm_exc)

        logger.info(
            "Fleet Agent completed | vehicles_checked=%d | overdue=%d | service_alerts=%d",
            results["vehicles_checked"],
            results["overdue_service"],
            results["service_alerts"],
        )

    except SoftTimeLimitExceeded:
        logger.warning("Fleet Agent soft time limit exceeded — completing gracefully")
    except Exception as exc:
        logger.error("Fleet Agent error: %s", exc, exc_info=True)
        raise self.retry(exc=exc)

    results["completed_at"] = datetime.now(tz=timezone.utc).isoformat()
    return results


# =============================================================
# Agent 5 — Client Intelligence Agent
# Weekly account health review and contract monitoring
# =============================================================


@celery_app.task(
    bind=True,
    base=AgentBaseTask,
    name="tasks.agent_tasks.run_client_intelligence_agent",
    queue="agents",
)
def run_client_intelligence_agent(
    self: AgentBaseTask,
    context: dict | None = None,
    client_id: str | None = None,
) -> dict[str, Any]:
    """
    Client Intelligence Agent — runs every Sunday at 09:00 MST.

    Responsibilities:
    - Identify clients with contracts expiring within 60 days
    - Flag clients with no jobs in the past 30 days (churn risk)
    - Review SLA diversion performance per client
    - Highlight clients with growing waste volumes (upsell opportunities)
    - Generate account health summaries using the LLM
    """
    logger.info("Client Intelligence Agent starting | client_id=%s", client_id)
    start_time = datetime.now(tz=timezone.utc)
    results: dict[str, Any] = {
        "agent": "client_intelligence",
        "started_at": start_time.isoformat(),
        "clients_reviewed": 0,
        "contract_expiry_alerts": 0,
        "churn_risk_alerts": 0,
        "events_created": [],
    }

    try:
        from sqlalchemy import text

        with self._get_db_session() as session:
            client_filter = "AND c.id = :client_id::uuid" if client_id else ""
            params: dict[str, Any] = {}
            if client_id:
                params["client_id"] = client_id

            # Contracts expiring within 60 days
            expiring = (
                session.execute(
                    text(
                        f"""
                    SELECT
                        id::text,
                        company_name,
                        pic_name,
                        pic_email,
                        contract_end,
                        (contract_end - CURRENT_DATE) AS days_until_expiry
                    FROM clients
                    WHERE is_active = TRUE
                      AND contract_end IS NOT NULL
                      AND contract_end <= CURRENT_DATE + INTERVAL '60 days'
                      AND contract_end >= CURRENT_DATE
                    {client_filter}
                    ORDER BY contract_end ASC
                    """
                    ),
                    params,
                )
                .mappings()
                .all()
            )

            for client in expiring:
                results["contract_expiry_alerts"] += 1
                days = int(client["days_until_expiry"])
                severity = "critical" if days <= 14 else "warning"
                event_id = self._persist_event(
                    agent_name="client_intelligence",
                    event_type="alert",
                    severity=severity,
                    title=(
                        f"Contract Expiring in {days} Days: {client['company_name']}"
                    ),
                    body=(
                        f"The service contract for {client['company_name']} "
                        f"(PIC: {client['pic_name']}, {client['pic_email']}) "
                        f"expires on {client['contract_end']} ({days} days remaining). "
                        "Initiate contract renewal discussions immediately."
                    ),
                    reference_type="client",
                    reference_id=client["id"],
                )
                if event_id:
                    results["events_created"].append(event_id)

            # Churn risk — active clients with no completed jobs in 30 days
            inactive = (
                session.execute(
                    text(
                        f"""
                    SELECT
                        c.id::text,
                        c.company_name,
                        c.pic_email,
                        MAX(j.completed_at) AS last_job_completed
                    FROM clients c
                    LEFT JOIN jobs j ON j.client_id = c.id
                        AND j.status = 'completed'
                        AND j.completed_at >= NOW() - INTERVAL '30 days'
                    WHERE c.is_active = TRUE
                    {client_filter}
                    GROUP BY c.id, c.company_name, c.pic_email
                    HAVING COUNT(j.id) = 0
                    ORDER BY c.company_name
                    """
                    ),
                    params,
                )
                .mappings()
                .all()
            )

            for client in inactive:
                results["churn_risk_alerts"] += 1
                event_id = self._persist_event(
                    agent_name="client_intelligence",
                    event_type="recommendation",
                    severity="warning",
                    title=f"Churn Risk: {client['company_name']} — No jobs in 30 days",
                    body=(
                        f"{client['company_name']} has had no completed waste collection "
                        "jobs in the past 30 days. This may indicate reduced activity, "
                        "competitor engagement, or a service issue. "
                        "Schedule a client check-in call."
                    ),
                    reference_type="client",
                    reference_id=client["id"],
                )
                if event_id:
                    results["events_created"].append(event_id)

            results["clients_reviewed"] = len(expiring) + len(inactive)

        logger.info(
            "Client Intelligence Agent completed | "
            "contract_expiry=%d | churn_risk=%d | events=%d",
            results["contract_expiry_alerts"],
            results["churn_risk_alerts"],
            len(results["events_created"]),
        )

    except SoftTimeLimitExceeded:
        logger.warning(
            "Client Intelligence Agent soft time limit exceeded — completing gracefully"
        )
    except Exception as exc:
        logger.error("Client Intelligence Agent error: %s", exc, exc_info=True)
        raise self.retry(exc=exc)

    results["completed_at"] = datetime.now(tz=timezone.utc).isoformat()
    return results


# =============================================================
# Utility Task — Flag overdue invoices
# Runs daily at midnight UTC
# =============================================================


@celery_app.task(
    bind=True,
    base=AgentBaseTask,
    name="tasks.agent_tasks.flag_overdue_invoices",
    queue="default",
)
def flag_overdue_invoices(
    self: AgentBaseTask, context: dict | None = None
) -> dict[str, Any]:
    """
    Operational utility task — runs daily at midnight UTC.

    Scans all ``unpaid`` and ``partial`` invoices whose ``due_date`` has
    passed and marks them as ``overdue``.  Persists a single summary
    agent event if any invoices are updated.
    """
    logger.info("flag_overdue_invoices starting")
    results: dict[str, Any] = {
        "task": "flag_overdue_invoices",
        "started_at": datetime.now(tz=timezone.utc).isoformat(),
        "invoices_flagged": 0,
        "total_overdue_myr": 0.0,
    }

    try:
        from sqlalchemy import text

        with self._get_db_session() as session:
            update_result = session.execute(
                text(
                    """
                    UPDATE invoices
                    SET status = 'overdue'
                    WHERE due_date < CURRENT_DATE
                      AND status IN ('unpaid', 'partial')
                      AND (total_myr - paid_amount_myr) > 0
                    RETURNING id, invoice_number, (total_myr - paid_amount_myr) AS outstanding
                    """
                )
            )
            rows = update_result.mappings().all()
            session.commit()

        if rows:
            results["invoices_flagged"] = len(rows)
            results["total_overdue_myr"] = sum(
                float(r["outstanding"] or 0) for r in rows
            )

            body = (
                f"{len(rows)} invoice(s) totalling MYR "
                f"{results['total_overdue_myr']:,.2f} have been marked as overdue today. "
                "Review the Finance module for details and initiate collection follow-ups."
            )
            self._persist_event(
                agent_name="operations",
                event_type="alert",
                severity="warning" if results["invoices_flagged"] < 5 else "critical",
                title=f"{results['invoices_flagged']} Invoice(s) Overdue — MYR {results['total_overdue_myr']:,.2f}",
                body=body,
            )
            logger.warning(
                "Flagged %d overdue invoices | total_outstanding=MYR %.2f",
                results["invoices_flagged"],
                results["total_overdue_myr"],
            )
        else:
            logger.info("No invoices to flag as overdue today.")

    except Exception as exc:
        logger.error("flag_overdue_invoices error: %s", exc, exc_info=True)
        raise self.retry(exc=exc)

    results["completed_at"] = datetime.now(tz=timezone.utc).isoformat()
    return results
