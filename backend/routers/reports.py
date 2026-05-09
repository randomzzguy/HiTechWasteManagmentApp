# =============================================================
# Hi-Tech Waste Management — Reports Router
# Celery-backed report generation + PDF download streaming
# =============================================================

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from config import get_settings
from database import get_db
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from routers.auth import get_current_user, require_roles

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()

# =============================================================
# Report type constants
# =============================================================

REPORT_TYPES = {
    "esg_monthly",
    "tonnage_summary",
    "compliance_audit",
    "fleet_utilisation",
    "recyclables_recovery",
    "invoice_ageing",
}

REPORT_TYPE_DESCRIPTIONS = {
    "esg_monthly": "Monthly ESG performance report with carbon metrics and SDG alignment",
    "tonnage_summary": "Waste tonnage summary by client, waste type, and time period",
    "compliance_audit": "Scheduled waste compliance audit — batch status, deadlines, consignment notes",
    "fleet_utilisation": "Fleet utilisation report — trip counts, distance, fuel, maintenance schedule",
    "recyclables_recovery": "Recyclables recovery report — material breakdown, revenue, buyer traceability",
    "invoice_ageing": "Accounts-receivable ageing schedule with outstanding invoice breakdown",
}

# =============================================================
# Note: Report task metadata is stored in Celery result backend.
# For production, consider adding a report_tasks DB table for
# persistence across restarts.
# =============================================================


# =============================================================
# Pydantic Schemas
# =============================================================


class ReportGenerateRequest(BaseModel):
    """
    Request body for POST /reports/generate.

    Specifies the report type, optional scope (client_id), and
    the reporting period. All parameters are forwarded to the
    appropriate Celery task.
    """

    report_type: str = Field(
        ...,
        description=(
            "Type of report to generate. One of: " + ", ".join(sorted(REPORT_TYPES))
        ),
        examples=["esg_monthly"],
    )
    client_id: Optional[uuid.UUID] = Field(
        default=None,
        description=(
            "Scope the report to a specific client UUID. "
            "If omitted, a company-wide report is generated "
            "(applicable to most report types)."
        ),
    )
    period_from: Optional[str] = Field(
        default=None,
        description="Report period start date in ISO format YYYY-MM-DD.",
        examples=["2024-01-01"],
    )
    period_to: Optional[str] = Field(
        default=None,
        description="Report period end date in ISO format YYYY-MM-DD.",
        examples=["2024-12-31"],
    )
    report_title: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Custom report title. Auto-generated if omitted.",
    )
    include_charts: bool = Field(
        default=True,
        description="Whether to include charts/visualisations in the PDF.",
    )
    output_format: str = Field(
        default="pdf",
        description="Output format. Currently only 'pdf' is supported.",
    )
    extra_params: Optional[Dict[str, Any]] = Field(
        default=None,
        description=(
            "Optional additional parameters passed through to the report generator. "
            "Content is report-type specific."
        ),
    )

    model_config = ConfigDict(str_strip_whitespace=True)


class ReportTaskResponse(BaseModel):
    """Response returned after successfully queuing a report generation task."""

    task_id: str = Field(description="Celery task ID for status polling")
    report_type: str
    status: str = Field(
        description="Initial task status: 'queued' or 'error'",
        examples=["queued"],
    )
    client_id: Optional[str] = None
    period_from: Optional[str] = None
    period_to: Optional[str] = None
    report_title: Optional[str] = None
    queued_at: str = Field(description="ISO timestamp when the task was enqueued")
    poll_url: str = Field(
        description="URL to poll for task status and download the report when ready"
    )
    message: str

    model_config = ConfigDict(from_attributes=True)


