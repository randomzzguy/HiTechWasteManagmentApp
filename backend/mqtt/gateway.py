# =============================================================
# Hi-Tech Waste Management — MQTT Gateway
# Subscribes to fleet/gps/# and bridges to WebSocket room
# =============================================================

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


async def start_mqtt_gateway() -> None:
    """
    Start the MQTT gateway that subscribes to GPS telemetry topics
    and broadcasts updates to the 'fleet' WebSocket room.

    Topic pattern: fleet/gps/<vehicle_id>
    Expected payload (JSON):
    {
        "vehicle_id": "uuid",
        "lat": 3.1390,
        "lng": 101.6869,
        "speed_kmh": 45.2,
        "heading": 270,
        "timestamp": "2025-01-01T08:00:00Z",
        "odometer_km": 98234.5
    }

    This coroutine runs indefinitely and should be started as a
    background task in the FastAPI lifespan context.
    """
    try:
        import aiomqtt  # type: ignore[import]
        from config import get_settings
        from websocket.manager import manager as ws_manager

        settings = get_settings()

        logger.info(
            "MQTT gateway starting | broker=%s:%d | topic=%s",
            settings.MQTT_BROKER_HOST,
            settings.MQTT_BROKER_PORT,
            settings.MQTT_TOPIC_GPS,
        )

        reconnect_delay = 5  # seconds

        while True:
            try:
                async with aiomqtt.Client(
                    hostname=settings.MQTT_BROKER_HOST,
                    port=settings.MQTT_BROKER_PORT,
                    client_id="hitech_backend_gateway",
                    keepalive=60,
                ) as client:
                    logger.info("MQTT gateway connected to broker")

                    await client.subscribe(settings.MQTT_TOPIC_GPS)
                    logger.info("MQTT subscribed to topic: %s", settings.MQTT_TOPIC_GPS)

                    async with client.messages() as messages:
                        async for message in messages:
                            await _handle_gps_message(
                                topic=str(message.topic),
                                payload=message.payload,
                                ws_manager=ws_manager,
                            )

            except aiomqtt.MqttError as exc:
                logger.warning(
                    "MQTT connection lost: %s — reconnecting in %ds",
                    exc,
                    reconnect_delay,
                )
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, 60)  # exponential backoff

            except asyncio.CancelledError:
                logger.info("MQTT gateway task cancelled — shutting down")
                break

            except Exception as exc:
                logger.error("MQTT gateway unexpected error: %s", exc, exc_info=True)
                await asyncio.sleep(reconnect_delay)

    except ImportError:
        logger.warning(
            "aiomqtt not available — MQTT gateway disabled. "
            "Install aiomqtt to enable real-time GPS telemetry."
        )


async def _handle_gps_message(
    topic: str,
    payload: bytes,
    ws_manager: Any,
) -> None:
    """
    Process a single GPS MQTT message and broadcast to the fleet WebSocket room.

    Args:
        topic:      MQTT topic string (e.g. fleet/gps/vehicle-uuid)
        payload:    Raw message bytes
        ws_manager: WebSocket ConnectionManager instance
    """
    try:
        # Parse JSON payload
        data: dict[str, Any] = json.loads(payload.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.warning("MQTT: invalid JSON payload on topic %s: %s", topic, exc)
        return

    # Extract vehicle_id from topic or payload
    vehicle_id = data.get("vehicle_id")
    if not vehicle_id:
        # Try to extract from topic: fleet/gps/<vehicle_id>
        parts = topic.split("/")
        if len(parts) >= 3:
            vehicle_id = parts[2]

    if not vehicle_id:
        logger.debug("MQTT: GPS message missing vehicle_id on topic %s", topic)
        return

    # Build WebSocket broadcast payload
    ws_payload = {
        "event": "gps_update",
        "vehicle_id": vehicle_id,
        "lat": data.get("lat"),
        "lng": data.get("lng"),
        "speed_kmh": data.get("speed_kmh") or data.get("speed"),
        "heading": data.get("heading"),
        "timestamp": data.get("timestamp"),
        "odometer_km": data.get("odometer_km"),
        "source": "mqtt",
    }

    # Broadcast to fleet WebSocket room
    await ws_manager.broadcast_fleet(ws_payload)

    # Optionally update vehicle status in DB if speed indicates movement
    speed = data.get("speed_kmh") or data.get("speed", 0)
    if speed and float(speed) > 5:
        await _update_vehicle_gps_status(vehicle_id, data)

    logger.debug(
        "MQTT GPS | vehicle=%s | lat=%.4f | lng=%.4f | speed=%.1f km/h",
        vehicle_id,
        data.get("lat", 0),
        data.get("lng", 0),
        float(speed or 0),
    )


async def _update_vehicle_gps_status(
    vehicle_id: str,
    gps_data: dict[str, Any],
) -> None:
    """
    Update the vehicle's odometer in the database from GPS data.
    Non-fatal — errors are logged and swallowed.
    """
    try:
        import uuid
        from database import get_async_session
        from models.vehicle import Vehicle
        from sqlalchemy import select

        odometer = gps_data.get("odometer_km")
        if not odometer:
            return

        async with get_async_session() as session:
            result = await session.execute(
                select(Vehicle).where(Vehicle.id == uuid.UUID(vehicle_id))
            )
            vehicle = result.scalar_one_or_none()
            if vehicle and (
                vehicle.odometer_km is None
                or float(odometer) > float(vehicle.odometer_km)
            ):
                vehicle.odometer_km = odometer
                await session.commit()

    except Exception as exc:
        logger.debug("MQTT: could not update vehicle odometer: %s", exc)
