# =============================================================
# Hi-Tech Waste Management — Notification Service
# Email (SMTP) and WhatsApp Business API notifications
# =============================================================

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def send_email(
    to: str | list[str],
    subject: str,
    body_html: str,
    body_text: str | None = None,
    cc: list[str] | None = None,
    attachments: list[dict[str, Any]] | None = None,
) -> bool:
    """
    Send an email via SMTP.

    Args:
        to:           Recipient email address(es)
        subject:      Email subject line
        body_html:    HTML body content
        body_text:    Plain-text fallback (auto-generated from HTML if omitted)
        cc:           Optional CC recipients
        attachments:  List of {filename, content_bytes, mime_type} dicts

    Returns:
        True on success, False on failure (logs the error)
    """
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    from config import get_settings

    settings = get_settings()

    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        logger.warning("SMTP credentials not configured — skipping email to %s", to)
        return False

    recipients = [to] if isinstance(to, str) else to

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_USER}>"
        msg["To"] = ", ".join(recipients)
        if cc:
            msg["Cc"] = ", ".join(cc)

        # Plain text fallback
        if body_text:
            msg.attach(MIMEText(body_text, "plain", "utf-8"))

        # HTML body
        msg.attach(MIMEText(body_html, "html", "utf-8"))

        # Attachments
        if attachments:
            from email.mime.base import MIMEBase
            from email import encoders

            for att in attachments:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(att["content_bytes"])
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    f'attachment; filename="{att["filename"]}"',
                )
                msg.attach(part)

        all_recipients = recipients + (cc or [])

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_USER, all_recipients, msg.as_string())

        logger.info("Email sent | to=%s | subject=%r", recipients, subject)
        return True

    except Exception as exc:
        logger.error("Failed to send email to %s: %s", recipients, exc)
        return False


async def send_whatsapp(
    phone_number: str,
    message: str,
    template_name: str | None = None,
    template_params: list[str] | None = None,
) -> bool:
    """
    Send a WhatsApp message via the WhatsApp Business API.

    Args:
        phone_number:    Recipient phone number in E.164 format (e.g. +60123456789)
        message:         Free-form message text (for non-template messages)
        template_name:   WhatsApp template name (for template messages)
        template_params: Template parameter values

    Returns:
        True on success, False on failure
    """
    import httpx
    from config import get_settings

    settings = get_settings()

    if not settings.WHATSAPP_API_URL or not settings.WHATSAPP_API_TOKEN:
        logger.warning(
            "WhatsApp API not configured — skipping message to %s", phone_number
        )
        return False

    try:
        headers = {
            "Authorization": f"Bearer {settings.WHATSAPP_API_TOKEN}",
            "Content-Type": "application/json",
        }

        if template_name:
            payload: dict[str, Any] = {
                "messaging_product": "whatsapp",
                "to": phone_number,
                "type": "template",
                "template": {
                    "name": template_name,
                    "language": {"code": "en_US"},
                    "components": [
                        {
                            "type": "body",
                            "parameters": [
                                {"type": "text", "text": p}
                                for p in (template_params or [])
                            ],
                        }
                    ],
                },
            }
        else:
            payload = {
                "messaging_product": "whatsapp",
                "to": phone_number,
                "type": "text",
                "text": {"body": message},
            }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                settings.WHATSAPP_API_URL,
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()

        logger.info("WhatsApp message sent | to=%s", phone_number)
        return True

    except Exception as exc:
        logger.error("Failed to send WhatsApp to %s: %s", phone_number, exc)
        return False


async def send_job_status_email(
    to: str,
    client_name: str,
    job_number: str,
    status: str,
    scheduled_date: str | None = None,
    driver_name: str | None = None,
    vehicle_reg: str | None = None,
) -> bool:
    """Send a job status update email to the client PIC."""
    status_labels = {
        'confirmed': 'Confirmed',
        'dispatched': 'Driver Dispatched',
        'in_progress': 'Collection In Progress',
        'completed': 'Collection Completed',
    }
    label = status_labels.get(status, status.replace('_', ' ').title())

    subject = f"Job {job_number} — {label}"
    body_html = f"""
    <html><body>
    <p>Dear {client_name},</p>
    <p>Your waste collection job <strong>{job_number}</strong> status has been updated to: <strong>{label}</strong>.</p>
    {"<p>Scheduled Date: " + scheduled_date + "</p>" if scheduled_date else ""}
    {"<p>Driver: " + driver_name + "</p>" if driver_name else ""}
    {"<p>Vehicle: " + vehicle_reg + "</p>" if vehicle_reg else ""}
    <p>Thank you for choosing Hi-Tech Waste Management.</p>
    <br><p>Hi-Tech Waste Management Sdn. Bhd.<br>Shah Alam, Selangor</p>
    </body></html>
    """
    return await send_email(to=to, subject=subject, body_html=body_html)


async def send_test_email(to: str) -> bool:
    """Send a test email to verify SMTP configuration."""
    return await send_email(
        to=to,
        subject="Hi-Tech Waste Management — Test Email",
        body_html="""
        <html><body>
        <p>This is a test email from Hi-Tech Waste Management platform.</p>
        <p>If you received this, your SMTP configuration is working correctly.</p>
        <br><p>Hi-Tech Waste Management Sdn. Bhd.</p>
        </body></html>
        """,
    )


