# =============================================================
# Hi-Tech Waste Management — Agent Orchestrator
# Routes user queries to the appropriate AI agent
# =============================================================

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# =============================================================
# Intent keyword maps
# =============================================================

_INTENT_KEYWORDS: dict[str, list[str]] = {
    "compliance": [
        "sw code", "sw305", "sw410", "scheduled waste", "consignment note",
        "eswis", "e-swis", "cenviro", "doe", "storage deadline", "90 day",
        "90-day", "compliance", "regulation", "eqa", "act 127", "hazardous",
        "toxic", "waste code", "packaging requirement",
    ],
    "esg": [
        "esg", "carbon", "co2", "co₂", "ghg", "greenhouse", "diversion rate",
        "diversion", "recyclable", "recycling rate", "sustainability",
        "scope 3", "sdg", "emission", "landfill avoidance", "wte",
        "waste to energy", "carbon footprint", "net zero",
    ],
    "operations": [
        "schedule", "scheduling", "job assign", "route", "dispatch",
        "driver", "vehicle assign", "today's job", "morning briefing",
        "resource gap", "capacity", "overloaded", "unconfirmed job",
        "sla breach", "collection order",
    ],
    "fleet": [
        "fleet", "vehicle", "truck", "lorry", "maintenance", "service due",
        "odometer", "fuel consumption", "fuel usage", "gps", "breakdown",
        "repair", "tyre", "engine", "compactor", "hook loader",
    ],
    "client": [
        "client", "customer", "account", "company", "contract", "renewal",
        "churn", "upsell", "cross-sell", "waste volume", "tonnage history",
        "bsf enrol", "food waste client", "email draft", "service history",
    ],
}


def detect_intent(message: str) -> str:
    """
    Analyse a user message and return the most likely agent intent.

    Returns one of: 'compliance' | 'esg' | 'operations' | 'fleet' | 'client'
    Defaults to 'client' when intent is ambiguous.
    """
    lower = message.lower()
    scores: dict[str, int] = {intent: 0 for intent in _INTENT_KEYWORDS}

    for intent, keywords in _INTENT_KEYWORDS.items():
        for kw in keywords:
            if kw in lower:
                scores[intent] += 1

    best_intent = max(scores, key=lambda k: scores[k])

    # Default to client intelligence when no clear signal
    if scores[best_intent] == 0:
        return "client"

    logger.debug("Intent detection: scores=%s → %s", scores, best_intent)
    return best_intent


def get_agent_system_prompt(intent: str, client_id: str | None = None) -> str:
    """
    Return the specialised system prompt for the given agent intent.
    Optionally scopes the prompt to a specific client.
    """
    base = (
        "You are HiTech AI, the intelligent assistant for Hi-Tech Waste Management "
        "Sdn. Bhd., a Malaysian environmental services company. "
        "Always be accurate, professional, and concise. "
        "Cite specific regulations, job numbers, or data sources when relevant.\n\n"
    )

    if client_id:
        base += f"This query is scoped to client ID: {client_id}. Focus on this client's data.\n\n"

    prompts = {
        "compliance": (
            base
            + "You are the Compliance Agent — a DOE scheduled waste compliance expert. "
            "You have deep knowledge of Malaysia's Environmental Quality Act 1974, "
            "Scheduled Wastes Regulations 2005, SW codes (First Schedule), "
            "e-SWIS consignment note requirements, and Cenviro coordination procedures. "
            "Help staff identify correct SW codes, packaging requirements, storage rules, "
            "and draft consignment note data. Always cite the specific regulation or clause."
        ),
        "esg": (
            base
            + "You are the ESG & Carbon Agent — a GHG Protocol and ESG reporting specialist. "
            "You calculate waste diversion rates, carbon footprints (Scope 3 Category 5), "
            "and generate sustainability narratives aligned with SDG 12, 13, and 15. "
            "Use Malaysia-specific emission factors where available. "
            "Be data-driven and cite methodology sources."
        ),
        "operations": (
            base
            + "You are the Operations & Scheduling Agent — a logistics and scheduling optimizer. "
            "You help assign jobs to vehicles and drivers, detect scheduling conflicts, "
            "suggest route resequencing to minimise fuel costs, and generate morning briefings. "
            "Consider vehicle capacity, driver availability, and zone clustering."
        ),
        "fleet": (
            base
            + "You are the Fleet & Maintenance Agent — a fleet maintenance and telematics expert. "
            "You monitor vehicle service schedules, flag overdue maintenance, "
            "analyse fuel consumption patterns, and detect GPS route deviations. "
            "Prioritise safety and regulatory compliance in all recommendations."
        ),
        "client": (
            base
            + "You are the Client Intelligence Agent — a customer success analyst. "
            "You answer natural language queries about client history, waste volumes, "
            "service performance, and contract status. "
            "Identify upsell opportunities, churn risks, and draft client communications. "
            "Always cite specific job numbers, dates, and tonnage figures when available."
        ),
    }

    return prompts.get(intent, prompts["client"])


def build_messages(
    user_message: str,
    system_prompt: str,
    conversation_history: list[dict[str, str]] | None = None,
    max_history: int = 20,
) -> list[dict[str, str]]:
    """
    Construct the full message list for the Ollama /api/chat endpoint.

    Format:
        [system_message, ...history[-max_history:], user_message]
    """
    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt}
    ]

    if conversation_history:
        recent = conversation_history[-max_history:]
        for msg in recent:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": user_message})
    return messages