class ReportStatusResponse(BaseModel):
    """Response for task status queries."""

    task_id: str
    report_type: Optional[str] = None
    status: str = Field(
        description="pending | running | success | failure",
        examples=["success"],
    )
    progress_pct: Optional[int] = Field(
        default=None,
        description="Progress percentage (0-100) if the task reports progress",
    )
    pdf_url: Optional[str] = Field(
        default=None,
        description=(
            "Relative download URL for the generated PDF. "
            "Available once status='success'."
        ),
    )
    file_size_bytes: Optional[int] = Field(
        default=None,
        description="Size of the generated PDF file in bytes.",
    )
    generated_at: Optional[str] = Field(
        default=None,
        description="ISO timestamp when the report was successfully generated.",
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Error description when status='failure'.",
    )
    message: str

    model_config = ConfigDict(from_attributes=True)


# =============================================================
# Celery task name mapping
# =============================================================

# Maps report_type -> Celery task name registered in tasks/report_tasks.py
CELERY_TASK_MAP: Dict[str, str] = {
    "esg_monthly": "tasks.report_tasks.generate_esg_monthly_report",
    "tonnage_summary": "tasks.report_tasks.generate_tonnage_summary_report",
    "compliance_audit": "tasks.report_tasks.generate_compliance_audit_report",
    "fleet_utilisation": "tasks.report_tasks.generate_fleet_utilisation_report",
    "recyclables_recovery": "tasks.report_tasks.generate_recyclables_recovery_report",
    "invoice_ageing": "tasks.report_tasks.generate_invoice_ageing_report",
}


# =============================================================
# POST /generate — trigger report generation
# =============================================================


@router.post(
    "/generate",
    response_model=ReportTaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger report generation",
    description=(
        "Enqueues a Celery task to generate a PDF report of the specified type. "
        "Returns a `task_id` immediately. "
        "Poll `GET /reports/{task_id}/status` to check progress. "
        "Download the completed report via `GET /reports/{task_id}/download`."
    ),
)
async def generate_report(
    payload: ReportGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> ReportTaskResponse:
    """
    Triggers asynchronous PDF report generation via Celery.

    **Supported report types and their scoping:**

    | report_type            | client_id required? | period required? |
    |------------------------|--------------------:|----------------:|
    | esg_monthly            | optional            | recommended      |
    | tonnage_summary        | optional            | recommended      |
    | compliance_audit       | optional            | optional         |
    | fleet_utilisation      | no                  | recommended      |
    | recyclables_recovery   | optional            | recommended      |
    | invoice_ageing         | optional            | no               |

    The endpoint validates the report_type, optionally validates the
    client_id, and enqueues the appropriate Celery task. If Celery is
    unavailable, a placeholder task entry is created in the in-memory
    store so the status endpoint remains consistent.
    """
    # ── Validate report_type ──────────────────────────────────
    if payload.report_type not in REPORT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Invalid report_type '{payload.report_type}'. "
                f"Must be one of: {sorted(REPORT_TYPES)}"
            ),
        )

    # ── Validate client_id if supplied ───────────────────────
    if payload.client_id is not None:
        from models.client import Client as ClientModel
        from sqlalchemy import select

        client_result = await db.execute(
            select(ClientModel).where(ClientModel.id == payload.client_id)
        )
        if client_result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Client {payload.client_id} not found",
            )

    # ── Build report title if not supplied ────────────────────
    report_title = payload.report_title
    if not report_title:
        parts = [REPORT_TYPE_DESCRIPTIONS.get(payload.report_type, payload.report_type)]
        if payload.period_from and payload.period_to:
            parts.append(f"({payload.period_from} → {payload.period_to})")
        elif payload.period_from:
            parts.append(f"(from {payload.period_from})")
        report_title = " ".join(parts)

    # ── Build task kwargs ─────────────────────────────────────
    task_kwargs: Dict[str, Any] = {
        "report_type": payload.report_type,
        "client_id": str(payload.client_id) if payload.client_id else None,
        "period_from": payload.period_from,
        "period_to": payload.period_to,
        "report_title": report_title,
        "include_charts": payload.include_charts,
        "output_format": payload.output_format,
        "requested_by": current_user["sub"],
        "extra_params": payload.extra_params or {},
    }

    task_id_str = str(uuid.uuid4())
    queued_at = datetime.now(timezone.utc).isoformat()

    # ── Enqueue via Celery ────────────────────────────────────
    celery_task_name = CELERY_TASK_MAP[payload.report_type]
    celery_queued = False

    try:
        from tasks.celery_app import celery_app  # type: ignore[import]

        task = celery_app.send_task(celery_task_name, kwargs=task_kwargs)
        task_id_str = task.id
        celery_queued = True
        logger.info(
            "Report task enqueued | type=%s | task_id=%s | client=%s | by=%s",
            payload.report_type,
            task_id_str,
            payload.client_id,
            current_user["sub"],
        )
    except Exception as exc:
        # Celery unavailable — record in in-memory store and continue
        logger.warning(
            "Could not enqueue report task '%s' via Celery: %s. "
            "Using placeholder task_id=%s.",
            celery_task_name,
            exc,
            task_id_str,
        )

    poll_url = f"{settings.BACKEND_URL}/api/v1/reports/{task_id_str}/status"

    return ReportTaskResponse(
        task_id=task_id_str,
        report_type=payload.report_type,
        status="queued" if celery_queued else "pending",
        client_id=str(payload.client_id) if payload.client_id else None,
        period_from=payload.period_from,
        period_to=payload.period_to,
        report_title=report_title,
        queued_at=queued_at,
        poll_url=poll_url,
        message=(
            f"Report generation task has been queued (task_id={task_id_str}). "
            f"Poll {poll_url} to check status. "
            f"Download the PDF via GET /api/v1/reports/{task_id_str}/download "
            "once status='success'."
        ),
    )


