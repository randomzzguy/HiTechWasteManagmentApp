# =============================================================
# Hi-Tech Waste Management — WebSocket Connection Manager
# Room-based connection management with broadcast & personal send
# =============================================================

from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

# Valid room names — extend as new real-time features are added
VALID_ROOMS: set[str] = {
    "dashboard",
    "fleet",
    "agent-alerts",
}


class ConnectionManager:
    """
    Manages WebSocket connections grouped into named rooms.

    Each room is an independent broadcast channel. A single client
    can join multiple rooms simultaneously. The manager is designed
    to be instantiated once at module level and shared across all
    router handlers via the ``manager`` singleton exported at the
    bottom of this file.

    Rooms
    -----
    - ``dashboard``    : Live KPI tiles, job status updates, weight records
    - ``fleet``        : GPS telemetry, vehicle status changes, route updates
    - ``agent-alerts`` : AI agent notifications, compliance warnings, critical alerts

    Thread safety
    -------------
    FastAPI runs in a single asyncio event loop; all WebSocket operations
    are coroutines. No additional locking is required for the in-memory
    connection dict as long as all mutations happen within the same loop.
    """

    def __init__(self) -> None:
        # Map of room_name -> list of active WebSocket connections
        self.active_connections: dict[str, list[WebSocket]] = defaultdict(list)

        # Map of websocket -> set of rooms it has joined (for cleanup)
        self._socket_rooms: dict[int, set[str]] = defaultdict(set)

        # Connection counter for metrics / debugging
        self._total_connections: int = 0
        self._total_messages_sent: int = 0

    # ----------------------------------------------------------
    # Connection lifecycle
    # ----------------------------------------------------------

    async def connect(self, websocket: WebSocket, room: str) -> None:
        """
        Accept a new WebSocket connection and register it in the given room.

        Parameters
        ----------
        websocket : WebSocket
            The incoming FastAPI WebSocket instance.
        room : str
            The room name to join. Will be created if it does not exist.
        """
        await websocket.accept()

        if room not in VALID_ROOMS:
            logger.warning(
                "Client joined unknown room '%s'. Allowing but consider adding it "
                "to VALID_ROOMS.",
                room,
            )

        self.active_connections[room].append(websocket)
        self._socket_rooms[id(websocket)].add(room)
        self._total_connections += 1

        room_size = len(self.active_connections[room])
        logger.info(
            "WebSocket connected | room='%s' | clients_in_room=%d | total_ever=%d",
            room,
            room_size,
            self._total_connections,
        )

        # Send a welcome frame so the client knows it is fully connected
        await self.send_personal(
            {
                "event": "connected",
                "room": room,
                "clients_in_room": room_size,
                "server_time": _utcnow(),
            },
            websocket,
        )

    def disconnect(self, websocket: WebSocket, room: str) -> None:
        """
        Remove a WebSocket connection from the specified room.

        Safe to call even if the connection is no longer present in the
        room list (e.g. after a duplicate disconnect call).

        Parameters
        ----------
        websocket : WebSocket
            The WebSocket instance to remove.
        room : str
            The room to leave.
        """
        room_connections = self.active_connections.get(room, [])
        if websocket in room_connections:
            room_connections.remove(websocket)
            logger.info(
                "WebSocket disconnected | room='%s' | clients_remaining=%d",
                room,
                len(room_connections),
            )

        # Clean up the reverse mapping
        socket_key = id(websocket)
        if socket_key in self._socket_rooms:
            self._socket_rooms[socket_key].discard(room)
            if not self._socket_rooms[socket_key]:
                del self._socket_rooms[socket_key]

        # Remove empty room entries to keep memory clean
        if room in self.active_connections and not self.active_connections[room]:
            del self.active_connections[room]

    def disconnect_all_rooms(self, websocket: WebSocket) -> None:
        """
        Remove a WebSocket from every room it has joined.

        Useful in a single ``finally`` block when the client disconnects
        without specifying which room it is leaving.
        """
        socket_key = id(websocket)
        rooms = list(self._socket_rooms.get(socket_key, set()))
        for room in rooms:
            self.disconnect(websocket, room)

    # ----------------------------------------------------------
    # Sending messages
    # ----------------------------------------------------------

    async def broadcast(self, message: dict[str, Any], room: str) -> None:
        """
        Send a JSON message to **all** connected clients in a room.

        Dead connections are silently removed during the broadcast sweep
        so the room list stays clean without a separate reaper task.

        Parameters
        ----------
        message : dict
            The payload to broadcast. Will be serialised to JSON.
        room : str
            Target room name.
        """
        connections = self.active_connections.get(room, [])
        if not connections:
            logger.debug("broadcast: room='%s' has no subscribers, skipping.", room)
            return

        # Enrich the message with metadata before sending
        enriched = _enrich(message, room=room)
        payload = json.dumps(enriched, default=str)

        dead: list[WebSocket] = []

        for connection in list(connections):
            try:
                await connection.send_text(payload)
                self._total_messages_sent += 1
            except (WebSocketDisconnect, RuntimeError) as exc:
                logger.warning(
                    "broadcast: stale connection removed from room='%s' (%s)",
                    room,
                    exc,
                )
                dead.append(connection)
            except Exception as exc:
                logger.error(
                    "broadcast: unexpected error sending to room='%s': %s",
                    room,
                    exc,
                )
                dead.append(connection)

        # Prune dead connections discovered during broadcast
        for ws in dead:
            self.disconnect(ws, room)

    async def broadcast_to_all_rooms(self, message: dict[str, Any]) -> None:
        """
        Broadcast a message to every active room simultaneously.

        Useful for system-wide announcements (e.g. scheduled maintenance).
        """
        tasks = [
            self.broadcast(message, room)
            for room in list(self.active_connections.keys())
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def send_personal(
        self, message: dict[str, Any], websocket: WebSocket
    ) -> None:
        """
        Send a JSON message to a **single** WebSocket client.

        Parameters
        ----------
        message : dict
            The payload to send. Will be serialised to JSON.
        websocket : WebSocket
            The target connection.
        """
        enriched = _enrich(message)
        try:
            await websocket.send_text(json.dumps(enriched, default=str))
            self._total_messages_sent += 1
        except (WebSocketDisconnect, RuntimeError) as exc:
            logger.warning("send_personal: connection already closed — %s", exc)
        except Exception as exc:
            logger.error("send_personal: unexpected error — %s", exc)

    async def send_json_personal(
        self, data: dict[str, Any], websocket: WebSocket
    ) -> None:
        """Alias for ``send_personal`` — mirrors FastAPI's WebSocket.send_json API."""
        await self.send_personal(data, websocket)

    # ----------------------------------------------------------
    # Room-specific broadcast helpers (semantic wrappers)
    # ----------------------------------------------------------

    async def broadcast_dashboard(self, message: dict[str, Any]) -> None:
        """Broadcast a live update to the dashboard room."""
        await self.broadcast(message, "dashboard")

    async def broadcast_fleet(self, message: dict[str, Any]) -> None:
        """Broadcast a fleet / GPS update to the fleet room."""
        await self.broadcast(message, "fleet")

    async def broadcast_agent_alert(self, message: dict[str, Any]) -> None:
        """Broadcast an AI agent alert to the agent-alerts room."""
        await self.broadcast(message, "agent-alerts")

    # ----------------------------------------------------------
    # Introspection helpers
    # ----------------------------------------------------------

    def room_size(self, room: str) -> int:
        """Return the number of active connections in a room."""
        return len(self.active_connections.get(room, []))

    def total_connections(self) -> int:
        """Return the total number of currently active connections across all rooms."""
        return sum(len(v) for v in self.active_connections.values())

    def stats(self) -> dict[str, Any]:
        """
        Return a snapshot of connection statistics.

        Used by the ``/health`` endpoint and admin dashboards.
        """
        return {
            "rooms": {
                room: len(conns) for room, conns in self.active_connections.items()
            },
            "total_active_connections": self.total_connections(),
            "total_connections_ever": self._total_connections,
            "total_messages_sent": self._total_messages_sent,
            "valid_rooms": list(VALID_ROOMS),
        }


# =============================================================
# Private helpers
# =============================================================


def _utcnow() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(tz=timezone.utc).isoformat()


def _enrich(message: dict[str, Any], *, room: str | None = None) -> dict[str, Any]:
    """
    Inject standard envelope fields into every outgoing message.

    Adds ``server_time`` if not already present so clients can measure
    latency, and optionally adds the ``room`` the message was sent to.
    """
    enriched = dict(message)
    enriched.setdefault("server_time", _utcnow())
    if room is not None:
        enriched.setdefault("room", room)
    return enriched


# =============================================================
# Module-level singleton
# Import this instance in all router files.
#
#   from websocket.manager import manager
# =============================================================

manager = ConnectionManager()
