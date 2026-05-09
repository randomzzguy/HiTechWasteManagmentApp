# GPS Simulator

Simulates real GPS telemetry for Hi-Tech fleet vehicles by publishing MQTT messages to the `fleet/gps/<vehicle_id>` topic. The backend MQTT gateway picks these up and broadcasts them to the Fleet page via WebSocket.

## How it works

- Loads active vehicles from the database (falls back to mock data if DB unavailable)
- Moves each vehicle along realistic routes in the Shah Alam / Petaling Jaya / Klang area
- Publishes JSON GPS payloads every 5 seconds (configurable)
- The Fleet page map updates in real time as positions arrive

## Quick start

### Option 1: Docker (recommended)

```bash
# Start the simulator alongside the main stack
docker compose --profile simulator up -d gps-simulator

# Watch the logs
docker compose logs -f gps-simulator

# Stop the simulator
docker compose stop gps-simulator
```

### Option 2: Run locally

```bash
# Install dependencies
pip install paho-mqtt psycopg2-binary

# Run (from project root)
python scripts/gps_simulator.py
```

## Configuration

| Variable | Default | Description |
|---|---|---|
| `MQTT_BROKER_HOST` | `localhost` | MQTT broker hostname |
| `MQTT_BROKER_PORT` | `1883` | MQTT broker port |
| `DATABASE_URL` | `postgresql://hitech:password@localhost:5432/hitech_waste` | PostgreSQL DSN |
| `GPS_UPDATE_INTERVAL` | `5` | Seconds between position updates |
| `GPS_SPEED_KMH` | `40` | Simulated vehicle speed |

## MQTT payload format

```json
{
  "vehicle_id": "uuid",
  "lat": 3.1073,
  "lng": 101.6067,
  "speed_kmh": 42.3,
  "heading": 270.0,
  "odometer_km": 45231.5,
  "timestamp": "2025-04-22T08:00:00Z",
  "gps_device_id": "GPS-SIM-WXY 1234",
  "source": "simulator"
}
```

## Connecting real GPS devices

When real GPS hardware is available, configure each device to publish to:
```
mqtt://<broker_host>:1883/fleet/gps/<vehicle_uuid>
```

The payload format is the same as above. The `vehicle_uuid` must match the vehicle's `id` in the database (visible in the Fleet page URL when clicking a vehicle).

## Routes simulated

Vehicles are assigned to one of three circular routes:
- **Shah Alam loop** — Shah Alam City Centre → Seksyen 15/23/27 → Bukit Jelutong → Kota Kemuning → Glenmarie → back
- **PJ–Klang loop** — Petaling Jaya → Damansara → Subang → Shah Alam → Klang → Port Klang → back
- **KL–PJ loop** — KL City Centre → Bangsar → Mid Valley → Petaling Jaya → Kelana Jaya → back
