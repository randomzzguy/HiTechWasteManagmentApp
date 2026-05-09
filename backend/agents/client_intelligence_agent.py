# =============================================================
# Hi-Tech Waste Management — Client Intelligence Agent
# RAG-primary agent for client queries and account management
# =============================================================

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

AGENT_NAME = "client"

KEYWORDS = [
    "client", "customer", "account", "company", "contract", "renewal",
    "churn", "upsell", "cross-sell", "waste volume", "tonnage history",
    "bsf enrol", "food waste client", "email draft", "service history",
    "client portal", "pic", "person in charge", "sla", "diversion target",
    "account manager", "client profile",
]

SYSTEM_PROMPT = (
    "You are the Client Intelligence Agent for Hi-Tech Waste Management Sdn. Bhd. "
    "You are a customer success analyst with expertise in:\n"
    "- Answering natural language queries about client history, waste volumes, "
    "and service performance\n"
    "- Identifying upsell and cross-sell opportunities from waste stream data "
    "(e.g. clients generating food waste not enrolled in BSF programme)\n"
    "- Detecting churn signals (declining volumes, missed collections, contract expiry)\n"
    "- Drafting professional client-facing emails, status updates, and reports\n"
    "- Generating new-staff briefings on client history and preferences\n"
    "- Benchmarking client performance against industry averages\n\n"
    "Always cite specific job numbers, dates, and tonnage figures when available. "
    "Be professional and client-centric in all communications. "
    "When drafting emails, use formal Malaysian business English."
)


def get_system_prompt(client_id: str | None = None) -> str:
    prompt = SYSTEM_PROMPT
    if client_id:
        prompt += (
            f"\n\nThis query is scoped to client ID: {client_id}. "
            "Focus exclusively on this client's data, history, and opportunities."
        )
    return prompt


def trigger_weekly_run(context: dict[str, Any] | None = None) -> str:
    """Trigger the client intelligence agent's weekly review. Returns task ID."""
    from tasks.agent_tasks import run_client_intelligence_agent

    task = run_client_intelligence_agent.delay(context=context)
    logger.info("Client intelligence agent weekly run triggered | task_id=%s", task.id)
    return task.id
