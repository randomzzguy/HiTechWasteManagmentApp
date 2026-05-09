# =============================================================
# Hi-Tech Waste Management - Report Generation Celery Tasks
# PDF report generation for all report types
# =============================================================
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from celery.exceptions import SoftTimeLimitExceeded
from jinja2 import Environment, FileSystemLoader, select_autoescape

from tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

# Jinja2 template setup
TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "reports"
jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(['html', 'xml'])
)


# =============================================================
# Shared helpers
# =============================================================

def _get_output_path(report_type: str, task_id: str) -> str:
    from config import get_settings
    settings = get_settings()
    output_dir = os.path.join(settings.REPORT_OUTPUT_DIR, "reports")
    os.makedirs(output_dir, exist_ok=True)
    return os.path.join(output_dir, f"{report_type}_{task_id[:8]}.pdf")


def _load_and_render_template(report_type: str, context: dict[str, Any]) -> str | None:
    """Load Jinja2 template and render with context data."""
    template_map = {
        "esg_monthly": "esg_monthly.html",
        "tonnage_summary": "tonnage_summary.html",
        "compliance_audit": "compliance_audit.html",
        "fleet_utilisation": "fleet_utilisation.html",
        "recyclables_recovery": "recyclables_recovery.html",
        "invoice_ageing": "invoice_ageing.html",
    }
    
    template_name = template_map.get(report_type)
    if not template_name:
        logger.error(f"No template found for report type: {report_type}")
        return None
    
    try:
        template = jinja_env.get_template(template_name)
        # Add common context variables
        context["generated_at"] = datetime.now(timezone.utc).strftime("%d %B %Y, %H:%M UTC")
        return template.render(**context)
    except Exception as exc:
        logger.error(f"Template rendering failed for {report_type}: {exc}")
        return None


