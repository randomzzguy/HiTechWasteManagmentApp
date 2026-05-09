# =============================================================
# Hi-Tech Waste Management — Fleet & Maintenance Agent
# Daily vehicle service monitoring and GPS anomaly detection
# =============================================================

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

AGENT_NAME = "fleet"

KEYWORDS = [
    "fleet", "vehicle", "truck", "lorry", "maintenance", "service due",
    "odometer", "fuel consumption", "fuel usage", "gps", "breakdown",
    "repair", "tyre", "engine", "compactor", "hook loader", "skip truck",
    "van", "registration", "road tax", "puspakom", "inspection",
    "route deviation", "geofence", "telematics",
]

SYSTEM_PROMPT = (
    "You are the Fleet & Maintenance Agent for Hi-Tech Waste Management Sdn. Bhd. "
    "You are a fleet maintenance and telematics expert with expertise in:\n"
    "- Preventive maintenance scheduling (mileage and time-based thresholds)\n"
    "- Fuel consumption analysis and anomaly detection\n"
    "- GPS route deviation monitoring and geofence alerts\n"
    "- Vehicle lifecycle management (retirement/replacement signals)\n"
    "- Malaysian road transport regulations (JPJ, PUSPAKOM inspection requirements)\n"
    "- Fleet utilisation rate optimisation\n\n"
    "Monitor vehicle health, flag maintenance issues, and analyse fleet performance. "
    "Prioritise safety and regulatory compliance in all recommendations. "
    "Reference specific vehicle registrations and odometer readings when available."
)


def get_system_prompt(client_id: str | None = None) -> str:
    return SYSTEM_PROMPT


def trigger_daily_run(context: dict[str, Any] | None = None) -> str:
    """Trigger the fleet agent's daily check task. Returns task ID."""
    from tasks.agent_tasks import run_fleet_agent

    task = run_fleet_agent.delay(context=context)
    logger.info("Fleet agent daily run triggered | task_id=%s", task.id)
    return task.id


def trigger_on_gps_anomaly(vehicle_id: str, anomaly_type: str) -> str:
    """Trigger the fleet agent on a GPS anomaly event. Returns task ID."""
    from tasks.agent_tasks import run_fleet_agent

    context = {
        "trigger": "gps_anomaly",
        "vehicle_id": vehicle_id,
        "anomaly_type": anomaly_type,
    }
    task = run_fleet_agent.delay(context=context)
    logger.info(
        "Fleet agent triggered on GPS anomaly | vehicle=%s | type=%s | task_id=%s",
        vehicle_id,
        anomaly_type,
        task.id,
    )
    return task.id
