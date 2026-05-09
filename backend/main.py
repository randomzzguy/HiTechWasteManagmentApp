# =============================================================
# Hi-Tech Waste Management — FastAPI Application Entry Point
# =============================================================

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import Any

from config import get_settings
from database import check_database_connection, close_db_connections, create_all_tables
from cache import cache
from rate_limit import RateLimitMiddleware, start_rate_limit_cleanup, stop_rate_limit_cleanup
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Sentry error tracking (optional)
try:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    SENTRY_AVAILABLE = True
except ImportError:
    SENTRY_AVAILABLE = False

# ── Router imports ────────────────────────────────────────────
from routers import (
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
    settings as settings_router,
    weighbridge,
)
from routers import websocket as ws_router
from routers import equipment, labour, disruptions, recycler_deliveries, operational_field

logger = logging.getLogger(__name__)
settings = get_settings()


# =============================================================
# Lifespan — startup / shutdown logic
# =============================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages the full lifecycle of the FastAPI application.

    Startup:
      - Configure logging
      - Verify database connectivity
      - Create/verify ORM tables (dev convenience; use Alembic in production)
      - Log registered routes

    Shutdown:
      - Close all database connection pools gracefully
    """
    # ── Startup ───────────────────────────────────────────────
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    logger.info("=" * 60)
    logger.info("Starting %s v%s", settings.APP_TITLE, settings.APP_VERSION)
    logger.info("Environment : %s", settings.APP_ENV)
    logger.info("=" * 60)

    # Initialize Sentry if DSN is provided
    if SENTRY_AVAILABLE and settings.SENTRY_DSN:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.SENTRY_ENVIRONMENT,
            traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
            integrations=[
                FastApiIntegration(),
                SqlalchemyIntegration(),
            ],
        )
        logger.info("Sentry error tracking enabled")
    elif not settings.SENTRY_DSN:
        logger.info("Sentry error tracking disabled (no DSN configured)")
    else:
        logger.warning("Sentry SDK not installed. Install with: pip install sentry-sdk[fastapi]")

    # Initialize Redis cache connection
    await cache.connect()
    if cache._client:
        logger.info("Redis cache connected")
    else:
        logger.warning("Redis cache connection failed - caching will be disabled")

    # Start rate limit cleanup task
    if settings.RATE_LIMIT_ENABLED:
        await start_rate_limit_cleanup()
        logger.info("Rate limiting enabled")
    else:
        logger.info("Rate limiting disabled")

    # Verify database connectivity before accepting requests
    db_ok = await check_database_connection()
    if db_ok:
        logger.info("Database connection: OK")
    else:
        logger.critical(
            "Database connection FAILED. Check DATABASE_URL and ensure "
            "PostgreSQL is reachable before sending traffic."
        )

    # Create tables in development only — use Alembic migrations in production
    if settings.is_development:
        try:
            await create_all_tables()
            logger.info("ORM table sync: OK (dev mode)")
        except Exception as exc:
            logger.error("ORM table sync failed: %s", exc)
    else:
        logger.info("Production mode — skipping create_all_tables() (use Alembic)")

    logger.info("Application ready — listening on port 8000")

    # Start MQTT gateway as a background task (non-fatal if broker unavailable)
    import asyncio
    from mqtt.gateway import start_mqtt_gateway

    mqtt_task = asyncio.create_task(start_mqtt_gateway())
    logger.info("MQTT gateway task started")

    yield  # ── Application runs here ───────────────────────────

    # Cancel MQTT gateway on shutdown
    mqtt_task.cancel()
    try:
        await mqtt_task
    except asyncio.CancelledError:
        pass

    # ── Shutdown ──────────────────────────────────────────────
    logger.info("Shutting down %s …", settings.APP_TITLE)
    await close_db_connections()
    await cache.disconnect()
    await stop_rate_limit_cleanup()
    logger.info("Database connections closed. Goodbye.")


# =============================================================
# FastAPI Application Instance
# =============================================================

app = FastAPI(
    title=settings.APP_TITLE,
    version=settings.APP_VERSION,
    description=(
        "AI-integrated waste management operations platform for Hi-Tech "
        "Waste Management Sdn. Bhd. Provides REST + WebSocket APIs for "
        "client management, job scheduling, fleet telematics, weighbridge "
        "tracking, scheduled-waste compliance, recyclables traceability, "
        "witnessed destruction, BSF farm operations, ESG reporting, "
        "invoicing, and multi-agent AI intelligence."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
    redirect_slashes=False,  # Disable auto-redirect to prevent CORS issues
)


# =============================================================
# Middleware
# =============================================================

# ── Trailing slash normalization ─────────────────────────────
# Strip trailing slashes before routing to prevent 404s
@app.middleware("http")
async def strip_trailing_slashes(request: Request, call_next):
    """Removes trailing slashes from request paths to ensure routes match."""
    if request.url.path != "/" and request.url.path.endswith("/"):
        from starlette.requests import Request as StarletteRequest
        # Create new scope without trailing slash
        scope = request.scope.copy()
        path = request.url.path.rstrip("/")
        scope["path"] = path
        # Also update raw_path
        raw_path = scope.get("raw_path", b"")
        if raw_path.endswith(b"/"):
            scope["raw_path"] = raw_path.rstrip(b"/")
        request = StarletteRequest(scope, receive=request.receive)
    return await call_next(request)


# ── Rate limiting middleware ─────────────────────────────────
if settings.RATE_LIMIT_ENABLED:
    exclude_paths = settings.RATE_LIMIT_EXCLUDE_PATHS.split(",")
    rate_limit_middleware = RateLimitMiddleware(
        max_requests=settings.RATE_LIMIT_MAX_REQUESTS,
        window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS,
        exclude_paths=exclude_paths,
    )
    app.middleware("http")(rate_limit_middleware)


# ── CORS ─────────────────────────────────────────────────────
# In production, set ALLOWED_ORIGINS to your actual frontend domain(s).
# Example: ALLOWED_ORIGINS=https://app.hitechwaste.com.my,https://admin.hitechwaste.com.my
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Process-Time"],
)


# ── Cache-busting middleware for dashboard APIs ─────────────────
@app.middleware("http")
async def add_cache_busting_headers(request: Request, call_next):
    """Adds cache-busting headers to dashboard API responses to prevent stale data."""
    response = await call_next(request)
    
    # Add cache-busting headers for dashboard/widget API endpoints
    path = request.url.path
    if path.startswith("/api/v1/") and (
        "/status-counts" in path
        or "/stats" in path
        or "/summary" in path
        or "/jobs" in path
        or "/dashboard" in path
    ):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        response.headers["X-Data-Timestamp"] = str(time.time())
    
    return response


# ── Request timing middleware ─────────────────────────────────
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Attaches X-Process-Time header (milliseconds) to every response."""
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Process-Time"] = f"{elapsed_ms:.2f}ms"
    return response


