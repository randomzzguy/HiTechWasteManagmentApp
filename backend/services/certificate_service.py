# =============================================================
# Hi-Tech Waste Management - Certificate Service
# Generates PDF certificates for recycling, destruction, and ESG
# Uses Jinja2 templates for professional certificate generation
# =============================================================
from __future__ import annotations
import logging, os, uuid
from datetime import datetime, timezone
from typing import Any
from pathlib import Path

logger = logging.getLogger(__name__)

# Template directory
TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "certificates"


def _load_template(template_name: str) -> str:
    """Load a Jinja2 template from the templates directory."""
    template_path = TEMPLATE_DIR / template_name
    if template_path.exists():
        return template_path.read_text(encoding="utf-8")
    logger.warning(f"Template not found: {template_path}, using fallback")
    return None


def _render_jinja_template(template_str: str, **kwargs) -> str:
    """Render a Jinja2 template with the given context."""
    try:
        from jinja2 import Template
        template = Template(template_str)
        return template.render(**kwargs)
    except ImportError:
        logger.error("Jinja2 not installed, cannot render template")
        return None


def generate_recycling_certificate_pdf(
    certificate_id: str, record_id: str, client_name: str,
    material_breakdown: dict[str, Any], total_recyclable_kg: float,
    issued_at: datetime, issued_by_name: str, output_dir: str,
) -> str | None:
    """Generate a Certificate of Recycling PDF using Jinja2 template."""
    from config import get_settings
    settings = get_settings()
    os.makedirs(output_dir, exist_ok=True)
    pdf_path = os.path.join(output_dir, f"recycling_{certificate_id}.pdf")

    # Prepare materials list for template
    materials = []
    for mat, kg in material_breakdown.items():
        if kg and float(kg) > 0:
            materials.append((mat.replace('_kg', '').title(), float(kg)))
    
    # Load and render Jinja2 template
    template_str = _load_template("recycling_certificate.html")
    if template_str:
        html = _render_jinja_template(
            template_str,
            certificate_number=f"REC-{certificate_id[:8].upper()}",
            client_name=client_name,
            issued_date=issued_at.strftime("%d %B %Y"),
            issued_by_name=issued_by_name,
            materials=materials,
            total_weight=total_recyclable_kg
        )
        if html:
            return _render_pdf(html, pdf_path)
    
    # Fallback to basic HTML if template fails
    logger.warning("Using fallback HTML for recycling certificate")
    return _generate_recycling_certificate_fallback(
        certificate_id, client_name, material_breakdown, 
        total_recyclable_kg, issued_at, issued_by_name, pdf_path
    )


def generate_destruction_certificate_pdf(
    certificate_id: str, destruction_job_id: str,
    goods_description: str, quantity_units: int | None, weight_kg: float | None,
    destruction_method: str, destruction_date: str, destruction_location: str,
    witness_hitech_name: str, witness_client_name: str, witness_client_designation: str,
    reason_codes: list[str], client_name: str, issued_at: datetime, output_dir: str,
) -> str | None:
    """Generate a Certificate of Destruction PDF using Jinja2 template."""
    os.makedirs(output_dir, exist_ok=True)
    pdf_path = os.path.join(output_dir, f"destruction_{certificate_id}.pdf")

    reason_str = ", ".join(r.replace("_", " ").title() for r in (reason_codes or []))
    qty_str = f"{quantity_units:,} units" if quantity_units else "N/A"
    weight_str = f"{weight_kg:,.1f} kg" if weight_kg else "N/A"
    method_str = destruction_method.replace("_", " ").title()

    # Load and render Jinja2 template
    template_str = _load_template("destruction_certificate.html")
    if template_str:
        html = _render_jinja_template(
            template_str,
            certificate_number=f"DEST-{certificate_id[:8].upper()}",
            client_name=client_name,
            destruction_date=destruction_date,
            destruction_location=destruction_location,
            goods_description=goods_description,
            quantity=qty_str,
            weight=weight_str,
            destruction_method=method_str,
            reason=reason_str or "N/A",
            witness_hitech=witness_hitech_name,
            witness_client=witness_client_name,
            witness_client_designation=witness_client_designation
        )
        if html:
            return _render_pdf(html, pdf_path)
    
    # Fallback to basic HTML if template fails
    logger.warning("Using fallback HTML for destruction certificate")
    return _generate_destruction_certificate_fallback(
        certificate_id, client_name, goods_description, quantity_units, 
        weight_kg, destruction_method, destruction_date, destruction_location,
        witness_hitech_name, witness_client_name, witness_client_designation,
        reason_codes, issued_at, pdf_path
    )


