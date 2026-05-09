# =============================================================
# Hi-Tech Waste Management — Rate Limiting Middleware
# Protects API endpoints from abuse and DDoS attacks
# =============================================================

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from functools import wraps
from typing import Callable, Optional

from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    In-memory rate limiter using sliding window algorithm.
    For production, consider using Redis for distributed rate limiting.
    """

    def __init__(self):
        # Store request timestamps per IP
        self.requests: defaultdict[str, list[datetime]] = defaultdict(list)
        # Clean up old entries periodically
        self._cleanup_task: Optional[asyncio.Task] = None

    async def is_allowed(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
    ) -> bool:
        """Check if request is allowed within rate limits."""
        now = datetime.now()
        window_start = now - timedelta(seconds=window_seconds)

        # Clean up old requests
        self.requests[key] = [
            ts for ts in self.requests[key] if ts > window_start
        ]

        # Check if within limit
        if len(self.requests[key]) >= max_requests:
            return False

        # Record this request
        self.requests[key].append(now)
        return True

    async def cleanup(self):
        """Periodically clean up old entries."""
        while True:
            await asyncio.sleep(300)  # Every 5 minutes
            now = datetime.now()
            window_start = now - timedelta(seconds=3600)  # 1 hour

            for key in list(self.requests.keys()):
                self.requests[key] = [
                    ts for ts in self.requests[key] if ts > window_start
                ]
                if not self.requests[key]:
                    del self.requests[key]

            logger.debug("Rate limiter cleanup completed")


# Global rate limiter instance
rate_limiter = RateLimiter()


def get_client_identifier(request: Request) -> str:
    """
    Get client identifier for rate limiting.
    Uses X-Forwarded-For header if available (behind proxy).
    """
    # Check for forwarded header (behind proxy/load balancer)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # Take the first IP in the chain
        return forwarded.split(",")[0].strip()

    # Fall back to direct client IP
    return request.client.host if request.client else "unknown"


def rate_limit(
    max_requests: int = 100,
    window_seconds: int = 60,
    key_func: Optional[Callable[[Request], str]] = None,
):
    """
    Rate limiting decorator for FastAPI endpoints.

    Args:
        max_requests: Maximum number of requests allowed
        window_seconds: Time window in seconds
        key_func: Optional function to extract rate limit key from request

    Usage:
        @router.get("/endpoint")
        @rate_limit(max_requests=10, window_seconds=60)
        async def endpoint():
            return {"data": "value"}
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            # Get rate limit key
            if key_func:
                key = key_func(request)
            else:
                key = get_client_identifier(request)

            # Check rate limit
            allowed = await rate_limiter.is_allowed(
                key=key,
                max_requests=max_requests,
                window_seconds=window_seconds,
            )

            if not allowed:
                logger.warning(
                    "Rate limit exceeded for key: %s (max: %d/%d sec)",
                    key,
                    max_requests,
                    window_seconds,
                )
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "Rate limit exceeded",
                        "limit": max_requests,
                        "window": window_seconds,
                    },
                )

            return await func(request, *args, **kwargs)

        return wrapper

    return decorator


class RateLimitMiddleware:
    """
    Global rate limiting middleware for all endpoints.
    Can be applied to specific routes or globally.
    """

    def __init__(
        self,
        max_requests: int = 100,
        window_seconds: int = 60,
        exclude_paths: Optional[list[str]] = None,
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.exclude_paths = exclude_paths or ["/health", "/metrics", "/docs"]

    async def __call__(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for excluded paths
        if request.url.path in self.exclude_paths:
            return await call_next(request)

        # Get client identifier
        key = get_client_identifier(request)

        # Check rate limit
        allowed = await rate_limiter.is_allowed(
            key=key,
            max_requests=self.max_requests,
            window_seconds=self.window_seconds,
        )

        if not allowed:
            logger.warning(
                "Rate limit exceeded for path: %s from: %s",
                request.url.path,
                key,
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "limit": self.max_requests,
                    "window": self.window_seconds,
                    "retry_after": self.window_seconds,
                },
            )

        # Add rate limit headers
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.max_requests)
        response.headers["X-RateLimit-Window"] = str(self.window_seconds)

        return response


async def start_rate_limit_cleanup():
    """Start background task for rate limit cleanup."""
    rate_limiter._cleanup_task = asyncio.create_task(rate_limiter.cleanup())
    logger.info("Rate limit cleanup task started")


async def stop_rate_limit_cleanup():
    """Stop background task for rate limit cleanup."""
    if rate_limiter._cleanup_task:
        rate_limiter._cleanup_task.cancel()
        try:
            await rate_limiter._cleanup_task
        except asyncio.CancelledError:
            pass
        logger.info("Rate limit cleanup task stopped")