# ── Request ID middleware ─────────────────────────────────────
@app.middleware("http")
async def attach_request_id(request: Request, call_next):
    """Generates and propagates a unique request ID for tracing."""
    import uuid

    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# =============================================================
# Exception Handlers
# =============================================================


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """
    Converts FastAPI HTTPException into a consistent JSON error envelope:
    { "error": { "code": <int>, "message": <str>, "detail": <any> } }
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.status_code,
                "message": _status_message(exc.status_code),
                "detail": exc.detail,
            }
        },
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """
    Returns a 422 JSON response with structured field-level validation errors.
    Each error includes the field location, type, and human-readable message.
    """
    errors = []
    for err in exc.errors():
        errors.append(
            {
                "field": " → ".join(str(loc) for loc in err["loc"]),
                "type": err["type"],
                "message": err["msg"],
            }
        )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": 422,
                "message": "Validation failed",
                "detail": errors,
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catches any unhandled exception and returns a generic 500 response.
    Full traceback is logged server-side but never exposed to the client.
    """
    logger.exception(
        "Unhandled exception on %s %s: %s",
        request.method,
        request.url.path,
        exc,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": 500,
                "message": "Internal server error",
                "detail": "An unexpected error occurred. Please try again later.",
            }
        },
    )


def _status_message(code: int) -> str:
    """Maps HTTP status codes to human-readable messages."""
    return {
        400: "Bad request",
        401: "Unauthorised",
        403: "Forbidden",
        404: "Not found",
        405: "Method not allowed",
        409: "Conflict",
        410: "Gone",
        422: "Unprocessable entity",
        429: "Too many requests",
        500: "Internal server error",
        502: "Bad gateway",
        503: "Service unavailable",
    }.get(code, "Error")


# =============================================================
# API Routers — /api/v1
# =============================================================

API_PREFIX = "/api/v1"

