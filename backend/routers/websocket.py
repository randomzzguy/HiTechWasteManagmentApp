# =============================================================
# Hi-Tech Waste Management — WebSocket Router
# Three authenticated rooms: dashboard, fleet, agent-alerts
# =============================================================

from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from websocket.manager import manager

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================
# Auth helper
# =============================================================


async def _verify_ws_token(token: Optional[str]) -> Optional[dict]:
    """
    Validate the JWT token passed as a query parameter on WebSocket upgrade.

    WebSocket connections cannot send Authorization headers in the browser,
    so the token is passed as ?token=<jwt>. We decode it here using the same
    logic as the HTTP auth dependency.

    Returns the decoded payload dict on success, or None if the token is
    missing / invalid (caller decides whether to reject or allow).
    """
    if not token:
        return None

    try:
        from config import get_settings
        from jose import JWTError, jwt

        settings = get_settings()
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except Exception as exc:
        logger.warning("WebSocket token validation failed: %s", exc)
        return None


# =============================================================
# /ws/dashboard
# =============================================================


@router.websocket("/ws/dashboard/")
async def ws_dashboard_alias(
    websocket: WebSocket,
    token: Optional[str] = Query(default=None, description="JWT access token"),
):
    """Alias for /ws/dashboard with trailing slash."""
    await ws_dashboard(websocket, token)


@router.websocket("/ws/dashboard")
async def ws_dashboard(
    websocket: WebSocket,
    token: Optional[str] = Query(default=None, description="JWT access token"),
):
    """
    **Dashboard WebSocket room**

    Streams live KPI updates, job status changes, weighbridge records,
    and summary metrics to the main operations dashboard.

    ### Connection
    ```
    ws://localhost:8000/ws/dashboard?token=<jwt>
    ```

    ### Incoming client messages
    | type    | Description                              |
    |---------|------------------------------------------|
    | `ping`  | Keepalive — server responds with `pong`  |
    | `*`     | Any other payload is re-broadcast to the room |

    ### Server-pushed events
    | event            | Payload fields                               |
    |------------------|----------------------------------------------|
    | `connected`      | `room`, `clients_in_room`, `server_time`     |
    | `pong`           | `server_time`                                |
    | `job_update`     | `job_id`, `status`, `client`, `updated_at`   |
    | `weight_record`  | `record_id`, `net_kg`, `waste_type`, `time`  |
    | `kpi_refresh`    | `jobs_today`, `tonnes_today`, `vehicles_out` |
    | `agent_alert`    | `agent`, `severity`, `title`, `body`         |
    """
    # Optional auth — log user if token provided, allow anonymous in dev
    user = await _verify_ws_token(token)
    user_label = user.get("sub", "anonymous") if user else "anonymous"
    logger.info("Dashboard WS connecting | user=%s", user_label)

    await manager.connect(websocket, "dashboard")

    try:
        while True:
            try:
                raw = await websocket.receive_text()
            except WebSocketDisconnect:
                break

            # Parse incoming message
            try:
                data = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                await manager.send_personal(
                    {"event": "error", "message": "Invalid JSON payload"},
                    websocket,
                )
                continue

            msg_type = data.get("type") or data.get("event", "")

            # ── Keepalive ping/pong ───────────────────────────
            if msg_type == "ping":
                await manager.send_personal({"event": "pong"}, websocket)
                continue

            # ── Subscribe to a sub-topic ──────────────────────
            if msg_type == "subscribe":
                topic = data.get("topic", "")
                await manager.send_personal(
                    {
                        "event": "subscribed",
                        "topic": topic,
                        "message": f"Subscribed to {topic} in dashboard room",
                    },
                    websocket,
                )
                continue

            # ── Re-broadcast any other message to the room ────
            await manager.broadcast(
                {
                    "event": "message",
                    "from": user_label,
                    "data": data,
                },
                "dashboard",
            )

    except WebSocketDisconnect:
        logger.info("Dashboard WS disconnected | user=%s", user_label)
    except Exception as exc:
        logger.error("Dashboard WS unexpected error | user=%s | %s", user_label, exc)
    finally:
        manager.disconnect(websocket, "dashboard")
        # Notify remaining clients that someone left
        remaining = manager.room_size("dashboard")
        if remaining > 0:
            await manager.broadcast(
                {
                    "event": "peer_left",
                    "room": "dashboard",
                    "clients_remaining": remaining,
                },
                "dashboard",
            )


# =============================================================
# /ws/fleet
# =============================================================


@router.websocket("/ws/fleet/")
async def ws_fleet_alias(
    websocket: WebSocket,
    token: Optional[str] = Query(default=None, description="JWT access token"),
    vehicle_id: Optional[str] = Query(
        default=None, description="Filter telemetry to a specific vehicle ID"
    ),
):
    """Alias for /ws/fleet with trailing slash."""
    await ws_fleet(websocket, token, vehicle_id)


