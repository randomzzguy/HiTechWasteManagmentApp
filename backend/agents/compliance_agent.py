# =============================================================
# Hi-Tech Waste Management — Compliance Agent
# Scheduled waste deadline monitoring + consignment note drafting
# =============================================================

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

AGENT_NAME = "compliance"

# Intent keywords used by the orchestrator for routing
KEYWORDS = [
    "sw code", "sw305", "sw410", "scheduled waste", "consignment note",
    "eswis", "e-swis", "cenviro", "doe", "storage deadline", "90 day",
    "90-day", "compliance", "regulation", "eqa", "act 127", "hazardous",
    "toxic", "waste code", "packaging requirement", "first schedule",
]

SYSTEM_PROMPT = (
    "You are the Compliance Agent for Hi-Tech Waste Management Sdn. Bhd. "
    "You are a DOE scheduled waste compliance expert with deep knowledge of:\n"
    "- Malaysia's Environmental Quality Act 1974 (EQA)\n"
    "- Scheduled Wastes Regulations 2005\n"
    "- SW codes from the First Schedule (e.g. SW305 = used lubricating oil, "
    "SW410 = batteries, SW420 = e-waste)\n"
    "- e-SWIS consignment note requirements and Cenviro coordination procedures\n"
    "- The 90-day on-site storage rule and enforcement thresholds\n\n"
    "Help staff identify correct SW codes, packaging requirements, storage rules, "
    "and draft consignment note data. Always cite the specific regulation or clause. "
    "Be precise and legally accurate — errors in scheduled waste compliance carry "
    "significant regulatory penalties."
)


def get_system_prompt(client_id: str | None = None) -> str:
    """Return the compliance agent system prompt, optionally scoped to a client."""
    prompt = SYSTEM_PROMPT
    if client_id:
        prompt += (
            f"\n\nThis query is scoped to client ID: {client_id}. "
            "Focus on this client's scheduled waste batches and compliance status."
        )
    return prompt


def trigger_scheduled_run(context: dict[str, Any] | None = None) -> str:
    """
    Trigger the compliance agent's scheduled Celery task.
    Returns the Celery task ID.
    """
    from tasks.agent_tasks import run_compliance_agent

    task = run_compliance_agent.delay(context=context)
    logger.info("Compliance agent scheduled run triggered | task_id=%s", task.id)
    return task.id


def trigger_on_new_batch(batch_id: str, client_id: str | None = None) -> str:
    """
    Trigger the compliance agent when a new SW batch is created.
    Returns the Celery task ID.
    """
    from tasks.agent_tasks import run_compliance_agent

    context = {"trigger": "new_sw_batch", "batch_id": batch_id, "client_id": client_id}
    task = run_compliance_agent.delay(context=context)
    logger.info(
        "Compliance agent triggered on new batch | batch_id=%s | task_id=%s",
        batch_id,
        task.id,
    )
    return task.id