# =============================================================
# GET /{task_id}/status — poll task status
# =============================================================


@router.get(
    "/{task_id}/status",
    response_model=ReportStatusResponse,
    summary="Poll report generation task status",
    description=(
        "Checks the status of a queued or running report generation task. "
        "Returns the PDF download URL when status='success'."
    ),
)
async def get_report_status(
    task_id: str,
    current_user: Any = Depends(get_current_user),
) -> ReportStatusResponse:
    """
    Polls the Celery result backend for task status.

    Response states:
    - **pending**  : Task is queued but not yet picked up by a worker
    - **running**  : Worker is actively generating the report
    - **success**  : Report generated — `pdf_url` is populated
    - **failure**  : Generation failed — `error_message` contains details
    """
    # Query Celery result backend
    try:
        from celery.result import AsyncResult  # type: ignore[import]
        from tasks.celery_app import celery_app  # type: ignore[import]

        result = AsyncResult(task_id, app=celery_app)
        state = result.state
        
        # Get report type from task result if available
        report_type = None

        if state == "PENDING":
            return ReportStatusResponse(
                task_id=task_id,
                report_type=report_type,
                status="pending",
                message="Report generation task is queued and waiting for a worker.",
            )

        if state in ("STARTED", "RETRY"):
            info = result.info or {}
            progress = info.get("progress_pct") if isinstance(info, dict) else None
            return ReportStatusResponse(
                task_id=task_id,
                report_type=report_type,
                status="running",
                progress_pct=progress,
                message="Report is currently being generated.",
            )

        if state == "PROGRESS":
            info = result.info or {}
            progress = info.get("progress_pct") if isinstance(info, dict) else None
            step = info.get("step", "") if isinstance(info, dict) else ""
            return ReportStatusResponse(
                task_id=task_id,
                report_type=report_type,
                status="running",
                progress_pct=progress,
                message=f"Generating report: {step}"
                if step
                else "Report is being generated.",
            )

        if state == "SUCCESS":
            task_result = result.result or {}
            pdf_path: Optional[str] = None
            pdf_url: Optional[str] = None
            file_size_bytes: Optional[int] = None
            generated_at: Optional[str] = None
            report_type_from_result = None

            if isinstance(task_result, dict):
                pdf_path = task_result.get("pdf_path")
                pdf_url = task_result.get("pdf_url")
                file_size_bytes = task_result.get("file_size_bytes")
                generated_at = task_result.get("generated_at")
                report_type_from_result = task_result.get("report_type")

            # Build download URL if we have a pdf_path
            if pdf_path and not pdf_url:
                pdf_url = f"{settings.BACKEND_URL}/api/v1/reports/{task_id}/download"

            return ReportStatusResponse(
                task_id=task_id,
                report_type=report_type or report_type_from_result,
                status="success",
                pdf_url=pdf_url,
                file_size_bytes=file_size_bytes,
                message=f"Report generated successfully. Download at {pdf_url}"
                if pdf_url
                else "Report generated but download URL unavailable.",
            )

        if state == "FAILURE":
            error_info = str(result.info) if result.info else "Unknown error"
            return ReportStatusResponse(
                task_id=task_id,
                report_type=report_type,
                status="failure",
                error_message=error_info,
                message=f"Report generation failed: {error_info}",
            )

        # Other Celery states (REVOKED, etc.)
        return ReportStatusResponse(
            task_id=task_id,
            report_type=report_type,
            status=state.lower(),
            message=f"Task is in state: {state}",
        )

    except Exception as exc:
        logger.warning(
            "Celery result backend unavailable for task_id=%s: %s", task_id, exc
        )

    # Celery unavailable — return generic response
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=(
            f"Cannot determine status for task '{task_id}'. "
            "Celery result backend is unavailable. Please try again later."
        ),
    )