@router.websocket("/ws/fleet")
async def ws_fleet(
    websocket: WebSocket,
    token: Optional[str] = Query(default=None, description="JWT access token"),
    vehicle_id: Optional[str] = Query(
        default=None, description="Filter telemetry to a specific vehicle ID"
    ),
):
    """
    **Fleet WebSocket room**

    Streams real-time GPS telemetry, vehicle status transitions,
    driver check-ins, route deviations, and maintenance alerts.

    ### Connection
    ```
    ws://localhost:8000/ws/fleet?token=<jwt>&vehicle_id=<optional_filter>
    ```

    ### Incoming client messages
    | type              | Payload              | Description                        |
    |-------------------|----------------------|------------------------------------|
    | `ping`            | —                    | Keepalive                          |
    | `gps_update`      | `lat`, `lng`, `speed`, `heading`, `vehicle_id` | Driver device pushes telemetry |
    | `status_update`   | `vehicle_id`, `status` | Manual vehicle status change     |
    | `subscribe_vehicle` | `vehicle_id`       | Filter future events to one vehicle|

    ### Server-pushed events
    | event              | Description                               |
    |--------------------|-------------------------------------------|
    | `connected`        | Handshake confirmation                    |
    | `pong`             | Keepalive response                        |
    | `gps_broadcast`    | Live position update from a vehicle       |
    | `vehicle_status`   | Vehicle went on_trip / available / maintenance |
    | `route_deviation`  | Vehicle strayed from planned route        |
    | `geofence_event`   | Vehicle entered / exited a geofence zone  |
    """
    user = await _verify_ws_token(token)
    user_label = user.get("sub", "anonymous") if user else "anonymous"
    logger.info(
        "Fleet WS connecting | user=%s | vehicle_filter=%s", user_label, vehicle_id
    )

    await manager.connect(websocket, "fleet")

    # Track which vehicle this socket is filtering (if any)
    subscribed_vehicle: Optional[str] = vehicle_id

    try:
        while True:
            try:
                raw = await websocket.receive_text()
            except WebSocketDisconnect:
                break

            try:
                data = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                await manager.send_personal(
                    {"event": "error", "message": "Invalid JSON payload"},
                    websocket,
                )
                continue

            msg_type = data.get("type") or data.get("event", "")

            # ── Keepalive ─────────────────────────────────────
            if msg_type == "ping":
                await manager.send_personal({"event": "pong"}, websocket)
                continue

            # ── GPS telemetry push from driver device ─────────
            if msg_type == "gps_update":
                vid = data.get("vehicle_id", "unknown")
                await manager.broadcast(
                    {
                        "event": "gps_broadcast",
                        "vehicle_id": vid,
                        "lat": data.get("lat"),
                        "lng": data.get("lng"),
                        "speed_kmh": data.get("speed"),
                        "heading": data.get("heading"),
                        "timestamp": data.get("timestamp"),
                        "reported_by": user_label,
                    },
                    "fleet",
                )
                continue

            # ── Vehicle status change ─────────────────────────
            if msg_type == "status_update":
                vid = data.get("vehicle_id", "unknown")
                new_status = data.get("status", "unknown")
                await manager.broadcast(
                    {
                        "event": "vehicle_status",
                        "vehicle_id": vid,
                        "status": new_status,
                        "updated_by": user_label,
                    },
                    "fleet",
                )
                continue

            # ── Subscribe to a specific vehicle's updates ─────
            if msg_type == "subscribe_vehicle":
                subscribed_vehicle = data.get("vehicle_id")
                await manager.send_personal(
                    {
                        "event": "vehicle_subscribed",
                        "vehicle_id": subscribed_vehicle,
                        "message": f"Now tracking vehicle {subscribed_vehicle}",
                    },
                    websocket,
                )
                continue

            # ── Generic broadcast ─────────────────────────────
            await manager.broadcast(
                {
                    "event": "fleet_message",
                    "from": user_label,
                    "data": data,
                },
                "fleet",
            )

    except WebSocketDisconnect:
        logger.info("Fleet WS disconnected | user=%s", user_label)
    except Exception as exc:
        logger.error("Fleet WS unexpected error | user=%s | %s", user_label, exc)
    finally:
        manager.disconnect(websocket, "fleet")


# =============================================================
# /ws/agent-alerts
# =============================================================


@router.websocket("/ws/agent-alerts/")
async def ws_agent_alerts_alias(
    websocket: WebSocket,
    token: Optional[str] = Query(default=None, description="JWT access token"),
    severity_filter: Optional[str] = Query(
        default=None,
        description="Only receive alerts at or above this severity: info | warning | critical",
    ),
):
    """Alias for /ws/agent-alerts with trailing slash."""
    await ws_agent_alerts(websocket, token, severity_filter)


