# =============================================================
# Hi-Tech Waste Management — Routers Package
# Exposes all API router modules for import in main.py
# =============================================================

from . import (
    ai,
    auth,
    bsf,
    clients,
    compliance,
    destruction,
    esg,
    finance,
    fleet,
    jobs,
    recyclables,
    reports,
    websocket,
    weighbridge,
)

__all__ = [
    "ai",
    "auth",
    "bsf",
    "clients",
    "compliance",
    "destruction",
    "esg",
    "finance",
    "fleet",
    "jobs",
    "recyclables",
    "reports",
    "weighbridge",
    "websocket",
]