app.include_router(auth.router, prefix=f"{API_PREFIX}/auth", tags=["Authentication"])
app.include_router(clients.router, prefix=f"{API_PREFIX}/clients", tags=["Clients"])
app.include_router(jobs.router, prefix=f"{API_PREFIX}/jobs", tags=["Jobs"])
app.include_router(fleet.router, prefix=f"{API_PREFIX}/fleet", tags=["Fleet"])
app.include_router(
    weighbridge.router, prefix=f"{API_PREFIX}/weighbridge", tags=["Weighbridge"]
)
app.include_router(
    compliance.router, prefix=f"{API_PREFIX}/compliance", tags=["Compliance"]
)
app.include_router(
    recyclables.router, prefix=f"{API_PREFIX}/recyclables", tags=["Recyclables"]
)
app.include_router(
    destruction.router, prefix=f"{API_PREFIX}/destruction", tags=["Destruction"]
)
app.include_router(bsf.router, prefix=f"{API_PREFIX}/bsf", tags=["BSF Farm"])
app.include_router(esg.router, prefix=f"{API_PREFIX}/esg", tags=["ESG & Carbon"])
app.include_router(finance.router, prefix=f"{API_PREFIX}/finance", tags=["Finance"])
app.include_router(reports.router, prefix=f"{API_PREFIX}/reports", tags=["Reports"])
app.include_router(ai.router, prefix=f"{API_PREFIX}/ai", tags=["AI Agents"])
app.include_router(settings_router.router, prefix=f"{API_PREFIX}/settings", tags=["Settings"])

# ── Operational Field Management ──────────────────────────────
app.include_router(
    equipment.router, prefix=f"{API_PREFIX}/equipment", tags=["Equipment"]
)
app.include_router(
    labour.router, prefix=f"{API_PREFIX}/labour", tags=["Labour"]
)
app.include_router(
    disruptions.router, prefix=f"{API_PREFIX}/disruptions", tags=["Disruptions"]
)
app.include_router(
    recycler_deliveries.router,
    prefix=f"{API_PREFIX}/recycler-deliveries",
    tags=["Recycler Deliveries"],
)
app.include_router(
    operational_field.router,
    prefix=f"{API_PREFIX}/operational-field",
    tags=["Operational Field"],
)

# ── WebSocket router (no /api/v1 prefix — raw /ws/* paths) ───
app.include_router(ws_router.router, tags=["WebSocket"])


# =============================================================
# Internal Broadcast Endpoint
# Used by Celery workers to push agent alerts to WebSocket clients.
# Only accessible from within the Docker network (no auth required
# since it is not exposed externally).
# =============================================================


@app.post(
    "/internal/broadcast-alert",
    include_in_schema=False,  # Hide from public API docs
)
async def internal_broadcast_alert(payload: dict) -> dict:
    """
    Internal endpoint for Celery workers to broadcast agent alerts
    to the 'agent-alerts' WebSocket room.

    This endpoint is NOT exposed externally — it is only reachable
    from within the Docker network via BACKEND_URL.
    """
    from websocket.manager import manager as ws_manager

    await ws_manager.broadcast_agent_alert(payload)
    return {"status": "broadcast_sent", "room": "agent-alerts"}


# =============================================================
# Root Endpoints
# =============================================================


@app.get(
    "/",
    summary="Health check",
    response_description="Service liveness probe",
    tags=["Health"],
)
async def root() -> dict[str, Any]:
    """
    Lightweight liveness probe used by Docker health checks, load balancers,
    and the frontend to verify the API is running.
    """
    return {
        "status": "ok",
        "service": settings.APP_TITLE,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
    }


@app.get(
    "/health",
    summary="Deep health check",
    response_description="Detailed readiness probe including downstream service status",
    tags=["Health"],
)
async def health_check() -> dict[str, Any]:
    """
    Readiness probe that checks connectivity to all critical downstream
    services. Returns a 200 if all checks pass, 503 otherwise.
    """
    checks: dict[str, str] = {}
    all_healthy = True

    # Database
    db_ok = await check_database_connection()
    checks["database"] = "ok" if db_ok else "unreachable"
    if not db_ok:
        all_healthy = False

    # Redis
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        await r.ping()
        await r.aclose()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "unreachable"
        all_healthy = False

    # Ollama
    try:
        import httpx

        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{settings.OLLAMA_BASE_URL}/")
            checks["ollama"] = "ok" if resp.status_code < 500 else "degraded"
    except Exception:
        checks["ollama"] = "unreachable"

    overall_status = "ok" if all_healthy else "degraded"
    http_status = (
        status.HTTP_200_OK if all_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    )

    return JSONResponse(
        status_code=http_status,
        content={
            "status": overall_status,
            "service": settings.APP_TITLE,
            "version": settings.APP_VERSION,
            "checks": checks,
        },
    )