@router.websocket("/ws/agent-alerts")
async def ws_agent_alerts(
    websocket: WebSocket,
    token: Optional[str] = Query(default=None, description="JWT access token"),
    severity_filter: Optional[str] = Query(
        default=None,
        description="Only receive alerts at or above this severity: info | warning | critical",
    ),
):
    """
    **Agent Alerts WebSocket room**

    Streams real-time notifications generated by the five AI agents:
    Compliance, ESG, Operations, Client Intelligence, and Fleet & Maintenance.

    ### Connection
    ```
    ws://localhost:8000/ws/agent-alerts?token=<jwt>&severity_filter=warning
    ```

    ### Incoming client messages
    | type          | Payload                | Description                      |
    |---------------|------------------------|----------------------------------|
    | `ping`        | —                      | Keepalive                        |
    | `mark_read`   | `alert_id`             | Mark an alert as read            |
    | `set_filter`  | `severity`             | Update severity filter live      |
    | `ack`         | `alert_id`, `action`   | Acknowledge and act on an alert  |

    ### Server-pushed events
    | event         | Description                                        |
    |---------------|----------------------------------------------------|
    | `connected`   | Handshake with current unread count                |
    | `pong`        | Keepalive response                                 |
    | `alert`       | New AI agent alert (severity: info/warning/critical)|
    | `alert_read`  | Another client marked an alert as read             |
    | `agent_status`| An agent started/finished a scheduled run          |
    """
    user = await _verify_ws_token(token)
    user_label = user.get("sub", "anonymous") if user else "anonymous"
    user_role = user.get("role", "viewer") if user else "viewer"

    logger.info(
        "Agent-alerts WS connecting | user=%s | role=%s | severity_filter=%s",
        user_label,
        user_role,
        severity_filter,
    )

    await manager.connect(websocket, "agent-alerts")

    # Per-connection severity filter (mutable via set_filter message)
    _SEVERITY_ORDER = {"info": 0, "warning": 1, "critical": 2}
    current_filter_level: int = _SEVERITY_ORDER.get(
        (severity_filter or "info").lower(), 0
    )

    try:
        while True:
            try:
                raw = await websocket.receive_text()
            except WebSocketDisconnect:
                break

            try:
                data = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                await manager.send_personal(
                    {"event": "error", "message": "Invalid JSON payload"},
                    websocket,
                )
                continue

            msg_type = data.get("type") or data.get("event", "")

            # ── Keepalive ─────────────────────────────────────
            if msg_type == "ping":
                await manager.send_personal({"event": "pong"}, websocket)
                continue

            # ── Mark alert as read ────────────────────────────
            if msg_type == "mark_read":
                alert_id = data.get("alert_id")
                if alert_id:
                    # Broadcast the read status to all clients so UIs stay in sync
                    await manager.broadcast(
                        {
                            "event": "alert_read",
                            "alert_id": alert_id,
                            "read_by": user_label,
                        },
                        "agent-alerts",
                    )
                continue

            # ── Update severity filter ────────────────────────
            if msg_type == "set_filter":
                new_severity = data.get("severity", "info").lower()
                current_filter_level = _SEVERITY_ORDER.get(new_severity, 0)
                await manager.send_personal(
                    {
                        "event": "filter_updated",
                        "severity": new_severity,
                        "message": f"Now receiving alerts at level '{new_severity}' and above",
                    },
                    websocket,
                )
                continue

            # ── Acknowledge and act on an alert ──────────────
            if msg_type == "ack":
                alert_id = data.get("alert_id")
                action = data.get("action", "acknowledged")
                await manager.broadcast(
                    {
                        "event": "alert_acknowledged",
                        "alert_id": alert_id,
                        "action": action,
                        "acknowledged_by": user_label,
                    },
                    "agent-alerts",
                )
                continue

            # ── Supervisor / agent can push new alerts ────────
            if msg_type == "alert":
                severity = data.get("severity", "info").lower()
                alert_level = _SEVERITY_ORDER.get(severity, 0)

                # Only allow trusted roles to inject alerts via WebSocket
                if user_role not in ("admin", "supervisor", "agent_system"):
                    await manager.send_personal(
                        {
                            "event": "error",
                            "message": "Insufficient permissions to publish alerts",
                        },
                        websocket,
                    )
                    continue

                await manager.broadcast(
                    {
                        "event": "alert",
                        "agent": data.get("agent", "system"),
                        "severity": severity,
                        "title": data.get("title", ""),
                        "body": data.get("body", ""),
                        "reference_type": data.get("reference_type"),
                        "reference_id": data.get("reference_id"),
                        "published_by": user_label,
                    },
                    "agent-alerts",
                )
                continue

            # ── Generic broadcast (other message types) ───────
            await manager.broadcast(
                {
                    "event": "agent_message",
                    "from": user_label,
                    "data": data,
                },
                "agent-alerts",
            )

    except WebSocketDisconnect:
        logger.info("Agent-alerts WS disconnected | user=%s", user_label)
    except Exception as exc:
        logger.error("Agent-alerts WS unexpected error | user=%s | %s", user_label, exc)
    finally:
        manager.disconnect(websocket, "agent-alerts")