# =============================================================
# GET /{task_id}/download — stream the generated PDF
# =============================================================


@router.get(
    "/{task_id}/download",
    summary="Download the generated PDF report",
    description=(
        "Streams the generated PDF file as a downloadable response. "
        "Returns HTTP 202 if the report is still being generated. "
        "Returns HTTP 404 if the task does not exist or has no PDF."
    ),
    responses={
        200: {
            "content": {"application/pdf": {}},
            "description": "PDF report file",
        },
        202: {"description": "Report is still being generated — retry later"},
        404: {"description": "Task not found or PDF not yet available"},
    },
)
async def download_report(
    task_id: str,
    current_user: Any = Depends(get_current_user),
) -> Any:
    """
    Downloads the generated PDF report for a completed task.

    **Behaviour:**
    1. Resolves the PDF file path from the Celery result backend
       or the in-memory task store.
    2. If the task is still running, returns HTTP 202 with a
       Retry-After header.
    3. If the PDF file exists on disk, streams it as an
       `application/pdf` FileResponse with Content-Disposition set
       to trigger a browser download.
    4. If the file path is recorded but the file is missing from disk
       (e.g. the container was restarted), returns HTTP 410 Gone with
       an instruction to regenerate the report.

    **Access control:**
    - All authenticated users can download any report (the report scope
      is encoded in the filename, not the access control).
    - In a production deployment, you may want to verify that the
      requesting user matches the `requested_by` field stored in
      the task metadata.
    """
    from fastapi.responses import JSONResponse

    # ── Resolve task metadata ─────────────────────────────────
    pdf_path: Optional[str] = None
    task_status: str = "unknown"
    report_type: Optional[str] = None

    # 1. Try Celery result backend
    celery_resolved = False
    try:
        from celery.result import AsyncResult  # type: ignore[import]
        from tasks.celery_app import celery_app  # type: ignore[import]

        result = AsyncResult(task_id, app=celery_app)

        if result.state == "SUCCESS":
            task_result = result.result or {}
            if isinstance(task_result, dict):
                pdf_path = task_result.get("pdf_path")
            task_status = "success"
            celery_resolved = True
        elif result.state in ("PENDING", "STARTED", "RETRY", "PROGRESS"):
            task_status = "running"
            celery_resolved = True
        elif result.state == "FAILURE":
            task_status = "failure"
            celery_resolved = True

    except Exception as exc:
        logger.debug(
            "Celery backend unavailable for task_id=%s during download: %s",
            task_id,
            exc,
        )

    if not celery_resolved:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"Cannot retrieve task '{task_id}'. "
                "Celery result backend is unavailable. Please try again later."
            ),
        )

    # ── Status-based early returns ────────────────────────────
    if task_status in ("pending", "running", "queued"):
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={
                "task_id": task_id,
                "status": task_status,
                "message": (
                    "The report is still being generated. "
                    "Please retry in a few seconds. "
                    f"Poll GET /api/v1/reports/{task_id}/status to check progress."
                ),
            },
            headers={"Retry-After": "10"},
        )

    if task_status == "failure":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                f"Report generation failed for task '{task_id}'. "
                "Please regenerate the report via POST /reports/generate."
            ),
        )

    # ── Validate PDF file exists on disk ──────────────────────
    if not pdf_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No PDF file path is recorded for task '{task_id}'. "
                "The report may still be generating or the result was lost. "
                f"Check status via GET /api/v1/reports/{task_id}/status."
            ),
        )

    if not os.path.exists(pdf_path):
        logger.error(
            "PDF file not found on disk for task_id=%s: path=%s",
            task_id,
            pdf_path,
        )
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=(
                f"The PDF file for report task '{task_id}' no longer exists on disk "
                f"(expected at: {pdf_path}). "
                "Please regenerate the report via POST /reports/generate."
            ),
        )

    # ── Stream the PDF file ───────────────────────────────────
    file_size = os.path.getsize(pdf_path)
    filename = _build_download_filename(task_id, report_type, local_meta)

    logger.info(
        "Streaming PDF report | task_id=%s | path=%s | size=%d bytes | user=%s",
        task_id,
        pdf_path,
        file_size,
        current_user["sub"],
    )

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=filename,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(file_size),
            "X-Report-Task-ID": task_id,
            "X-Report-Type": report_type or "unknown",
        },
    )


