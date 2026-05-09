# =============================================================
# Hi-Tech Waste Management — ESG & Carbon Agent
# Weekly carbon footprint analysis and diversion rate monitoring
# =============================================================

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

AGENT_NAME = "esg"

KEYWORDS = [
    "esg", "carbon", "co2", "co₂", "ghg", "greenhouse", "diversion rate",
    "diversion", "recyclable", "recycling rate", "sustainability",
    "scope 3", "sdg", "emission", "landfill avoidance", "wte",
    "waste to energy", "carbon footprint", "net zero", "climate",
    "sdg 12", "sdg 13", "sdg 15", "ghg protocol", "ipcc",
]

SYSTEM_PROMPT = (
    "You are the ESG & Carbon Agent for Hi-Tech Waste Management Sdn. Bhd. "
    "You are a GHG Protocol and ESG reporting specialist with expertise in:\n"
    "- Scope 3 Category 5 (waste generated in operations) carbon accounting\n"
    "- Malaysia-specific emission factors (MyCC, IPCC AR6)\n"
    "- Waste diversion rate calculations and benchmarking\n"
    "- SDG alignment: SDG 12 (Responsible Consumption), SDG 13 (Climate Action), "
    "SDG 15 (Life on Land)\n"
    "- GHG Protocol Corporate Value Chain Standard\n"
    "- Landfill methane avoidance credits and recycling GHG savings (WRAP methodology)\n\n"
    "Calculate and explain carbon footprints, diversion rates, and ESG metrics. "
    "Draft ESG narrative summaries in English and Bahasa Malaysia when requested. "
    "Be data-driven and always cite methodology sources."
)


def get_system_prompt(client_id: str | None = None) -> str:
    prompt = SYSTEM_PROMPT
    if client_id:
        prompt += (
            f"\n\nThis query is scoped to client ID: {client_id}. "
            "Focus on this client's carbon records, diversion rates, and ESG performance."
        )
    return prompt


def trigger_weekly_run(
    period: str = "weekly",
    client_id: str | None = None,
) -> str:
    """Trigger the ESG agent's weekly Celery task. Returns task ID."""
    from tasks.agent_tasks import run_esg_agent

    task = run_esg_agent.delay(period=period, client_id=client_id)
    logger.info("ESG agent weekly run triggered | task_id=%s", task.id)
    return task.id


def trigger_on_demand(
    client_id: str | None = None,
    period_start: str | None = None,
    period_end: str | None = None,
) -> str:
    """Trigger an on-demand ESG analysis. Returns task ID."""
    from tasks.agent_tasks import run_esg_agent

    task = run_esg_agent.delay(
        period="custom",
        client_id=client_id,
        period_start=period_start,
        period_end=period_end,
        include_recommendations=True,
    )
    logger.info(
        "ESG agent on-demand run triggered | client=%s | task_id=%s",
        client_id,
        task.id,
    )
    return task.id
