#!/usr/bin/env python3
"""
Simple uptime monitoring script for Hi-Tech Waste Management.
Checks if the application is healthy and sends alerts if down.
"""

import argparse
import logging
import smtplib
import time
from datetime import datetime
from email.mime.text import MIMEText
from typing import Optional

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
)
logger = logging.getLogger(__name__)


class UptimeMonitor:
    def __init__(
        self,
        url: str,
        check_interval: int = 60,
        timeout: int = 10,
        email_alerts: bool = False,
        smtp_host: Optional[str] = None,
        smtp_port: int = 587,
        smtp_user: Optional[str] = None,
        smtp_password: Optional[str] = None,
        alert_email: Optional[str] = None,
    ):
        self.url = url
        self.check_interval = check_interval
        self.timeout = timeout
        self.email_alerts = email_alerts
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.alert_email = alert_email
        self.consecutive_failures = 0
        self.max_consecutive_failures = 3

    def check_health(self) -> bool:
        """Check if the application is healthy."""
        try:
            response = requests.get(f"{self.url}/", timeout=self.timeout)
            is_healthy = response.status_code == 200
            logger.info(f"Health check: {response.status_code} - {'OK' if is_healthy else 'FAIL'}")
            return is_healthy
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    def send_alert(self, message: str):
        """Send email alert if configured."""
        if not self.email_alerts or not self.alert_email:
            logger.warning("Email alerts not configured, skipping alert")
            return

        try:
            msg = MIMEText(message)
            msg["Subject"] = f"⚠️ Hi-Tech Waste Management Alert - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            msg["From"] = self.smtp_user
            msg["To"] = self.alert_email

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

            logger.info(f"Alert email sent to {self.alert_email}")
        except Exception as e:
            logger.error(f"Failed to send alert email: {e}")

    def monitor(self):
        """Run continuous monitoring."""
        logger.info(f"Starting uptime monitor for {self.url}")
        logger.info(f"Check interval: {self.check_interval}s, Timeout: {self.timeout}s")
        logger.info(f"Alert threshold: {self.max_consecutive_failures} consecutive failures")

        while True:
            is_healthy = self.check_health()

            if is_healthy:
                if self.consecutive_failures >= self.max_consecutive_failures:
                    # Service recovered
                    self.send_alert(f"✅ Service recovered at {self.url}")
                self.consecutive_failures = 0
            else:
                self.consecutive_failures += 1
                logger.warning(f"Consecutive failures: {self.consecutive_failures}")

                if self.consecutive_failures == self.max_consecutive_failures:
                    # Threshold reached, send alert
                    alert_msg = (
                        f"⚠️ Service DOWN at {self.url}\n"
                        f"Failed {self.consecutive_failures} consecutive health checks.\n"
                        f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    )
                    self.send_alert(alert_msg)

            time.sleep(self.check_interval)


def main():
    parser = argparse.ArgumentParser(description="Uptime monitor for Hi-Tech Waste Management")
    parser.add_argument("--url", default="http://localhost:8000", help="Application URL to monitor")
    parser.add_argument("--interval", type=int, default=60, help="Check interval in seconds")
    parser.add_argument("--timeout", type=int, default=10, help="Request timeout in seconds")
    parser.add_argument("--email-alerts", action="store_true", help="Enable email alerts")
    parser.add_argument("--smtp-host", help="SMTP server host")
    parser.add_argument("--smtp-port", type=int, default=587, help="SMTP server port")
    parser.add_argument("--smtp-user", help="SMTP username")
    parser.add_argument("--smtp-password", help="SMTP password")
    parser.add_argument("--alert-email", help="Email address to send alerts to")

    args = parser.parse_args()

    monitor = UptimeMonitor(
        url=args.url,
        check_interval=args.interval,
        timeout=args.timeout,
        email_alerts=args.email_alerts,
        smtp_host=args.smtp_host,
        smtp_port=args.smtp_port,
        smtp_user=args.smtp_user,
        smtp_password=args.smtp_password,
        alert_email=args.alert_email,
    )

    try:
        monitor.monitor()
    except KeyboardInterrupt:
        logger.info("Monitoring stopped by user")


if __name__ == "__main__":
    main()
