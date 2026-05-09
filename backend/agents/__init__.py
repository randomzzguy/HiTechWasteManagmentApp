# =============================================================
# Hi-Tech Waste Management — Agents Package
# =============================================================

from .client_intelligence_agent import (
    AGENT_NAME as CLIENT_AGENT_NAME,
    get_system_prompt as get_client_prompt,
)
from .compliance_agent import (
    AGENT_NAME as COMPLIANCE_AGENT_NAME,
    get_system_prompt as get_compliance_prompt,
)
from .esg_agent import (
    AGENT_NAME as ESG_AGENT_NAME,
    get_system_prompt as get_esg_prompt,
)
from .fleet_agent import (
    AGENT_NAME as FLEET_AGENT_NAME,
    get_system_prompt as get_fleet_prompt,
)
from .operations_agent import (
    AGENT_NAME as OPERATIONS_AGENT_NAME,
    get_system_prompt as get_operations_prompt,
)
from .orchestrator import detect_intent, get_agent_system_prompt, build_messages

__all__ = [
    "detect_intent",
    "get_agent_system_prompt",
    "build_messages",
    "COMPLIANCE_AGENT_NAME",
    "ESG_AGENT_NAME",
    "OPERATIONS_AGENT_NAME",
    "FLEET_AGENT_NAME",
    "CLIENT_AGENT_NAME",
    "get_compliance_prompt",
    "get_esg_prompt",
    "get_operations_prompt",
    "get_fleet_prompt",
    "get_client_prompt",
]
