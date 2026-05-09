#!/usr/bin/env python3
"""
Hi-Tech Waste Management — GPS Simulator
=========================================
Simulates real GPS telemetry for fleet vehicles by publishing MQTT messages
to the fleet/gps/<vehicle_id> topic.

The simulator moves vehicles along realistic routes in the Shah Alam /
Petaling Jaya / Klang area (where Hi-Tech Waste Management operates).

Usage:
    # From the project root:
    python scripts/gps_simulator.py

    # With custom broker:
    MQTT_BROKER_HOST=localhost MQTT_BROKER_PORT=1883 python scripts/gps_simulator.py

    # Faster simulation (update every 2 seconds):
    GPS_UPDATE_INTERVAL=2 python scripts/gps_simulator.py

Environment variables:
    MQTT_BROKER_HOST    MQTT broker hostname (default: localhost)
    MQTT_BROKER_PORT    MQTT broker port (default: 1883)
    DATABASE_URL        PostgreSQL DSN (default: localhost:5432)
    GPS_UPDATE_INTERVAL Seconds between position updates (default: 5)
    GPS_SPEED_KMH       Simulated vehicle speed in km/h (default: 40)
"""

from __future__ import annotations

import json
import math
import os
import random
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MQTT_HOST = os.environ.get("MQTT_BROKER_HOST", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_BROKER_PORT", "1883"))
UPDATE_INTERVAL = float(os.environ.get("GPS_UPDATE_INTERVAL", "5"))  # seconds
SPEED_KMH = float(os.environ.get("GPS_SPEED_KMH", "40"))
TOPIC_PREFIX = "fleet/gps"

# ---------------------------------------------------------------------------
# Realistic waypoints in Shah Alam / PJ / Klang area (lat, lng)
# These form circular routes that vehicles travel along.
# ---------------------------------------------------------------------------

ROUTES = {
    "route_shah_alam": [
        (3.0738, 101.5183),  # Shah Alam City Centre
        (3.0850, 101.5300),  # Seksyen 15 Industrial
        (3.0950, 101.5450),  # Seksyen 23 Industrial
        (3.1050, 101.5600),  # Seksyen 27
        (3.1100, 101.5750),  # Bukit Jelutong
        (3.1050, 101.5900),  # Kota Kemuning
        (3.0950, 101.5800),  # Glenmarie
        (3.0850, 101.5650),  # Subang Hi-Tech
        (3.0750, 101.5500),  # Subang Jaya Industrial
        (3.0738, 101.5183),  # Back to start
    ],
    "route_pj_klang": [
        (3.1073, 101.6067),  # Petaling Jaya
        (3.1200, 101.5900),  # Damansara
        (3.1350, 101.5750),  # Ara Damansara
        (3.1200, 101.5600),  # Subang
        (3.1050, 101.5450),  # Shah Alam
        (3.0900, 101.5300),  # Klang North
        (3.0750, 101.5150),  # Klang South
        (3.0600, 101.5000),  # Port Klang
        (3.0750, 101.5150),  # Return
        (3.0900, 101.5300),
        (3.1073, 101.6067),  # Back to PJ
    ],
    "route_kl_pj": [
        (3.1390, 101.6869),  # KL City Centre
        (3.1300, 101.6700),  # Bangsar
        (3.1200, 101.6500),  # Mid Valley
        (3.1100, 101.6300),  # Kerinchi
        (3.1073, 101.6067),  # Petaling Jaya
        (3.1000, 101.5900),  # Kelana Jaya
        (3.0900, 101.5750),  # Subang
        (3.1000, 101.5900),  # Return
        (3.1073, 101.6067),
        (3.1200, 101.6500),
        (3.1390, 101.6869),  # Back to KL
    ],
}

ROUTE_NAMES = list(ROUTES.keys())

# ---------------------------------------------------------------------------
# Vehicle state tracker
# ---------------------------------------------------------------------------

class VehicleState:
    def __init__(self, vehicle_id: str, registration: str, route_name: str, odometer: float):
        self.vehicle_id = vehicle_id
        self.registration = registration
        self.route = ROUTES[route_name]
        self.route_name = route_name
        self.waypoint_idx = random.randint(0, len(self.route) - 2)
        self.progress = random.random()  # 0.0 to 1.0 between waypoints
        self.odometer = odometer
        self.speed = SPEED_KMH + random.uniform(-10, 10)  # slight variation
        self.heading = 0.0

    def advance(self, dt_seconds: float) -> dict[str, Any]:
        """Advance position by dt_seconds and return GPS payload."""
        # Distance covered in this time step (km)
        dist_km = (self.speed / 3600) * dt_seconds

        # Move along route
        while dist_km > 0:
            wp_from = self.route[self.waypoint_idx]
            wp_to = self.route[(self.waypoint_idx + 1) % len(self.route)]

            # Distance between waypoints (Haversine approximation)
            segment_km = _haversine(wp_from, wp_to)
            remaining_in_segment = segment_km * (1 - self.progress)

            if dist_km >= remaining_in_segment:
                # Move to next waypoint
                dist_km -= remaining_in_segment
                self.waypoint_idx = (self.waypoint_idx + 1) % len(self.route)
                self.progress = 0.0
            else:
                # Advance within segment
                self.progress += dist_km / segment_km
                dist_km = 0

        # Interpolate current position
        wp_from = self.route[self.waypoint_idx]
        wp_to = self.route[(self.waypoint_idx + 1) % len(self.route)]
        lat = wp_from[0] + (wp_to[0] - wp_from[0]) * self.progress
        lng = wp_from[1] + (wp_to[1] - wp_from[1]) * self.progress

        # Add small GPS noise (±0.0001 degrees ≈ ±11m)
        lat += random.uniform(-0.0001, 0.0001)
        lng += random.uniform(-0.0001, 0.0001)

        # Calculate heading
        dlat = wp_to[0] - wp_from[0]
        dlng = wp_to[1] - wp_from[1]
        self.heading = math.degrees(math.atan2(dlng, dlat)) % 360

        # Update odometer
        step_km = (self.speed / 3600) * dt_seconds
        self.odometer += step_km

        # Vary speed slightly
        self.speed = max(10, min(80, self.speed + random.uniform(-2, 2)))

        return {
            "vehicle_id": self.vehicle_id,
            "lat": round(lat, 6),
            "lng": round(lng, 6),
            "speed_kmh": round(self.speed, 1),
            "heading": round(self.heading, 1),
            "odometer_km": round(self.odometer, 1),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "gps_device_id": f"GPS-SIM-{self.registration}",
            "source": "simulator",
        }


def _haversine(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    """Return distance in km between two (lat, lng) points."""
    R = 6371.0
    lat1, lon1 = math.radians(p1[0]), math.radians(p1[1])
    lat2, lon2 = math.radians(p2[0]), math.radians(p2[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


# ---------------------------------------------------------------------------
# Database: fetch active vehicles
# ---------------------------------------------------------------------------

def fetch_vehicles() -> list[dict[str, Any]]:
    """Fetch vehicles from the database. Falls back to mock data if DB unavailable."""
    try:
        import psycopg2  # type: ignore

        db_url = os.environ.get(
            "DATABASE_URL",
            "postgresql://hitech:password@localhost:5432/hitech_waste",
        )
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id::text, registration, odometer_km, status
            FROM vehicles
            WHERE status NOT IN ('retired')
            ORDER BY registration
            """
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()

        if rows:
            print(f"  Loaded {len(rows)} vehicles from database")
            return [
                {
                    "id": row[0],
                    "registration": row[1],
                    "odometer_km": float(row[2] or 0),
                    "status": row[3],
                }
                for row in rows
            ]
    except Exception as exc:
        print(f"  DB unavailable ({exc}) — using mock vehicles")

    # Fallback mock vehicles (matches seed data)
    return [
        {"id": str(uuid.uuid4()), "registration": "WXY 1234", "odometer_km": 45230.0, "status": "on_trip"},
        {"id": str(uuid.uuid4()), "registration": "WXY 5678", "odometer_km": 67890.0, "status": "on_trip"},
        {"id": str(uuid.uuid4()), "registration": "WXY 9012", "odometer_km": 23450.0, "status": "available"},
        {"id": str(uuid.uuid4()), "registration": "WXY 3456", "odometer_km": 89120.0, "status": "on_trip"},
        {"id": str(uuid.uuid4()), "registration": "WXY 7890", "odometer_km": 12340.0, "status": "available"},
        {"id": str(uuid.uuid4()), "registration": "WXY 2345", "odometer_km": 34560.0, "status": "on_trip"},
    ]


# ---------------------------------------------------------------------------
# Main simulation loop
# ---------------------------------------------------------------------------

def run_simulator() -> None:
    try:
        import paho.mqtt.client as mqtt  # type: ignore
    except ImportError:
        print("ERROR: paho-mqtt not installed. Run: pip install paho-mqtt")
        sys.exit(1)

    print("=" * 60)
    print("Hi-Tech Waste Management — GPS Simulator")
    print("=" * 60)
    print(f"  MQTT broker:    {MQTT_HOST}:{MQTT_PORT}")
    print(f"  Update interval: {UPDATE_INTERVAL}s")
    print(f"  Simulated speed: {SPEED_KMH} km/h")
    print()

    # Fetch vehicles
    print("Loading vehicles...")
    vehicles = fetch_vehicles()

    # Only simulate vehicles that are on_trip or available (not maintenance/retired)
    active = [v for v in vehicles if v["status"] in ("on_trip", "available")]
    if not active:
        active = vehicles  # simulate all if none are active

    print(f"  Simulating {len(active)} vehicles")
    print()

    # Create vehicle states
    states = []
    for i, v in enumerate(active):
        route_name = ROUTE_NAMES[i % len(ROUTE_NAMES)]
        state = VehicleState(
            vehicle_id=v["id"],
            registration=v["registration"],
            route_name=route_name,
            odometer=v["odometer_km"],
        )
        states.append(state)
        print(f"  {v['registration']:12s} → {route_name}")

    print()

    # Connect to MQTT
    client = mqtt.Client(client_id=f"gps_simulator_{int(time.time())}")

    connected = False

    def on_connect(c, userdata, flags, rc):
        nonlocal connected
        if rc == 0:
            connected = True
            print(f"Connected to MQTT broker at {MQTT_HOST}:{MQTT_PORT}")
        else:
            print(f"MQTT connection failed with code {rc}")

    def on_disconnect(c, userdata, rc):
        nonlocal connected
        connected = False
        if rc != 0:
            print(f"Unexpected MQTT disconnect (rc={rc}) — will retry")

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect

    print(f"Connecting to MQTT broker at {MQTT_HOST}:{MQTT_PORT}...")
    try:
        client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    except Exception as exc:
        print(f"ERROR: Cannot connect to MQTT broker: {exc}")
        print(f"Make sure Mosquitto is running: docker compose up -d mosquitto")
        sys.exit(1)

    client.loop_start()

    # Wait for connection
    for _ in range(10):
        if connected:
            break
        time.sleep(0.5)

    if not connected:
        print("ERROR: Could not connect to MQTT broker within 5 seconds")
        sys.exit(1)

    print(f"\nSimulation running — publishing every {UPDATE_INTERVAL}s")
    print("Press Ctrl+C to stop\n")

    msg_count = 0
    last_time = time.time()

    try:
        while True:
            now = time.time()
            dt = now - last_time
            last_time = now

            for state in states:
                payload = state.advance(dt)
                topic = f"{TOPIC_PREFIX}/{state.vehicle_id}"
                msg = json.dumps(payload)
                result = client.publish(topic, msg, qos=0)

                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    msg_count += 1
                else:
                    print(f"  Publish failed for {state.registration}: rc={result.rc}")

            # Print status every 10 messages per vehicle
            if msg_count % (len(states) * 10) == 0 and msg_count > 0:
                sample = states[0].advance(0)
                print(
                    f"  [{datetime.now().strftime('%H:%M:%S')}] "
                    f"{msg_count} msgs sent | "
                    f"Sample: {states[0].registration} @ "
                    f"{sample['lat']:.4f},{sample['lng']:.4f} "
                    f"{sample['speed_kmh']:.0f}km/h"
                )

            time.sleep(UPDATE_INTERVAL)

    except KeyboardInterrupt:
        print(f"\nSimulator stopped. Total messages sent: {msg_count}")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    run_simulator()