def _render_pdf(html: str, output_path: str) -> str | None:
    """Render HTML to PDF using WeasyPrint, falling back to ReportLab."""
    try:
        from weasyprint import HTML
        HTML(string=html).write_pdf(output_path)
        logger.info("Certificate PDF generated: %s", output_path)
        return output_path
    except ImportError:
        pass
    except Exception as exc:
        logger.warning("WeasyPrint failed: %s — trying ReportLab", exc)

    try:
        import re
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas as rl_canvas
        from reportlab.lib.units import cm

        text_content = re.sub(r"<[^>]+>", " ", html)
        text_content = re.sub(r"\s+", " ", text_content).strip()

        c = rl_canvas.Canvas(output_path, pagesize=A4)
        width, height = A4
        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(width/2, height - 2*cm, "HI-TECH WASTE MANAGEMENT SDN. BHD.")
        c.setFont("Helvetica", 10)
        y = height - 3.5*cm
        for line in text_content[:2000].split(". "):
            if y < 2*cm:
                c.showPage(); y = height - 2*cm; c.setFont("Helvetica", 10)
            c.drawString(2*cm, y, line.strip()[:100])
            y -= 0.5*cm
        c.save()
        logger.info("Certificate PDF generated (ReportLab): %s", output_path)
        return output_path
    except Exception as exc:
        logger.error("PDF generation failed entirely: %s", exc)
        return None


# =============================================================
# Fallback certificate generation functions
# Used when Jinja2 templates are unavailable
# =============================================================

