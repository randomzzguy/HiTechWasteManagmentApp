# =============================================================
# Hi-Tech Waste Management — Celery Application
# Redis broker + result backend, beat schedule for AI agents
# =============================================================

from __future__ import annotations

import logging
import os
from datetime import timedelta

from celery import Celery
from celery.schedules import crontab
from celery.signals import (
    beat_init,
    celeryd_after_setup,
    task_failure,
    task_postrun,
    task_prerun,
    task_success,
    worker_ready,
)
from kombu import Exchange, Queue

logger = logging.getLogger(__name__)

# =============================================================
# Redis connection URL
# Read directly from env so the Celery app can be imported
# before the FastAPI lifespan runs (e.g. in celery worker CLI).
# =============================================================

REDIS_URL: str = os.environ.get("REDIS_URL", "redis://localhost:6379")

# Separate Redis DBs for broker (0) and result backend (1)
# to keep keys cleanly separated.
BROKER_URL: str = f"{REDIS_URL.rstrip('/')}/0"
RESULT_BACKEND_URL: str = f"{REDIS_URL.rstrip('/')}/1"


# =============================================================
# Queue definitions
# Three priority queues — agents run in a dedicated queue so
# long-running LLM tasks never starve operational tasks.
# =============================================================

default_exchange = Exchange("default", type="direct")
agents_exchange = Exchange("agents", type="direct")
reports_exchange = Exchange("reports", type="direct")

TASK_QUEUES = (
    Queue("default", default_exchange, routing_key="default"),
    Queue("agents", agents_exchange, routing_key="agents"),
    Queue("reports", reports_exchange, routing_key="reports"),
)


# =============================================================
# Beat schedule
# All times are in UTC.  Malaysia Standard Time (MST) = UTC+8,
# so a 6 AM MST start is 22:00 UTC the previous day.
# =============================================================

