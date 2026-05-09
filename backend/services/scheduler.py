# =============================================================
# Hi-Tech Waste Management — Scheduler Service
# Recurring job generation and schedule management utilities
# =============================================================

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

logger = logging.getLogger(__name__)


def get_next_occurrence(
    rrule_string: str,
    after: date | None = None,
) -> date | None:
    """
    Calculate the next occurrence date for an iCal RRULE string.

    Args:
        rrule_string: iCal RRULE, e.g. "FREQ=WEEKLY;BYDAY=MO,WE,FR"
        after:        Calculate next occurrence after this date (defaults to today)

    Returns:
        Next occurrence date, or None if the rule has no future occurrences
    """
    try:
        from dateutil.rrule import rrulestr  # type: ignore[import]
        from datetime import datetime

        start = after or date.today()
        # rrulestr needs a datetime, not a date
        start_dt = datetime(start.year, start.month, start.day)

        rule = rrulestr(rrule_string, dtstart=start_dt)
        next_dt = rule.after(start_dt)

        if next_dt is None:
            return None

        return next_dt.date()

    except Exception as exc:
        logger.warning("Could not parse RRULE '%s': %s", rrule_string, exc)
        return None


def should_generate_today(
    rrule_string: str,
    last_generated: date | None = None,
) -> bool:
    """
    Determine whether a recurring job template should generate a job today.

    Args:
        rrule_string:   iCal RRULE string
        last_generated: Date the last job was generated from this template

    Returns:
        True if a job should be generated today
    """
    today = date.today()
    next_date = get_next_occurrence(rrule_string, after=last_generated or today - timedelta(days=1))
    return next_date == today


def generate_jobs_from_templates(
    templates: list[dict[str, Any]],
    target_date: date | None = None,
) -> list[dict[str, Any]]:
    """
    Generate job records from active recurring templates for a target date.

    Args:
        templates:    List of recurring template dicts
        target_date:  Date to generate jobs for (defaults to today)

    Returns:
        List of job creation payloads for templates that should fire today
    """
    target = target_date or date.today()
    jobs_to_create: list[dict[str, Any]] = []

    for template in templates:
        if not template.get("is_active", True):
            continue

        rrule = template.get("recurrence_rule", "")
        if not rrule:
            continue

        last_generated_str = template.get("last_generated")
        last_generated: date | None = None
        if last_generated_str:
            try:
                last_generated = date.fromisoformat(str(last_generated_str))
            except ValueError:
                pass

        next_date = get_next_occurrence(rrule, after=last_generated)
        if next_date != target:
            continue

        # Build job creation payload from template
        job_payload = {
            "client_id": template.get("client_id"),
            "job_type": template.get("job_type", "general_collection"),
            "scheduled_date": target.isoformat(),
            "collection_address": template.get("collection_address"),
            "assigned_vehicle_id": template.get("assigned_vehicle_id"),
            "assigned_driver_id": template.get("assigned_driver_id"),
            "assigned_supervisor_id": template.get("assigned_supervisor_id"),
            "estimated_weight_kg": template.get("estimated_weight_kg"),
            "disposal_route": template.get("disposal_route"),
            "notes": f"[Auto-generated from template: {template.get('name', template.get('id', ''))}]",
            "_template_id": template.get("id"),
        }
        jobs_to_create.append(job_payload)

    logger.info(
        "Scheduler: %d jobs to generate for %s from %d templates",
        len(jobs_to_create),
        target.isoformat(),
        len(templates),
    )
    return jobs_to_create