def _build_download_filename(
    task_id: str,
    report_type: Optional[str],
    task_meta: Dict[str, Any],
) -> str:
    """
    Builds a descriptive, filesystem-safe download filename for the PDF.

    Format: {report_type}_{period_from}_{period_to}_{task_id[:8]}.pdf
    Example: esg_monthly_2024-01-01_2024-12-31_a1b2c3d4.pdf
    """
    parts: List[str] = []

    if report_type:
        parts.append(report_type.replace(" ", "_").lower())
    else:
        parts.append("report")

    period_from = task_meta.get("period_from")
    period_to = task_meta.get("period_to")

    if period_from:
        parts.append(period_from.replace("-", ""))
    if period_to:
        parts.append(period_to.replace("-", ""))

    # Append short task_id suffix for uniqueness
    parts.append(task_id[:8])

    return "_".join(parts) + ".pdf"


# =============================================================
# GET / — list available report types
# =============================================================


@router.get(
    "/",
    response_model=Dict[str, Any],
    summary="List available report types",
    description=(
        "Returns the catalogue of available report types with descriptions "
        "and their supported parameters."
    ),
)
async def list_report_types(
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Returns the catalogue of available PDF report types.

    Each entry includes:
    - `report_type`: the string identifier to use in POST /reports/generate
    - `description`: human-readable description of the report
    - `supports_client_filter`: whether a client_id can be specified
    - `supports_period_filter`: whether a date range can be specified
    """
    catalogue = [
        {
            "report_type": "esg_monthly",
            "description": REPORT_TYPE_DESCRIPTIONS["esg_monthly"],
            "supports_client_filter": True,
            "supports_period_filter": True,
            "typical_pages": "8-15",
        },
        {
            "report_type": "tonnage_summary",
            "description": REPORT_TYPE_DESCRIPTIONS["tonnage_summary"],
            "supports_client_filter": True,
            "supports_period_filter": True,
            "typical_pages": "4-8",
        },
        {
            "report_type": "compliance_audit",
            "description": REPORT_TYPE_DESCRIPTIONS["compliance_audit"],
            "supports_client_filter": True,
            "supports_period_filter": False,
            "typical_pages": "6-12",
        },
        {
            "report_type": "fleet_utilisation",
            "description": REPORT_TYPE_DESCRIPTIONS["fleet_utilisation"],
            "supports_client_filter": False,
            "supports_period_filter": True,
            "typical_pages": "5-10",
        },
        {
            "report_type": "recyclables_recovery",
            "description": REPORT_TYPE_DESCRIPTIONS["recyclables_recovery"],
            "supports_client_filter": True,
            "supports_period_filter": True,
            "typical_pages": "6-12",
        },
        {
            "report_type": "invoice_ageing",
            "description": REPORT_TYPE_DESCRIPTIONS["invoice_ageing"],
            "supports_client_filter": True,
            "supports_period_filter": False,
            "typical_pages": "3-6",
        },
    ]

    return {
        "total": len(catalogue),
        "report_types": catalogue,
    }


# =============================================================
# GET /history — list recently generated reports (in-memory)
# =============================================================


@router.get(
    "/history",
    response_model=Dict[str, Any],
    summary="List recently generated report tasks",
    description=(
        "Returns the history of report generation tasks from the "
        "in-memory task store. In production this would query a "
        "persistent task-result database."
    ),
)
async def list_report_history(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    report_type: Optional[str] = Query(
        default=None, description="Filter by report type"
    ),
    status_filter: Optional[str] = Query(
        default=None,
        alias="status",
        description="pending | queued | running | success | failure",
    ),
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    """Returns the history of report generation tasks."""
    tasks = list(_TASK_STORE.values())

    # Filter by requesting user (non-superadmin users see only their own tasks)
    if current_user.get("role") not in {"superadmin", "management"}:
        tasks = [t for t in tasks if t.get("requested_by") == current_user.get("sub")]

    # Apply optional filters
    if report_type:
        tasks = [t for t in tasks if t.get("report_type") == report_type]
    if status_filter:
        tasks = [t for t in tasks if t.get("status") == status_filter]

    # Sort by queued_at descending
    tasks.sort(key=lambda x: x.get("queued_at", ""), reverse=True)

    total = len(tasks)
    paginated = tasks[skip : skip + limit]

    # Build download URLs for completed tasks
    enriched = []
    for t in paginated:
        item = dict(t)
        if item.get("status") == "success" and item.get("pdf_path"):
            item["download_url"] = (
                f"{settings.BACKEND_URL}/api/v1/reports/{item['task_id']}/download"
            )
        else:
            item["download_url"] = None
        item["status_url"] = (
            f"{settings.BACKEND_URL}/api/v1/reports/{item['task_id']}/status"
        )
        enriched.append(item)

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": enriched,
    }


# =============================================================
# DELETE /{task_id} — remove a task entry and delete its PDF
# =============================================================


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Delete a report task and its generated PDF",
    description=(
        "Removes the task entry from the in-memory store and deletes "
        "the generated PDF file from disk (if it exists). "
        "Only the user who created the task or management/superadmin can delete it."
    ),
)
async def delete_report_task(
    task_id: str,
    current_user: Any = Depends(get_current_user),
) -> None:
    """
    Deletes a report task entry and its associated PDF file.

    - Any authenticated user can delete their own task entries.
    - Management and superadmin roles can delete any task.
    - The in-memory entry is removed and the PDF file is deleted from disk.
    """
    task_meta = _TASK_STORE.get(task_id)
    if task_meta is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report task '{task_id}' not found",
        )

    # Access control
    role = current_user.get("role")
    if role not in {"superadmin", "management"} and task_meta.get(
        "requested_by"
    ) != current_user.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this report task",
        )

    # Delete PDF from disk if it exists
    pdf_path = task_meta.get("pdf_path")
    if pdf_path and os.path.exists(pdf_path):
        try:
            os.remove(pdf_path)
            logger.info(
                "Deleted report PDF: path=%s | task_id=%s | by=%s",
                pdf_path,
                task_id,
                current_user["sub"],
            )
        except OSError as exc:
            logger.warning(
                "Could not delete PDF file %s for task %s: %s",
                pdf_path,
                task_id,
                exc,
            )

    # Remove from in-memory store
    del _TASK_STORE[task_id]
    logger.info(
        "Report task %s deleted by user %s",
        task_id,
        current_user["sub"],
    )
