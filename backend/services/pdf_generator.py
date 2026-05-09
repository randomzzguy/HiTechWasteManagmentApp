# =============================================================
# Hi-Tech Waste Management — PDF Generator Service
# WeasyPrint (HTML→PDF) with ReportLab fallback
# =============================================================

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def render_html_to_pdf(
    html_content: str,
    output_path: str,
    base_url: str | None = None,
) -> bool:
    """
    Render an HTML string to a PDF file using WeasyPrint.

    Args:
        html_content: Full HTML document string
        output_path:  Absolute path where the PDF should be written
        base_url:     Optional base URL for resolving relative CSS/image paths

    Returns:
        True on success, False on failure
    """
    try:
        from weasyprint import HTML  # type: ignore[import]

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        HTML(string=html_content, base_url=base_url).write_pdf(output_path)
        logger.info("PDF rendered via WeasyPrint: %s", output_path)
        return True

    except ImportError:
        logger.warning("WeasyPrint not available — falling back to ReportLab")
        return _render_text_pdf(html_content, output_path)
    except Exception as exc:
        logger.error("WeasyPrint PDF rendering failed: %s", exc)
        return False


def render_template_to_pdf(
    template_name: str,
    context: dict[str, Any],
    output_path: str,
    template_dir: str | None = None,
) -> bool:
    """
    Render a Jinja2 HTML template to PDF.

    Args:
        template_name: Template filename (e.g. 'recycling_certificate.html')
        context:       Template context variables
        output_path:   Output PDF path
        template_dir:  Directory containing templates (defaults to CERTIFICATE_TEMPLATE_DIR)

    Returns:
        True on success, False on failure
    """
    try:
        from jinja2 import Environment, FileSystemLoader  # type: ignore[import]
        from config import get_settings

        settings = get_settings()
        tpl_dir = template_dir or settings.CERTIFICATE_TEMPLATE_DIR

        env = Environment(
            loader=FileSystemLoader(tpl_dir),
            autoescape=True,
        )
        template = env.get_template(template_name)
        html_content = template.render(**context)

        return render_html_to_pdf(
            html_content=html_content,
            output_path=output_path,
            base_url=f"file://{tpl_dir}/",
        )

    except Exception as exc:
        logger.error(
            "Template PDF rendering failed for '%s': %s", template_name, exc
        )
        return False


def _render_text_pdf(content: str, output_path: str) -> bool:
    """
    Minimal ReportLab fallback — renders plain text content as a PDF.
    Used when WeasyPrint is unavailable.
    """
    try:
        from reportlab.lib.pagesizes import A4  # type: ignore[import]
        from reportlab.pdfgen import canvas as rl_canvas  # type: ignore[import]
        from reportlab.lib.units import cm  # type: ignore[import]

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        c = rl_canvas.Canvas(output_path, pagesize=A4)
        width, height = A4

        # Strip HTML tags for plain text rendering
        import re
        text = re.sub(r"<[^>]+>", " ", content)
        text = re.sub(r"\s+", " ", text).strip()

        c.setFont("Helvetica", 10)
        y = height - 2 * cm
        line_height = 0.5 * cm
        margin = 2 * cm
        max_width = width - 2 * margin

        # Word-wrap
        words = text.split()
        line = ""
        for word in words:
            test_line = f"{line} {word}".strip()
            if c.stringWidth(test_line, "Helvetica", 10) < max_width:
                line = test_line
            else:
                c.drawString(margin, y, line)
                y -= line_height
                line = word
                if y < 2 * cm:
                    c.showPage()
                    y = height - 2 * cm
                    c.setFont("Helvetica", 10)

        if line:
            c.drawString(margin, y, line)

        c.save()
        logger.info("PDF rendered via ReportLab fallback: %s", output_path)
        return True

    except Exception as exc:
        logger.error("ReportLab fallback PDF rendering failed: %s", exc)
        return False


def get_pdf_size(pdf_path: str) -> int:
    """Return the file size of a PDF in bytes, or 0 if not found."""
    try:
        return os.path.getsize(pdf_path)
    except OSError:
        return 0
