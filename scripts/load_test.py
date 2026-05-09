#!/usr/bin/env python3
"""
Load testing script for Hi-Tech Waste Management API endpoints.
Uses Locust for distributed load testing.
"""

import asyncio
import random
import time
from typing import Optional

import httpx
from locust import HttpUser, between, events, task
from locust.runners import MasterRunner

# API endpoint configuration
API_BASE_URL = "http://localhost:8000"
API_USERNAME = "admin@hitechwaste.com.my"
API_PASSWORD = "Admin@1234"


class WasteManagementUser(HttpUser):
    """
    Simulates a user interacting with the Hi-Tech Waste Management API.
    """

    # Wait between 1-5 seconds between tasks
    wait_time = between(1, 5)

    def on_start(self):
        """Login and store token for authenticated requests."""
        self.client.post("/api/v1/auth/login", json={
            "username": API_USERNAME,
            "password": API_PASSWORD
        })
        
        # Get token from response
        response = self.client.post("/api/v1/auth/login", json={
            "username": API_USERNAME,
            "password": API_PASSWORD
        })
        
        if response.status_code == 200:
            data = response.json()
            self.token = data.get("access_token")
            self.client.headers.update({
                "Authorization": f"Bearer {self.token}"
            })
        else:
            self.token = None

    @task(3)
    def get_scheduled_waste_batches(self):
        """Fetch scheduled waste batches list."""
        self.client.get("/api/v1/compliance/sw-batches")

    @task(2)
    def get_recyclables_stats(self):
        """Fetch recyclables statistics."""
        self.client.get("/api/v1/recyclables/stats")

    @task(2)
    def get_destruction_jobs(self):
        """Fetch destruction jobs list."""
        self.client.get("/api/v1/destruction/jobs")

    @task(1)
    def get_invoices(self):
        """Fetch invoices list."""
        self.client.get("/api/v1/finance/invoices")

    @task(1)
    def get_clients(self):
        """Fetch clients list."""
        self.client.get("/api/v1/clients")


class QuickTestUser(HttpUser):
    """
    Lightweight user for quick smoke tests.
    """
    wait_time = between(0.5, 2)

    @task
    def health_check(self):
        """Simple health check endpoint."""
        self.client.get("/")


def on_locust_init(environment, runner, **kwargs):
    """
    Initialize Locust environment.
    """
    if isinstance(runner, MasterRunner):
        print("Running in master mode")
    else:
        print("Running in worker/standalone mode")


# Event handlers for custom reporting
@events.init.add_listener
def on_locust_init(environment, **kwargs):
    """Initialize Locust with custom settings."""
    environment.events.hatch.add_listener(on_hatch_complete)


def on_hatch_complete(user_count, **kwargs):
    """Called when all users have been spawned."""
    print(f"All {user_count} users spawned")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("""
Load Testing Script for Hi-Tech Waste Management

Usage:
    # Run with default settings (10 users, spawn rate 1)
    python scripts/load_test.py

    # Run with custom settings
    locust -f scripts/load_test.py --users 50 --spawn-rate 5 --host http://localhost:8000

    # Run headless (without UI)
    locust -f scripts/load_test.py --users 100 --spawn-rate 10 --headless --run-time 2m --host http://localhost:8000

    # Run in distributed mode
    locust -f scripts/load_test.py --master --expect-workers 4 --host http://localhost:8000
    locust -f scripts/load_test.py --worker --master-host <master-ip>

Environment Variables:
    API_BASE_URL: API endpoint URL (default: http://localhost:8000)
    API_USERNAME: Login username (default: admin@hitechwaste.com.my)
    API_PASSWORD: Login password (default: Admin@1234)

Examples:
    # Quick smoke test
    locust -f scripts/load_test.py --users 10 --spawn-rate 2 --headless --run-time 30s --host http://localhost:8000

    # Medium load test
    locust -f scripts/load_test.py --users 100 --spawn-rate 10 --headless --run-time 5m --host http://localhost:8000

    # Heavy load test
    locust -f scripts/load_test.py --users 500 --spawn-rate 50 --headless --run-time 10m --host http://localhost:8000
        """)
        sys.exit(0)
    
    # Default to running Locust
    import subprocess
    subprocess.run([
        "locust",
        "-f", sys.argv[0],
        "--host", API_BASE_URL
    ])