def send_email_sync(
    to: str | list[str],
    subject: str,
    body_html: str,
) -> bool:
    """Synchronous wrapper for send_email — safe to call from Celery tasks."""
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from config import get_settings

    settings = get_settings()

    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        logger.warning("SMTP credentials not configured — skipping email to %s", to)
        return False

    recipients = [to] if isinstance(to, str) else to

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_USER}>"
        msg["To"] = ", ".join(recipients)
        msg.attach(MIMEText(body_html, "html", "utf-8"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_USER, recipients, msg.as_string())

        logger.info("Email sent (sync) | to=%s | subject=%r", recipients, subject)
        return True
    except Exception as exc:
        logger.error("Failed to send email (sync) to %s: %s", recipients, exc)
        return False


def send_compliance_deadline_alert(
    pic_email: str,
    pic_name: str,
    client_name: str,
    sw_code: str,
    days_remaining: int,
    storage_deadline: str,
    quantity_kg: float,
) -> None:
    """
    Send a compliance deadline alert email to a client's PIC.
    Queues the email as a Celery task to avoid blocking the request.
    """
    import asyncio

    subject = (
        f"{'URGENT: ' if days_remaining <= 2 else ''}Scheduled Waste Disposal Deadline — "
        f"{sw_code} ({days_remaining} days remaining)"
    )

    urgency = "URGENT" if days_remaining <= 2 else "REMINDER"
    body_html = f"""
    <html><body>
    <p>Dear {pic_name},</p>
    <p>This is a <strong>{urgency}</strong> notification regarding your scheduled waste batch.</p>
    <table border="1" cellpadding="8" style="border-collapse:collapse;">
        <tr><td><strong>Client</strong></td><td>{client_name}</td></tr>
        <tr><td><strong>SW Code</strong></td><td>{sw_code}</td></tr>
        <tr><td><strong>Quantity</strong></td><td>{quantity_kg:.1f} kg</td></tr>
        <tr><td><strong>Storage Deadline</strong></td><td>{storage_deadline}</td></tr>
        <tr><td><strong>Days Remaining</strong></td><td>{days_remaining}</td></tr>
    </table>
    <p>Please arrange for immediate disposal and ensure a consignment note is generated.</p>
    <p>Contact Hi-Tech Waste Management at your earliest convenience.</p>
    <br>
    <p>Hi-Tech Waste Management Sdn. Bhd.<br>Shah Alam, Selangor</p>
    </body></html>
    """

    # Fire-and-forget — don't await in sync context
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(
                send_email(to=pic_email, subject=subject, body_html=body_html)
            )
        else:
            loop.run_until_complete(
                send_email(to=pic_email, subject=subject, body_html=body_html)
            )
    except Exception as exc:
        logger.warning("Could not queue compliance alert email: %s", exc)


async def send_whatsapp_job_status(
    phone_number: str,
    client_name: str,
    job_number: str,
    new_status: str,
    driver_name: str | None = None,
    scheduled_date: str | None = None,
) -> bool:
    """
    Send a WhatsApp message to a client PIC when their job status changes.
    Only fires for meaningful status transitions (confirmed, dispatched,
    in_progress, completed).
    """
    status_messages = {
        "confirmed": (
            f"Hi {client_name}, your waste collection job *{job_number}* has been "
            f"*confirmed*."
            + (f" Scheduled for {scheduled_date}." if scheduled_date else "")
            + " — Hi-Tech Waste Management"
        ),
        "dispatched": (
            f"Hi {client_name}, your driver is on the way for job *{job_number}*."
            + (f" Driver: {driver_name}." if driver_name else "")
            + " — Hi-Tech Waste Management"
        ),
        "in_progress": (
            f"Hi {client_name}, waste collection for job *{job_number}* is now "
            f"*in progress*. — Hi-Tech Waste Management"
        ),
        "completed": (
            f"Hi {client_name}, waste collection job *{job_number}* has been "
            f"*completed*. Thank you for choosing Hi-Tech Waste Management."
        ),
    }

    message = status_messages.get(new_status)
    if not message:
        return False  # Don't notify for draft/invoiced transitions

    return await send_whatsapp(phone_number=phone_number, message=message)


async def send_whatsapp_sw_deadline_alert(
    phone_number: str,
    pic_name: str,
    client_name: str,
    sw_code: str,
    days_remaining: int,
    storage_deadline: str,
    quantity_kg: float,
) -> bool:
    """Send a WhatsApp alert for an approaching scheduled waste storage deadline."""
    urgency = "⚠️ URGENT" if days_remaining <= 5 else "📋 Reminder"
    message = (
        f"{urgency}: {client_name}\n"
        f"Scheduled waste *{sw_code}* ({quantity_kg:.0f} kg) must be disposed "
        f"by *{storage_deadline}* — *{days_remaining} days remaining*.\n"
        f"Please arrange disposal immediately.\n"
        f"— Hi-Tech Waste Management"
    )
    return await send_whatsapp(phone_number=phone_number, message=message)


async def send_whatsapp_contract_expiry_alert(
    phone_number: str,
    client_name: str,
    contract_end: str,
    days_remaining: int,
) -> bool:
    """Send a WhatsApp alert to management when a client contract is expiring."""
    message = (
        f"📋 Contract Renewal Reminder\n"
        f"Client: *{client_name}*\n"
        f"Contract expires: *{contract_end}* ({days_remaining} days remaining)\n"
        f"Please initiate renewal discussions.\n"
        f"— Hi-Tech Waste Management System"
    )
    return await send_whatsapp(phone_number=phone_number, message=message)