def _generate_recycling_certificate_fallback(
    certificate_id: str, client_name: str,
    material_breakdown: dict[str, Any], total_recyclable_kg: float,
    issued_at: datetime, issued_by_name: str, pdf_path: str
) -> str | None:
    """Generate a basic Certificate of Recycling PDF (fallback)."""
    materials_rows = ""
    for mat, kg in material_breakdown.items():
        if kg and float(kg) > 0:
            materials_rows += f'<tr><td>{mat.replace("_kg","").title()}</td><td>{float(kg):,.1f} kg</td></tr>'

    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 50px; color: #222; }}
        .header {{ text-align: center; border-bottom: 3px solid #1a5c2a; padding-bottom: 20px; margin-bottom: 30px; }}
        h1 {{ color: #1a5c2a; font-size: 22px; margin: 0; }}
        h2 {{ color: #555; font-size: 14px; font-weight: normal; margin: 5px 0 0; }}
        .cert-title {{ font-size: 28px; font-weight: bold; color: #1a5c2a; text-align: center; margin: 20px 0; }}
        table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
        th {{ background: #1a5c2a; color: white; padding: 8px 12px; text-align: left; }}
        td {{ padding: 7px 12px; border-bottom: 1px solid #ddd; }}
        .total-row td {{ font-weight: bold; background: #e8f5e9; }}
        .sig-block {{ margin-top: 50px; display: flex; justify-content: space-between; }}
        .sig-line {{ border-top: 1px solid #333; width: 200px; padding-top: 5px; font-size: 12px; }}
        .footer {{ margin-top: 40px; font-size: 10px; color: #888; text-align: center; border-top: 1px solid #ddd; padding-top: 10px; }}
    </style></head><body>
    <div class="header">
        <h1>HI-TECH WASTE MANAGEMENT SDN. BHD.</h1>
        <h2>Shah Alam, Selangor, Malaysia | DOE Licensed Waste Contractor</h2>
    </div>
    <div class="cert-title">CERTIFICATE OF RECYCLING</div>
    <table><tbody>
        <tr><td><strong>Certificate No.</strong></td><td>REC-{certificate_id[:8].upper()}</td></tr>
        <tr><td><strong>Client</strong></td><td>{client_name}</td></tr>
        <tr><td><strong>Date Issued</strong></td><td>{issued_at.strftime("%d %B %Y")}</td></tr>
        <tr><td><strong>Issued By</strong></td><td>{issued_by_name}</td></tr>
        <tr><td><strong>Total Recyclable Weight</strong></td><td><strong>{total_recyclable_kg:,.1f} kg</strong></td></tr>
    </tbody></table>
    <h3>Material Breakdown</h3>
    <table><thead><tr><th>Material</th><th>Weight</th></tr></thead>
    <tbody>{materials_rows}
    <tr class="total-row"><td>TOTAL</td><td>{total_recyclable_kg:,.1f} kg</td></tr>
    </tbody></table>
    <p>This certifies that the above recyclable materials were collected from the client premises and
    delivered to licensed downstream buyers for recycling in accordance with Malaysian environmental regulations.</p>
    <div class="sig-block">
        <div><div class="sig-line">Authorised Signatory<br>Hi-Tech Waste Management Sdn. Bhd.</div></div>
        <div><div class="sig-line">Client Representative</div></div>
    </div>
    <div class="footer">Hi-Tech Waste Management Sdn. Bhd. | ROC: 123456-X | DOE License: SW-2024-001<br>
    This certificate is valid only with the company stamp and authorised signature.</div>
    </body></html>"""

    return _render_pdf(html, pdf_path)


def _generate_destruction_certificate_fallback(
    certificate_id: str, client_name: str,
    goods_description: str, quantity_units: int | None, weight_kg: float | None,
    destruction_method: str, destruction_date: str, destruction_location: str,
    witness_hitech_name: str, witness_client_name: str, witness_client_designation: str,
    reason_codes: list[str], issued_at: datetime, pdf_path: str
) -> str | None:
    """Generate a basic Certificate of Destruction PDF (fallback)."""
    reason_str = ", ".join(r.replace("_", " ").title() for r in (reason_codes or []))
    qty_str = f"{quantity_units:,} units" if quantity_units else "N/A"
    weight_str = f"{weight_kg:,.1f} kg" if weight_kg else "N/A"
    method_str = destruction_method.replace("_", " ").title()

    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 50px; color: #222; }}
        .header {{ text-align: center; border-bottom: 3px solid #8b0000; padding-bottom: 20px; margin-bottom: 30px; }}
        h1 {{ color: #8b0000; font-size: 22px; margin: 0; }}
        h2 {{ color: #555; font-size: 14px; font-weight: normal; margin: 5px 0 0; }}
        .cert-title {{ font-size: 28px; font-weight: bold; color: #8b0000; text-align: center; margin: 20px 0; }}
        table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
        th {{ background: #8b0000; color: white; padding: 8px 12px; text-align: left; }}
        td {{ padding: 7px 12px; border-bottom: 1px solid #ddd; }}
        .sig-block {{ margin-top: 50px; display: flex; justify-content: space-between; }}
        .sig-line {{ border-top: 1px solid #333; width: 220px; padding-top: 5px; font-size: 12px; }}
        .footer {{ margin-top: 40px; font-size: 10px; color: #888; text-align: center; border-top: 1px solid #ddd; padding-top: 10px; }}
        .warning {{ background: #fff3cd; border: 1px solid #ffc107; padding: 10px; border-radius: 4px; font-size: 12px; margin: 15px 0; }}
    </style></head><body>
    <div class="header">
        <h1>HI-TECH WASTE MANAGEMENT SDN. BHD.</h1>
        <h2>Shah Alam, Selangor, Malaysia | Certified Destruction Services</h2>
    </div>
    <div class="cert-title">CERTIFICATE OF DESTRUCTION</div>
    <div class="warning">This certificate is a legally binding document. Alteration or falsification is a criminal offence.</div>
    <table><tbody>
        <tr><td><strong>Certificate No.</strong></td><td>DEST-{certificate_id[:8].upper()}</td></tr>
        <tr><td><strong>Client</strong></td><td>{client_name}</td></tr>
        <tr><td><strong>Date of Destruction</strong></td><td>{destruction_date}</td></tr>
        <tr><td><strong>Location</strong></td><td>{destruction_location}</td></tr>
        <tr><td><strong>Goods Description</strong></td><td>{goods_description}</td></tr>
        <tr><td><strong>Quantity</strong></td><td>{qty_str}</td></tr>
        <tr><td><strong>Weight</strong></td><td>{weight_str}</td></tr>
        <tr><td><strong>Destruction Method</strong></td><td>{method_str}</td></tr>
        <tr><td><strong>Reason for Destruction</strong></td><td>{reason_str or "N/A"}</td></tr>
        <tr><td><strong>Date Issued</strong></td><td>{issued_at.strftime("%d %B %Y")}</td></tr>
    </tbody></table>
    <p>We hereby certify that the above-described goods were destroyed in our presence on the date stated above
    using the {method_str} method. The destruction was carried out in compliance with all applicable Malaysian
    environmental and waste management regulations.</p>
    <div class="sig-block">
        <div>
            <div class="sig-line">{witness_hitech_name}<br>Hi-Tech Waste Management Sdn. Bhd.</div>
        </div>
        <div>
            <div class="sig-line">{witness_client_name}<br>{witness_client_designation}<br>{client_name}</div>
        </div>
    </div>
    <div class="footer">Hi-Tech Waste Management Sdn. Bhd. | ROC: 123456-X<br>
    Certificate No. DEST-{certificate_id[:8].upper()} | This certificate is valid only with company stamp and dual signatures.</div>
    </body></html>"""

    return _render_pdf(html, pdf_path)