BEAT_SCHEDULE: dict = {
    # ── Compliance Agent ────────────────────────────────────
    # Runs every 6 hours to check scheduled waste storage deadlines,
    # flag overdue batches, and push alerts to the WebSocket room.
    "compliance-check": {
        "task": "tasks.agent_tasks.run_compliance_agent",
        "schedule": timedelta(hours=6),
        "options": {
            "queue": "agents",
            "expires": 21_600,  # Expire after 6 h if not picked up
        },
        "kwargs": {},
    },
    # ── ESG & Carbon Agent ───────────────────────────────────
    # Runs every Monday at 08:00 MST (00:00 UTC Monday).
    # Aggregates the previous week's carbon data and posts ESG digest.
    "esg-weekly": {
        "task": "tasks.agent_tasks.run_esg_agent",
        "schedule": crontab(hour=0, minute=0, day_of_week="monday"),
        "options": {
            "queue": "agents",
            "expires": 86_400,  # Expire after 24 h if not picked up
        },
        "kwargs": {"period": "weekly"},
    },
    # ── Operations & Scheduling Agent ────────────────────────
    # Runs every day at 06:00 MST (22:00 UTC previous day).
    # Reviews today's job schedule, checks SLA compliance, and
    # flags any unconfirmed or under-resourced jobs.
    "operations-morning": {
        "task": "tasks.agent_tasks.run_operations_agent",
        "schedule": crontab(hour=22, minute=0),  # 22:00 UTC = 06:00 MST
        "options": {
            "queue": "agents",
            "expires": 43_200,  # Expire after 12 h
        },
        "kwargs": {},
    },
    # ── Fleet & Maintenance Agent ─────────────────────────────
    # Runs every day at 07:00 MST (23:00 UTC previous day).
    # Checks vehicle service schedules, flags vehicles due for
    # maintenance, and reviews the previous day's trip data.
    "fleet-daily": {
        "task": "tasks.agent_tasks.run_fleet_agent",
        "schedule": crontab(hour=23, minute=0),  # 23:00 UTC = 07:00 MST
        "options": {
            "queue": "agents",
            "expires": 43_200,  # Expire after 12 h
        },
        "kwargs": {},
    },
    # ── Client Intelligence Agent — Weekly ───────────────────
    # Every Sunday at 09:00 MST (01:00 UTC Sunday).
    # Reviews client waste profiles, diversion trends, and contract
    # renewal dates; generates account health summaries.
    "client-intelligence-weekly": {
        "task": "tasks.agent_tasks.run_client_intelligence_agent",
        "schedule": crontab(hour=1, minute=0, day_of_week="sunday"),
        "options": {
            "queue": "agents",
            "expires": 86_400,
        },
        "kwargs": {},
    },
    # ── Overdue invoice auto-flag ─────────────────────────────
    # Every day at midnight UTC — marks unpaid invoices whose
    # due_date has passed as 'overdue'.
    "invoice-overdue-check": {
        "task": "tasks.agent_tasks.flag_overdue_invoices",
        "schedule": crontab(hour=0, minute=0),
        "options": {
            "queue": "default",
            "expires": 86_400,
        },
        "kwargs": {},
    },
    # ── Compactor service due date check ──────────────────────
    # Every day at 07:30 MST (23:30 UTC previous day).
    # Escalates overdue machines to 'maintenance' and alerts.
    "compactor-service-check": {
        "task": "tasks.operational_field_tasks.check_compactor_service",
        "schedule": crontab(hour=23, minute=30),
        "options": {
            "queue": "default",
            "expires": 43_200,
        },
        "kwargs": {},
    },
    # ── Foreign worker permit expiry check ────────────────────
    # Every day at 08:00 MST (00:00 UTC).
    # Alerts 30 days before work permit expiry.
    "work-permit-expiry-check": {
        "task": "tasks.operational_field_tasks.check_work_permit_expiry",
        "schedule": crontab(hour=0, minute=0),
        "options": {
            "queue": "default",
            "expires": 86_400,
        },
        "kwargs": {},
    },
    # ── Disruption log escalation ─────────────────────────────
    # Every 30 minutes — escalates disruptions open > 4 hours
    # to 'critical' severity and notifies management.
    "disruption-escalation": {
        "task": "tasks.operational_field_tasks.escalate_stale_disruptions",
        "schedule": timedelta(minutes=30),
        "options": {
            "queue": "default",
            "expires": 1_800,
        },
        "kwargs": {},
    },
    # ── Scheduled Waste 90-day storage deadline alerts ────────
    # Every day at 08:00 MST (00:00 UTC).
    # Alerts at 15, 5, and 1 day(s) remaining — WhatsApp + email + in-app.
    "sw-storage-deadline-check": {
        "task": "tasks.operational_field_tasks.check_sw_storage_deadlines",
        "schedule": crontab(hour=0, minute=5),  # 00:05 UTC = 08:05 MST
        "options": {
            "queue": "default",
            "expires": 86_400,
        },
        "kwargs": {},
    },
    # ── Client contract expiry alerts ─────────────────────────
    # Every day at 08:10 MST (00:10 UTC).
    # Alerts management at 90, 60, and 30 days before contract end.
    "contract-expiry-check": {
        "task": "tasks.operational_field_tasks.check_contract_expiry",
        "schedule": crontab(hour=0, minute=10),  # 00:10 UTC = 08:10 MST
        "options": {
            "queue": "default",
            "expires": 86_400,
        },
        "kwargs": {},
    },
}


# =============================================================
# Celery application factory
# =============================================================


