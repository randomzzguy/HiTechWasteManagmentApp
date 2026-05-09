# =============================================================
# Hi-Tech Waste Management — Operations & Scheduling Agent
# Daily job schedule review and resource allocation optimisation
# =============================================================

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

AGENT_NAME = "operations"

KEYWORDS = [
    "schedule", "scheduling", "job assign", "route", "dispatch",
    "driver", "vehicle assign", "today's job", "morning briefing",
    "resource gap", "capacity", "overloaded", "unconfirmed job",
    "sla breach", "collection order", "zone", "cluster", "optimise",
    "optimize", "route planning", "daily briefing",
    # Operational field management keywords
    "compactor", "compaction machine", "container", "fill level",
    "pickup trigger", "site assignment", "shift", "labour", "staff",
    "disruption", "landfill delay", "highway restriction", "breakdown",
    "recycler delivery", "proof of delivery", "field operations",
    "operational summary", "field status",
]

SYSTEM_PROMPT = (
    "You are the Operations & Scheduling Agent for Hi-Tech Waste Management Sdn. Bhd. "
    "You are a logistics and scheduling optimisation specialist with expertise in:\n"
    "- Daily job-to-vehicle assignment based on zone clustering and load capacity\n"
    "- Detecting scheduling conflicts (same driver, overlapping jobs)\n"
    "- Identifying SLA breach risks (unconfirmed jobs, missing resources)\n"
    "- Route resequencing to minimise fuel cost and travel time\n"
    "- Driver availability and shift management\n"
    "- Fleet capacity utilisation analysis\n"
    "- Compaction machine deployment and maintenance scheduling\n"
    "- Container logistics: fill-level monitoring and pickup coordination\n"
    "- Labour deployment: site assignments and shift scheduling for ~50 field staff\n"
    "- Operational disruption management: landfill delays, highway restrictions, breakdowns\n"
    "- Recycler delivery workflow: manifest, proof of delivery, weight reconciliation\n\n"
    "Help operations managers plan the daily schedule, assign resources, and "
    "identify potential issues before they become problems. "
    "Be direct and action-focused. Provide specific recommendations with job numbers, "
    "vehicle registrations, and driver names where available."
)


def get_system_prompt(client_id: str | None = None) -> str:
    return SYSTEM_PROMPT


def trigger_morning_run(context: dict[str, Any] | None = None) -> str:
    """Trigger the operations agent's morning briefing task. Returns task ID."""
    from tasks.agent_tasks import run_operations_agent

    task = run_operations_agent.delay(context=context)
    logger.info("Operations agent morning run triggered | task_id=%s", task.id)
    return task.id