def _build_fallback_html(title: str, data: dict[str, Any]) -> str:
    """Build simple fallback HTML if template rendering fails."""
    now = datetime.now(timezone.utc).strftime("%d %B %Y, %H:%M UTC")
    rows = "".join(
        f"<tr><td><strong>{k.replace('_', ' ').title()}</strong></td><td>{v}</td></tr>"
        for k, v in data.items()
    )
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; color: #333; }}
        h1 {{ color: #1a5c2a; border-bottom: 2px solid #1a5c2a; padding-bottom: 10px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th {{ background: #1a5c2a; color: white; padding: 10px; text-align: left; }}
        td {{ padding: 8px 10px; border-bottom: 1px solid #ddd; }}
        tr:nth-child(even) {{ background: #f9f9f9; }}
        .footer {{ margin-top: 40px; font-size: 11px; color: #888; border-top: 1px solid #ddd; padding-top: 10px; }}
    </style></head><body>
    <h1>Hi-Tech Waste Management Sdn. Bhd.</h1>
    <h2>{title}</h2>
    <p>Generated: {now}</p>
    <table><thead><tr><th>Metric</th><th>Value</th></tr></thead><tbody>{rows}</tbody></table>
    <div class="footer">Hi-Tech Waste Management Sdn. Bhd. | Shah Alam, Selangor, Malaysia</div>
    </body></html>"""


def _render_pdf(html: str, output_path: str) -> bool:
    try:
        from weasyprint import HTML  # type: ignore[import]
        HTML(string=html).write_pdf(output_path)
        return True
    except Exception:
        pass
    try:
        import re
        from reportlab.lib.pagesizes import A4  # type: ignore[import]
        from reportlab.pdfgen import canvas as rl_canvas  # type: ignore[import]
        from reportlab.lib.units import cm  # type: ignore[import]
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()
        c = rl_canvas.Canvas(output_path, pagesize=A4)
        width, height = A4
        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(width / 2, height - 2 * cm, "HI-TECH WASTE MANAGEMENT")
        c.setFont("Helvetica", 10)
        y = height - 3.5 * cm
        for line in text[:3000].split(". "):
            if y < 2 * cm:
                c.showPage()
                y = height - 2 * cm
                c.setFont("Helvetica", 10)
            c.drawString(2 * cm, y, line.strip()[:100])
            y -= 0.5 * cm
        c.save()
        return True
    except Exception as exc:
        logger.error("PDF render failed: %s", exc)
        return False


def _run_report(
    self_task: Any,
    report_type: str,
    client_id: str | None = None,
    period_from: str | None = None,
    period_to: str | None = None,
    report_title: str | None = None,
    requested_by: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Shared implementation called by every report task."""
    task_id = self_task.request.id or str(uuid.uuid4())
    title = report_title or report_type.replace("_", " ").title()
    started_at = datetime.now(timezone.utc)

    try:
        from database import SyncSessionLocal
        from sqlalchemy import text
        from decimal import Decimal

        context: dict[str, Any] = {
            "report_type": report_type,
            "report_title": title,
            "period_from": period_from,
            "period_to": period_to,
            "client_scope": client_id or "Company-wide",
            "generated_by": requested_by or "System",
            "company_reg_no": "123456-X",
            "doe_license": "SW-2024-001",
        }

        with SyncSessionLocal() as session:
            if report_type == "tonnage_summary":
                context.update(_get_tonnage_data(session, period_from, period_to, client_id))

            elif report_type == "compliance_audit":
                context.update(_get_compliance_data(session, period_from, period_to, client_id))

            elif report_type == "fleet_utilisation":
                context.update(_get_fleet_data(session, period_from, period_to))

            elif report_type == "invoice_ageing":
                context.update(_get_invoice_data(session, period_from, period_to))

            elif report_type == "esg_monthly":
                context.update(_get_esg_data(session, period_from, period_to, client_id))

            elif report_type == "recyclables_recovery":
                context.update(_get_recyclables_data(session, period_from, period_to, client_id))
        
        pdf_path = _get_output_path(report_type, task_id)
        
        # Try to render with proper template, fallback to simple HTML
        html = _load_and_render_template(report_type, context)
        if html is None:
            logger.warning(f"Template rendering failed, using fallback for {report_type}")
            # Build simple fallback data
            data = {
                "Report Type": report_type.replace("_", " ").title(),
                "Period": f"{period_from or 'All time'} to {period_to or 'Present'}",
                "Client Scope": client_id or "Company-wide",
                "Generated By": requested_by or "System",
                "Generated At": started_at.strftime("%d %b %Y %H:%M UTC"),
            }
            html = _build_fallback_html(title, data)
        
        _render_pdf(html, pdf_path)

        file_size = os.path.getsize(pdf_path) if os.path.exists(pdf_path) else 0
        completed_at = datetime.now(timezone.utc)
        logger.info(
            "Report generated | type=%s | path=%s | size=%d bytes",
            report_type, pdf_path, file_size,
        )

        return {
            "report_type": report_type,
            "title": title,
            "pdf_path": pdf_path,
            "file_size_bytes": file_size,
            "generated_at": completed_at.isoformat(),
            "duration_seconds": (completed_at - started_at).total_seconds(),
        }

    except SoftTimeLimitExceeded:
        logger.warning("Report task soft time limit exceeded | type=%s", report_type)
        return {"report_type": report_type, "error": "Task timed out"}
    except Exception as exc:
        logger.error(
            "Report task failed | type=%s | error=%s", report_type, exc, exc_info=True
        )
        raise self_task.retry(exc=exc)


# =============================================================
# Data Query Helper Functions
# =============================================================

def _get_tonnage_data(session: Any, period_from: str | None, period_to: str | None, client_id: str | None) -> dict[str, Any]:
    """Fetch weighbridge tonnage data for report."""
    from sqlalchemy import text
    
    where_clause = "WHERE 1=1"
    params: dict[str, Any] = {}
    if period_from:
        where_clause += " AND recorded_at >= :period_from"
        params["period_from"] = period_from
    if period_to:
        where_clause += " AND recorded_at <= :period_to"
        params["period_to"] = period_to
    if client_id:
        where_clause += " AND client_id = :client_id"
        params["client_id"] = client_id
    
    # Summary totals
    row = session.execute(text(f"""
        SELECT 
            COUNT(*) as records,
            COALESCE(SUM(gross_weight_kg), 0) as gross,
            COALESCE(SUM(tare_weight_kg), 0) as tare,
            COALESCE(SUM(net_weight_kg), 0) as net
        FROM weighbridge_records
        {where_clause}
    """), params).first()
    
    data = {
        "total_records": row[0] if row else 0,
        "total_gross_kg": float(row[1]) if row else 0,
        "total_tare_kg": float(row[2]) if row else 0,
        "total_net_kg": float(row[3]) if row else 0,
        "total_trips": row[0] if row else 0,
    }
    
    # Daily breakdown
    daily_rows = session.execute(text(f"""
        SELECT 
            DATE(recorded_at) as day,
            COUNT(*) as trips,
            COALESCE(SUM(gross_weight_kg), 0) as gross,
            COALESCE(SUM(tare_weight_kg), 0) as tare,
            COALESCE(SUM(net_weight_kg), 0) as net
        FROM weighbridge_records
        {where_clause}
        GROUP BY DATE(recorded_at)
        ORDER BY day
    """), params).fetchall()
    
    data["daily_breakdown"] = [
        {
            "date": str(r[0]),
            "trips": r[1],
            "gross_kg": float(r[2]),
            "tare_kg": float(r[3]),
            "net_kg": float(r[4]),
        }
        for r in daily_rows
    ]
    
    # Waste type breakdown (from JSON field)
    data["waste_type_breakdown"] = []  # Placeholder - requires JSON parsing
    
    # Top clients
    client_rows = session.execute(text(f"""
        SELECT 
            c.company_name,
            COUNT(*) as trips,
            COALESCE(SUM(w.net_weight_kg), 0) as net_kg
        FROM weighbridge_records w
        LEFT JOIN clients c ON w.client_id = c.id
        {where_clause}
        GROUP BY c.company_name
        ORDER BY net_kg DESC
        LIMIT 10
    """), params).fetchall()
    
    total_net = data["total_net_kg"]
    data["top_clients"] = [
        {
            "name": r[0] or "Unknown",
            "trips": r[1],
            "net_tonnes": float(r[2]) / 1000,
            "percentage": round(float(r[2]) / total_net * 100, 1) if total_net > 0 else 0,
        }
        for r in client_rows
    ]
    
    # Period comparison placeholders
    data["prev_net_tonnes"] = data["total_net_kg"] / 1000 * 0.9  # Placeholder
    data["current_net_tonnes"] = data["total_net_kg"] / 1000
    data["tonnage_change_pct"] = 10.0  # Placeholder
    
    return data


def _get_compliance_data(session: Any, period_from: str | None, period_to: str | None, client_id: str | None) -> dict[str, Any]:
    """Fetch scheduled waste compliance data."""
    from sqlalchemy import text
    from datetime import date
    
    today = date.today()
    
    # Summary counts
    row = session.execute(text("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN status='in_storage' THEN 1 ELSE 0 END) as in_storage,
            SUM(CASE WHEN status='dispatched' THEN 1 ELSE 0 END) as dispatched,
            SUM(CASE WHEN status='processed' THEN 1 ELSE 0 END) as processed
        FROM scheduled_waste_batches
    """)).first()
    
    data = {
        "total_batches": row[0] if row else 0,
        "in_storage_batches": row[1] if row else 0,
        "disposed_batches": (row[2] or 0) + (row[3] or 0) if row else 0,
    }
    
    # Compliance rate (processed vs total)
    data["compliance_rate"] = round((data["disposed_batches"] / data["total_batches"] * 100), 1) if data["total_batches"] > 0 else 100
    
    # 90-day rule analysis
    overdue_rows = session.execute(text("""
        SELECT 
            id,
            sw_code,
            waste_description,
            quantity_kg,
            storage_start_date,
            storage_deadline,
            status,
            client_id
        FROM scheduled_waste_batches
        WHERE status = 'in_storage'
        ORDER BY storage_deadline
    """)).fetchall()
    
    overdue_count = 0
    warning_count = 0
    attention_count = 0
    compliant_count = 0
    batch_details = []
    
    for r in overdue_rows:
        deadline = r[5]  # storage_deadline
        days_remaining = (deadline - today).days if deadline else 0
        days_in_storage = (today - r[4]).days if r[4] else 0
        
        if days_remaining < 0:
            overdue_count += 1
        elif days_remaining <= 15:
            warning_count += 1
        elif days_remaining <= 30:
            attention_count += 1
        else:
            compliant_count += 1
        
        # Get client name
        client_row = session.execute(text("SELECT company_name FROM clients WHERE id = :id"), {"id": r[7]}).first()
        client_name = client_row[0] if client_row else "Unknown"
        
        batch_details.append({
            "id": str(r[0]),
            "sw_code": r[1],
            "waste_description": r[2][:50] + "..." if r[2] and len(r[2]) > 50 else r[2],
            "quantity_kg": float(r[3]) if r[3] else 0,
            "storage_start_date": str(r[4]),
            "days_in_storage": days_in_storage,
            "status": r[6],
            "client_name": client_name,
        })
    
    data.update({
        "overdue_batches": overdue_count,
        "warning_batches": warning_count,
        "attention_batches": attention_count,
        "compliant_batches": compliant_count,
        "batch_details": batch_details[:50],  # Limit to 50 for PDF
    })
    
    # SW code summary
    sw_rows = session.execute(text("""
        SELECT sw_code, COUNT(*) as cnt, SUM(quantity_kg) as qty
        FROM scheduled_waste_batches
        GROUP BY sw_code
        ORDER BY cnt DESC
    """)).fetchall()
    
    sw_descriptions = {
        "SW 305": "Spent lubricating oil",
        "SW 410": "Waste from electrical/electronic assemblies",
        "SW 202": "Waste catalysts",
        "SW 409": "Metal hydroxide sludge",
        "SW 102": "Waste from chemical processing",
    }
    
    data["sw_summary"] = [
        {
            "code": r[0],
            "description": sw_descriptions.get(r[0], "Scheduled Waste"),
            "batch_count": r[1],
            "total_kg": float(r[2]) if r[2] else 0,
            "in_storage": sum(1 for b in batch_details if b["sw_code"] == r[0] and b["status"] == "in_storage"),
            "disposed": sum(1 for b in batch_details if b["sw_code"] == r[0] and b["status"] != "in_storage"),
        }
        for r in sw_rows
    ]
    
    # Empty arrays for consignment notes and disposal certificates
    data["consignment_notes"] = []
    data["disposal_certificates"] = []
    
    # Audit findings
    if overdue_count > 0:
        data["audit_findings"] = [{
            "severity": "CRITICAL",
            "description": f"{overdue_count} batch(es) have exceeded the 90-day storage limit",
            "recommendation": "Immediate disposal action required - contact licensed disposal facility",
        }]
    else:
        data["audit_findings"] = []
    
    return data


def _get_fleet_data(session: Any, period_from: str | None, period_to: str | None) -> dict[str, Any]:
    """Fetch fleet utilization data."""
    from sqlalchemy import text
    
    # Vehicle counts by status
    status_rows = session.execute(text("""
        SELECT status, COUNT(*) as cnt
        FROM vehicles
        WHERE status != 'retired'
        GROUP BY status
    """)).fetchall()
    
    status_counts = {r[0]: r[1] for r in status_rows}
    total_vehicles = sum(status_counts.values())
    
    data = {
        "total_vehicles": total_vehicles,
        "active_vehicles": total_vehicles,
        "total_jobs": sum(status_counts.values()),  # Placeholder
        "utilization_rate": round((status_counts.get('on_trip', 0) / total_vehicles * 100), 1) if total_vehicles > 0 else 0,
    }
    
    # Status breakdown
    data["status_breakdown"] = [
        {"status": s, "count": c, "percentage": round(c/total_vehicles*100, 1) if total_vehicles > 0 else 0, "description": f"Vehicles {s}"}
        for s, c in status_counts.items()
    ]
    
    # Vehicle performance details
    vehicle_rows = session.execute(text("""
        SELECT 
            v.registration,
            v.vehicle_type,
            v.status,
            v.odometer_km,
            v.next_service_date,
            u.full_name as driver
        FROM vehicles v
        LEFT JOIN users u ON v.assigned_driver_id = u.id
        WHERE v.status != 'retired'
        ORDER BY v.registration
    """)).fetchall()
    
    data["vehicle_performance"] = [
        {
            "registration": r[0],
            "type": r[1],
            "status": r[2],
            "odometer_km": float(r[3]) if r[3] else 0,
            "driver": r[5] or "Unassigned",
            "jobs_completed": 0,  # Placeholder - would join with jobs table
            "kilometers": 0,
            "fuel_used": 0,
            "efficiency": 0,
        }
        for r in vehicle_rows
    ]
    
    # Upcoming maintenance
    maint_rows = session.execute(text("""
        SELECT 
            v.registration,
            v.next_service_date,
            v.odometer_km
        FROM vehicles v
        WHERE v.next_service_date IS NOT NULL
        AND v.status != 'retired'
        ORDER BY v.next_service_date
        LIMIT 20
    """)).fetchall()
    
    from datetime import date, timedelta
    today = date.today()
    
    data["upcoming_maintenance"] = []
    for r in maint_rows:
        due_date = r[1]
        days_until = (due_date - today).days if due_date else 0
        data["upcoming_maintenance"].append({
            "vehicle_registration": r[0],
            "service_type": "Scheduled Service",
            "due_date": str(due_date),
            "days_until": days_until,
            "current_odometer": float(r[2]) if r[2] else 0,
            "status": "overdue" if days_until < 0 else "scheduled",
        })
    
    # Driver analysis placeholder
    data["driver_analysis"] = []
    
    # Fuel analysis placeholder
    data["fuel_analysis"] = []
    data["total_distance_km"] = 0
    data["total_fuel_liters"] = 0
    data["fleet_avg_efficiency"] = 0
    data["total_fuel_cost"] = 0
    
    # Maintenance alerts
    overdue_maint = [m for m in data["upcoming_maintenance"] if m["days_until"] < 0]
    data["maintenance_alerts"] = [
        {"vehicle": m["vehicle_registration"], "message": "Service overdue", "recommended_action": "Schedule immediately"}
        for m in overdue_maint[:5]
    ]
    
    return data


def _get_invoice_data(session: Any, period_from: str | None, period_to: str | None) -> dict[str, Any]:
    """Fetch invoice ageing data."""
    from sqlalchemy import text
    from datetime import date
    
    today = date.today()
    
    # Summary
    row = session.execute(text("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN status = 'paid' THEN 1 ELSE 0 END) as paid,
            SUM(CASE WHEN status != 'paid' AND is_void = FALSE THEN 1 ELSE 0 END) as unpaid,
            COALESCE(SUM(CASE WHEN status != 'paid' AND is_void = FALSE THEN total_myr - paid_amount_myr ELSE 0 END), 0) as outstanding
        FROM invoices
    """)).first()
    
    data = {
        "total_invoices": row[0] if row else 0,
        "paid_invoices": row[1] if row else 0,
        "unpaid_count": row[2] if row else 0,
        "total_outstanding": float(row[3]) if row else 0,
    }
    
    # Ageing buckets
    unpaid_rows = session.execute(text("""
        SELECT 
            i.id,
            i.invoice_number,
            c.company_name as client,
            i.issue_date,
            i.due_date,
            i.total_myr,
            i.paid_amount_myr,
            i.status
        FROM invoices i
        LEFT JOIN clients c ON i.client_id = c.id
        WHERE i.status != 'paid' AND i.is_void = FALSE
        ORDER BY i.due_date
    """)).fetchall()
    
    buckets = {
        "current": {"count": 0, "amount": 0.0},
        "days_31_60": {"count": 0, "amount": 0.0},
        "days_61_90": {"count": 0, "amount": 0.0},
        "over_90": {"count": 0, "amount": 0.0},
    }
    
    unpaid_invoices = []
    client_ar = {}
    
    for r in unpaid_rows:
        due_date = r[4]
        days_overdue = (today - due_date).days if due_date else 0
        outstanding = float(r[5]) - float(r[6]) if r[5] and r[6] else 0
        
        # Bucket classification
        if days_overdue <= 30:
            buckets["current"]["count"] += 1
            buckets["current"]["amount"] += outstanding
        elif days_overdue <= 60:
            buckets["days_31_60"]["count"] += 1
            buckets["days_31_60"]["amount"] += outstanding
        elif days_overdue <= 90:
            buckets["days_61_90"]["count"] += 1
            buckets["days_61_90"]["amount"] += outstanding
        else:
            buckets["over_90"]["count"] += 1
            buckets["over_90"]["amount"] += outstanding
        
        unpaid_invoices.append({
            "invoice_number": r[1],
            "client_name": r[2] or "Unknown",
            "invoice_date": str(r[3]),
            "due_date": str(r[4]),
            "days_overdue": days_overdue,
            "total_amount": float(r[5]) if r[5] else 0,
            "paid_amount": float(r[6]) if r[6] else 0,
            "outstanding_amount": outstanding,
            "status": r[7],
        })
        
        # Client AR summary
        client = r[2] or "Unknown"
        if client not in client_ar:
            client_ar[client] = {"total": 0, "paid": 0, "unpaid": 0, "outstanding": 0, "oldest_overdue": 0}
        client_ar[client]["total"] += 1
        client_ar[client]["unpaid"] += 1
        client_ar[client]["outstanding"] += outstanding
        if days_overdue > client_ar[client]["oldest_overdue"]:
            client_ar[client]["oldest_overdue"] = days_overdue
    
    # Calculate percentages
    total_ar = data["total_outstanding"]
    for k in buckets:
        buckets[k]["percentage"] = round(buckets[k]["amount"] / total_ar * 100, 1) if total_ar > 0 else 0
    
    data["ageing_buckets"] = buckets
    data["unpaid_invoices"] = unpaid_invoices[:50]  # Limit for PDF
    
    # Client AR summary
    data["client_ar_summary"] = [
        {
            "name": name,
            "total_invoices": info["total"],
            "paid_count": info["paid"],
            "unpaid_count": info["unpaid"],
            "total_outstanding": info["outstanding"],
            "oldest_overdue_days": info["oldest_overdue"],
            "risk_level": "high" if info["oldest_overdue"] > 90 else ("medium" if info["oldest_overdue"] > 60 else "low"),
        }
        for name, info in sorted(client_ar.items(), key=lambda x: x[1]["outstanding"], reverse=True)[:20]
    ]
    
    # Recently paid
    paid_rows = session.execute(text("""
        SELECT 
            i.invoice_number,
            c.company_name as client,
            i.total_myr,
            i.issue_date,
            i.updated_at as paid_date
        FROM invoices i
        LEFT JOIN clients c ON i.client_id = c.id
        WHERE i.status = 'paid'
        ORDER BY i.updated_at DESC
        LIMIT 10
    """)).fetchall()
    
    data["recently_paid"] = [
        {
            "invoice_number": r[0],
            "client_name": r[1] or "Unknown",
            "total_amount": float(r[2]) if r[2] else 0,
            "invoice_date": str(r[3]),
            "paid_date": str(r[4]) if r[4] else "",
            "days_to_pay": (r[4].date() - r[3]).days if r[4] and r[3] else 0,
            "payment_method": "Bank Transfer",
        }
        for r in paid_rows
    ]
    
    # Metrics placeholders
    data["current_dso"] = 45
    data["previous_dso"] = 42
    data["dso_change"] = 3
    data["current_collection_rate"] = 95.0
    data["previous_collection_rate"] = 97.0
    data["collection_rate_change"] = -2.0
    data["current_bad_debt_ratio"] = 0.5
    data["previous_bad_debt_ratio"] = 0.3
    data["bad_debt_change"] = 0.2
    
    # Action items
    data["action_items"] = [
        {
            "priority": "HIGH",
            "description": f"Contact client regarding overdue invoice",
            "client": inv["client_name"],
            "amount": inv["outstanding_amount"],
        }
        for inv in unpaid_invoices[:3] if inv["days_overdue"] > 90
    ]
    
    return data


def _get_esg_data(session: Any, period_from: str | None, period_to: str | None, client_id: str | None) -> dict[str, Any]:
    """Fetch ESG monthly data."""
    from sqlalchemy import text
    
    where_clause = "WHERE 1=1"
    params: dict[str, Any] = {}
    if period_from:
        where_clause += " AND recorded_at >= :period_from"
        params["period_from"] = period_from
    if period_to:
        where_clause += " AND recorded_at <= :period_to"
        params["period_to"] = period_to
    if client_id:
        where_clause += " AND client_id = :client_id"
        params["client_id"] = client_id
    
    # Recyclable totals
    row = session.execute(text(f"""
        SELECT 
            COUNT(*) as records,
            COALESCE(SUM(total_recyclable_kg), 0) as total_kg
        FROM recyclable_records
        {where_clause}
    """), params).first()
    
    total_recycled_kg = float(row[1]) if row else 0
    total_diverted_tonnes = total_recycled_kg / 1000
    
    # Carbon calculations (simplified)
    ef_landfill = 0.5  # tCO2e per tonne diverted from landfill
    ef_recycling = 0.3  # tCO2e per tonne recycled
    co2_avoided = total_diverted_tonnes * (ef_landfill + ef_recycling)
    
    data = {
        "total_diverted_tonnes": round(total_diverted_tonnes, 2),
        "recycling_rate": 85.0,  # Placeholder
        "co2_avoided": round(co2_avoided, 2),
        "landfill_diversion": 90.0,  # Placeholder
        "report_month": period_from[:7] if period_from else "Current",  # YYYY-MM
    }
    
    # SDG contributions
    data["sdg_12_contribution"] = round(total_diverted_tonnes, 2)
    data["ocean_plastic_kg"] = 0  # Placeholder
    
    # Material breakdown from JSON
    material_rows = session.execute(text(f"""
        SELECT material_breakdown
        FROM recyclable_records
        {where_clause}
    """), params).fetchall()
    
    material_totals = {}
    for r in material_rows:
        if r[0] and isinstance(r[0], dict):
            for key, value in r[0].items():
                if key.endswith('_kg'):
                    material_type = key[:-3].upper()
                    material_totals[material_type] = material_totals.get(material_type, 0) + float(value)
    
    total_materials = sum(material_totals.values())
    data["material_breakdown"] = [
        {
            "type": mtype,
            "weight_kg": weight,
            "percentage": round(weight / total_materials * 100, 1) if total_materials > 0 else 0,
            "destination": "Recycling Facility",
        }
        for mtype, weight in sorted(material_totals.items(), key=lambda x: x[1], reverse=True)
    ]
    data["total_recyclable_kg"] = total_materials
    
    # Emission factors display
    data["ef_landfill"] = ef_landfill
    data["ef_recycling"] = ef_recycling
    data["ef_transport"] = 0.05
    data["scope3_baseline"] = round(total_diverted_tonnes * ef_landfill, 2)
    data["scope3_avoided"] = round(co2_avoided, 2)
    data["scope3_net"] = round(co2_avoided, 2)
    
    # Certificates issued placeholder
    data["certificates_issued"] = []
    
    # ESG scorecard placeholders
    data["carbon_intensity"] = 35
    data["client_satisfaction"] = 4.7
    data["compliance_score"] = 100
    
    return data


def _get_recyclables_data(session: Any, period_from: str | None, period_to: str | None, client_id: str | None) -> dict[str, Any]:
    """Fetch recyclables recovery data."""
    from sqlalchemy import text
    
    where_clause = "WHERE 1=1"
    params: dict[str, Any] = {}
    if period_from:
        where_clause += " AND r.recorded_at >= :period_from"
        params["period_from"] = period_from
    if period_to:
        where_clause += " AND r.recorded_at <= :period_to"
        params["period_to"] = period_to
    if client_id:
        where_clause += " AND r.client_id = :client_id"
        params["client_id"] = client_id
    
    # Summary totals
    row = session.execute(text(f"""
        SELECT 
            COUNT(*) as records,
            COALESCE(SUM(r.total_recyclable_kg), 0) as total_kg
        FROM recyclable_records r
        {where_clause}
    """), params).first()
    
    total_recovered_kg = float(row[1]) if row else 0
    
    # Buyer count
    buyer_row = session.execute(text("SELECT COUNT(*) FROM downstream_buyers WHERE is_active = TRUE")).first()
    
    data = {
        "total_recovered_kg": total_recovered_kg,
        "total_records": row[0] if row else 0,
        "downstream_buyer_count": buyer_row[0] if buyer_row else 0,
        "diversion_rate": 88.0,  # Placeholder
    }
    
    # Material breakdown
    material_rows = session.execute(text(f"""
        SELECT r.material_breakdown
        FROM recyclable_records r
        {where_clause}
    """), params).fetchall()
    
    material_totals = {}
    for r in material_rows:
        if r[0] and isinstance(r[0], dict):
            for key, value in r[0].items():
                if key.endswith('_kg'):
                    material_type = key[:-3].title()
                    material_totals[material_type] = material_totals.get(material_type, 0) + float(value)
    
    total_materials = sum(material_totals.values())
    data["material_breakdown"] = [
        {
            "type": mtype,
            "records": 0,  # Would need grouping query
            "quantity_kg": weight,
            "estimated_value": weight * 0.5,  # Placeholder RM 0.50/kg average
            "percentage": round(weight / total_materials * 100, 1) if total_materials > 0 else 0,
        }
        for mtype, weight in sorted(material_totals.items(), key=lambda x: x[1], reverse=True)
    ]
    data["total_estimated_value"] = sum(m["estimated_value"] for m in data["material_breakdown"])
    
    # Chain of custody records
    custody_rows = session.execute(text(f"""
        SELECT 
            r.id,
            c.company_name as client,
            r.recorded_at,
            r.total_recyclable_kg,
            b.company_name as buyer
        FROM recyclable_records r
        LEFT JOIN clients c ON r.client_id = c.id
        LEFT JOIN downstream_buyers b ON r.buyer_id = b.id
        {where_clause}
        ORDER BY r.recorded_at DESC
        LIMIT 50
    """), params).fetchall()
    
    data["custody_chain"] = [
        {
            "id": str(r[0]),
            "client_name": r[1] or "Unknown",
            "collection_date": str(r[2]),
            "quantity_kg": float(r[3]) if r[3] else 0,
            "buyer_name": r[4],
            "material_type": "Mixed Recyclables",
            "status": "delivered" if r[4] else "collected",
        }
        for r in custody_rows
    ]
    
    # Buyer summary
    buyer_rows = session.execute(text("""
        SELECT 
            company_name,
            material_types,
            license_number
        FROM downstream_buyers
        WHERE is_active = TRUE
    """)).fetchall()
    
    data["buyer_summary"] = [
        {
            "name": r[0],
            "material_types": ", ".join(r[1]) if r[1] else "Mixed",
            "deliveries": 0,  # Placeholder
            "total_tonnes": 0,  # Placeholder
            "revenue": 0,  # Placeholder
            "has_doe_license": bool(r[2]),
        }
        for r in buyer_rows
    ]
    
    # Client summary
    client_rows = session.execute(text(f"""
        SELECT 
            c.company_name,
            COUNT(*) as records,
            COALESCE(SUM(r.total_recyclable_kg), 0) as total_kg
        FROM recyclable_records r
        LEFT JOIN clients c ON r.client_id = c.id
        {where_clause}
        GROUP BY c.company_name
        ORDER BY total_kg DESC
        LIMIT 20
    """), params).fetchall()
    
    data["client_summary"] = [
        {
            "name": r[0] or "Unknown",
            "material_types": "Mixed",
            "total_recovered_kg": float(r[2]) if r[2] else 0,
            "diversion_rate": 85.0,  # Placeholder
            "certificate_count": r[1],
        }
        for r in client_rows
    ]
    
    # Carbon impact
    carbon_impact = []
    for m in data["material_breakdown"]:
        tonnes = m["quantity_kg"] / 1000
        # Simplified emission factors
        ef = {"Paper": 0.9, "Pet": 1.5, "Hdpe": 1.2, "Aluminium": 8.0, "Ferrous": 1.8, "Glass": 0.3}.get(m["type"], 0.5)
        carbon_impact.append({
            "material_type": m["type"],
            "quantity_tonnes": tonnes,
            "emission_factor": ef,
            "carbon_avoided": round(tonnes * ef, 2),
        })
    data["carbon_impact"] = carbon_impact
    data["total_carbon_avoided"] = sum(c["carbon_avoided"] for c in carbon_impact)
    
    # Recovery trends placeholder
    data["recovery_trends"] = []
    
    return data


# =============================================================
# Individual report tasks — one explicit function per type.
# Do NOT use a factory/loop pattern — Celery requires each task
# to be a real named function at module level.
# =============================================================

@celery_app.task(
    bind=True,
    name="tasks.report_tasks.generate_esg_monthly_report",
    queue="reports",
    max_retries=2,
    default_retry_delay=30,
)
def generate_esg_monthly_report(self, **kwargs: Any) -> dict[str, Any]:
    """Generate monthly ESG performance report."""
    return _run_report(self, "esg_monthly", **kwargs)


@celery_app.task(
    bind=True,
    name="tasks.report_tasks.generate_tonnage_summary_report",
    queue="reports",
    max_retries=2,
    default_retry_delay=30,
)
def generate_tonnage_summary_report(self, **kwargs: Any) -> dict[str, Any]:
    """Generate waste tonnage summary report."""
    return _run_report(self, "tonnage_summary", **kwargs)


@celery_app.task(
    bind=True,
    name="tasks.report_tasks.generate_compliance_audit_report",
    queue="reports",
    max_retries=2,
    default_retry_delay=30,
)
def generate_compliance_audit_report(self, **kwargs: Any) -> dict[str, Any]:
    """Generate scheduled waste compliance audit report."""
    return _run_report(self, "compliance_audit", **kwargs)


@celery_app.task(
    bind=True,
    name="tasks.report_tasks.generate_fleet_utilisation_report",
    queue="reports",
    max_retries=2,
    default_retry_delay=30,
)
def generate_fleet_utilisation_report(self, **kwargs: Any) -> dict[str, Any]:
    """Generate fleet utilisation and cost report."""
    return _run_report(self, "fleet_utilisation", **kwargs)


@celery_app.task(
    bind=True,
    name="tasks.report_tasks.generate_recyclables_recovery_report",
    queue="reports",
    max_retries=2,
    default_retry_delay=30,
)
def generate_recyclables_recovery_report(self, **kwargs: Any) -> dict[str, Any]:
    """Generate recyclables recovery and traceability report."""
    return _run_report(self, "recyclables_recovery", **kwargs)


@celery_app.task(
    bind=True,
    name="tasks.report_tasks.generate_invoice_ageing_report",
    queue="reports",
    max_retries=2,
    default_retry_delay=30,
)
def generate_invoice_ageing_report(self, **kwargs: Any) -> dict[str, Any]:
    """Generate accounts-receivable ageing report."""
    return _run_report(self, "invoice_ageing", **kwargs)