def _create_celery_app() -> Celery:
    """
    Construct and configure the Celery application instance.

    Configuration is set programmatically rather than via a separate
    config file so it stays close to the application code and is easy
    to override in tests.
    """
    app = Celery(
        "hitech_waste",
        broker=BROKER_URL,
        backend=RESULT_BACKEND_URL,
        include=[
            "tasks.agent_tasks",
            "tasks.rag_tasks",
            "tasks.report_tasks",
            "tasks.operational_field_tasks",
        ],
    )

    app.conf.update(
        # ── Serialisation ─────────────────────────────────────
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        event_serializer="json",
        # ── Timezone ──────────────────────────────────────────
        timezone="UTC",
        enable_utc=True,
        # ── Broker ────────────────────────────────────────────
        broker_url=BROKER_URL,
        broker_connection_retry_on_startup=True,
        broker_connection_max_retries=10,
        broker_transport_options={
            "visibility_timeout": 3600,  # 1 hour — covers long LLM runs
            "socket_timeout": 30,
            "socket_connect_timeout": 10,
        },
        # ── Result backend ────────────────────────────────────
        result_backend=RESULT_BACKEND_URL,
        result_expires=86_400,  # Keep results for 24 hours
        result_compression="zlib",
        # ── Task execution ────────────────────────────────────
        task_acks_late=True,  # Ack only after task completes
        task_reject_on_worker_lost=True,  # Re-queue if worker crashes mid-task
        task_track_started=True,  # Expose STARTED state for polling
        task_time_limit=3600,  # Hard kill after 1 hour
        task_soft_time_limit=3300,  # Soft kill (SoftTimeLimitExceeded) at 55 min
        task_default_retry_delay=60,  # Wait 60 s before retrying
        task_max_retries=3,
        # ── Queues ────────────────────────────────────────────
        task_queues=TASK_QUEUES,
        task_default_queue="default",
        task_default_exchange="default",
        task_default_routing_key="default",
        task_routes={
            "tasks.agent_tasks.run_*": {"queue": "agents"},
            "tasks.agent_tasks.flag_overdue_*": {"queue": "default"},
            "tasks.operational_field_tasks.*": {"queue": "default"},
            "tasks.report_tasks.*": {"queue": "reports"},
        },
        # ── Worker ────────────────────────────────────────────
        worker_prefetch_multiplier=1,  # One task at a time per worker process
        worker_max_tasks_per_child=100,  # Restart worker process after 100 tasks
        worker_hijack_root_logger=False,  # Preserve our logging config
        worker_redirect_stdouts=False,
        # ── Beat ──────────────────────────────────────────────
        beat_schedule=BEAT_SCHEDULE,
        beat_scheduler="celery.beat:PersistentScheduler",
        beat_schedule_filename="/app/celerybeat-schedule",
        beat_max_loop_interval=5,
        # ── Monitoring ────────────────────────────────────────
        task_send_sent_event=True,
        worker_send_task_events=True,
    )

    return app


celery_app: Celery = _create_celery_app()


# =============================================================
# Signal handlers
# Provide structured logging for task lifecycle events.
# =============================================================


@task_prerun.connect
def on_task_prerun(
    task_id: str,
    task: object,
    args: tuple,
    kwargs: dict,
    **extras,
) -> None:
    """Log the start of every task execution."""
    logger.info(
        "TASK STARTED | task_id=%s | name=%s | args=%s | kwargs=%s",
        task_id,
        getattr(task, "name", "unknown"),
        args,
        kwargs,
    )


@task_postrun.connect
def on_task_postrun(
    task_id: str,
    task: object,
    args: tuple,
    kwargs: dict,
    retval: object,
    state: str,
    **extras,
) -> None:
    """Log the completion state of every task."""
    logger.info(
        "TASK FINISHED | task_id=%s | name=%s | state=%s",
        task_id,
        getattr(task, "name", "unknown"),
        state,
    )


@task_success.connect
def on_task_success(
    sender: object,
    result: object,
    **extras,
) -> None:
    """Log successful task results at DEBUG level."""
    logger.debug(
        "TASK SUCCESS | name=%s | result=%r",
        getattr(sender, "name", "unknown"),
        result,
    )


@task_failure.connect
def on_task_failure(
    task_id: str,
    exception: Exception,
    args: tuple,
    kwargs: dict,
    traceback: object,
    einfo: object,
    **extras,
) -> None:
    """Log task failures with full exception info."""
    logger.error(
        "TASK FAILED | task_id=%s | exception=%s | args=%s | kwargs=%s",
        task_id,
        repr(exception),
        args,
        kwargs,
        exc_info=True,
    )


@worker_ready.connect
def on_worker_ready(sender: object, **extras) -> None:
    """Emit a banner log line when the Celery worker comes online."""
    logger.info(
        "Celery worker READY | hostname=%s | queues=%s",
        getattr(sender, "hostname", "unknown"),
        [q.name for q in TASK_QUEUES],
    )


@beat_init.connect
def on_beat_init(sender: object, **extras) -> None:
    """Log the beat schedule summary on initialisation."""
    logger.info(
        "Celery beat INITIALISED | scheduled tasks: %s",
        list(BEAT_SCHEDULE.keys()),
    )


@celeryd_after_setup.connect
def on_celeryd_after_setup(
    sender: str,
    instance: object,
    **extras,
) -> None:
    """Log worker configuration details after setup completes."""
    logger.info(
        "Celery worker configured | sender=%s | broker=%s",
        sender,
        BROKER_URL,
    )
