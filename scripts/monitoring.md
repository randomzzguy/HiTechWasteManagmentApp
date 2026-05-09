# Monitoring Setup

This document describes the monitoring setup for Hi-Tech Waste Management application.

## Sentry Error Tracking

### Setup

1. Create a free Sentry account at https://sentry.io
2. Create a new project for your application
3. Copy the DSN (Data Source Name)
4. Add the DSN to your `.env` file:

```bash
SENTRY_DSN=https://your-dsn@sentry.io/project-id
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.1
```

5. Install Sentry SDK (optional - already imported in main.py):

```bash
pip install sentry-sdk[fastapi]
```

### Features

- **Error Tracking**: Automatically captures unhandled exceptions
- **Performance Monitoring**: Tracks API response times
- **Release Tracking**: Associate errors with specific deployments
- **User Context**: Track which users encountered errors

### Configuration

- `SENTRY_DSN`: Your Sentry project DSN (required)
- `SENTRY_ENVIRONMENT`: Environment name (development/staging/production)
- `SENTRY_TRACES_SAMPLE_RATE`: Fraction of transactions to sample (0.0-1.0)

### Testing Sentry

```python
# Test Sentry integration
from sentry_sdk import capture_message

capture_message("Test message from Hi-Tech Waste Management")
```

## Uptime Monitoring

### Running the Uptime Monitor

```bash
# Basic monitoring (no email alerts)
python scripts/uptime_monitor.py --url http://localhost:8000

# With email alerts
python scripts/uptime_monitor.py \
  --url https://your-domain.com \
  --email-alerts \
  --smtp-host smtp.gmail.com \
  --smtp-port 587 \
  --smtp-user your-email@gmail.com \
  --smtp-password your-app-password \
  --alert-email admin@hitechwaste.com.my
```

### Configuration

- `--url`: Application URL to monitor
- `--interval`: Check interval in seconds (default: 60)
- `--timeout`: Request timeout in seconds (default: 10)
- `--email-alerts`: Enable email alerts
- `--smtp-host`: SMTP server host
- `--smtp-port`: SMTP server port (default: 587)
- `--smtp-user`: SMTP username
- `--smtp-password`: SMTP password (use app-specific password for Gmail)
- `--alert-email`: Email address to send alerts to

### Alert Logic

- Sends alert after 3 consecutive failed health checks
- Sends recovery alert when service comes back up
- Logs all health checks

### Running as a Service

#### Using systemd (Linux)

```bash
# Create service file
sudo nano /etc/systemd/system/hitech-uptime.service
```

```ini
[Unit]
Description=Hi-Tech Waste Management Uptime Monitor
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/HiTechWasteManagmentApp
ExecStart=/usr/bin/python3 /path/to/HiTechWasteManagmentApp/scripts/uptime_monitor.py \
  --url https://your-domain.com \
  --interval 60 \
  --email-alerts \
  --smtp-host smtp.gmail.com \
  --smtp-port 587 \
  --smtp-user your-email@gmail.com \
  --smtp-password your-app-password \
  --alert-email admin@hitechwaste.com.my
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start service
sudo systemctl enable hitech-uptime
sudo systemctl start hitech-uptime
sudo systemctl status hitech-uptime
```

#### Using Docker

```bash
# Add to docker-compose.yml
uptime-monitor:
  image: python:3.11-slim
  container_name: hitech_uptime_monitor
  restart: unless-stopped
  command: >
    sh -c "pip install requests &&
           python /scripts/uptime_monitor.py
           --url http://backend:8000
           --interval 60"
  volumes:
    - ./scripts:/scripts
  depends_on:
    - backend
```

## Health Check Endpoint

The application includes a health check endpoint at `/` that returns 200 when healthy.

### Manual Health Check

```bash
curl http://localhost:8000/
```

### Monitoring Services

You can also use external monitoring services:
- **UptimeRobot** (free): https://uptimerobot.com
- **Pingdom** (free tier available): https://pingdom.com
- **Better Uptime** (free): https://betteruptime.com

## Log Monitoring

### Application Logs

```bash
# View backend logs
docker logs hitech_backend -f

# View frontend logs
docker logs hitech_frontend -f

# View all logs
docker compose logs -f
```

### Log Aggregation

For production, consider:
- **Loki + Grafana** (free, self-hosted)
- **ELK Stack** (Elasticsearch, Logstash, Kibana)
- **CloudWatch** (AWS)
- **Logtail** (free tier)

## Metrics and Dashboards

### Recommended Metrics

- Application response times
- Error rates by endpoint
- Database query performance
- Redis cache hit rate
- Memory and CPU usage
- Request rate (RPS)

### Grafana Dashboard Setup

1. Install Prometheus for metrics collection
2. Install Grafana for visualization
3. Import FastAPI metrics dashboard
4. Set up alerts for critical metrics

## Alert Best Practices

1. **Don't alert on every error**: Set thresholds to avoid alert fatigue
2. **Group related alerts**: Use Sentry's issue grouping
3. **Include context**: Add user ID, request ID, and environment to alerts
4. **Test alerts**: Verify alert delivery before going live
5. **Document on-call procedures**: Know who to contact and what to do

## Troubleshooting

### Sentry not capturing errors

1. Check SENTRY_DSN is set correctly
2. Verify sentry-sdk is installed
3. Check application logs for Sentry initialization messages
4. Test with `capture_message()`

### Uptime monitor false positives

1. Increase timeout value for slow networks
2. Increase consecutive failure threshold
3. Check if health check endpoint is working
4. Verify network connectivity to application

### Email alerts not sending

1. Verify SMTP credentials
2. Check if SMTP port is blocked (try 465 for SSL)
3. Use app-specific password for Gmail
4. Check spam folder for test alerts
