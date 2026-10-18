"""
Event processing and classification logic.

This module matches Google Calendar events to students, either by the
email addresses of invited attendees or, for events with no one else
invited, by the event title.
"""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from invoice_generator.models import StudentInfo
from invoice_generator.logging_config import get_logger

logger = get_logger(__name__)

# Title formats for events with no other attendees
PMT = re.compile(r"\bPMT\b")  # paid through the agency, so not invoiced
BLUE_EDUCATION = re.compile(r"^(\S.*?)\s+BAC\b")  # "Joe Bloggs BAC Maths"
IN_PERSON = re.compile(r"^Tutoring\s+(\S.*)")  # "Tutoring Joe Bloggs"


@dataclass(frozen=True)
class Lesson:
    """A single lesson, with timezone-aware start and end times."""

    start: datetime
    end: datetime

    @property
    def duration(self) -> timedelta:
        return self.end - self.start


def is_billable(event: dict[str, Any]) -> bool:
    """Return True if a Google Calendar event should be invoiced.

    Filters out cancelled events via two checks:
    1. `status == "cancelled"` — Google Calendar's tombstone marker.
    2. Summary prefixed with "Canceled:" or "Cancelled:" (case-insensitive) —
       Apple Calendar prepends this in some edge cases where the status
       doesn't propagate.

    The filter exists because Blue Education's `.ics` booking attachments
    lack the `METHOD` property required by RFC 5546 (iTIP), so Apple
    Calendar imports them with mixed semantics. Deleting one of these
    events from Calendar.app sometimes leaves a tombstone in Google
    Calendar rather than fully removing it, and that tombstone otherwise
    leaks into invoice generation.
    """
    if event.get("status") == "cancelled":
        return False
    summary = (event.get("summary") or "").lower()
    return not summary.startswith(("canceled:", "cancelled:"))


def identify_student(
    event: dict[str, Any],
    student_data: dict[str, StudentInfo],
) -> str | None:
    """Work out which student a calendar event is a lesson with.

    Events with invited attendees are matched by email address. Events
    with no one else invited are matched by title:
    - "PMT ..." events are paid through the agency, so are skipped
    - Blue Education: "FirstName LastName BAC [additional info]"
    - In-person: "Tutoring StudentName"

    Args:
        event: Google Calendar event
        student_data: Dictionary mapping student names to StudentInfo models

    Returns:
        The student's name, or None (with the reason logged) if the
        event is not a lesson that can be matched

    Examples:
        >>> identify_student({"summary": "Joe Bloggs BAC Maths"}, {})
        'Joe Bloggs'
        >>> identify_student({"summary": "Tutoring Alice"}, {})
        'Alice'
    """
    title = event.get("summary", "")
    attendees = event.get("attendees", [])

    if not all(attendee.get("self", False) for attendee in attendees):
        for attendee in attendees:
            for student_name, info in student_data.items():
                if attendee.get("email") in info.emails:
                    return student_name
        logger.warning(f"Attendees not found in students.json: {attendees}")
        return None

    if PMT.search(title):
        logger.debug(f"Skipping PMT event: {title}")
        return None

    match = BLUE_EDUCATION.match(title) or IN_PERSON.match(title)
    if match is None:
        logger.warning(f"Skipping event with unexpected format: '{title}'")
        return None
    return match.group(1).strip()


def process_events(
    events: list[dict[str, Any]],
    student_data: dict[str, StudentInfo],
    students_to_invoice: list[str],
) -> dict[str, list[Lesson]]:
    """Match Google Calendar events to students.

    Args:
        events: List of Google Calendar events, ordered by start time
        student_data: Dictionary mapping student names to StudentInfo models
        students_to_invoice: List of specific students to process (empty = all)

    Returns:
        Each student seen, mapped to their lessons in calendar order
    """
    lessons: dict[str, list[Lesson]] = {}

    for event in events:
        title = event.get("summary")
        if not is_billable(event):
            logger.debug(f"Skipping cancelled event: {title or '<no title>'}")
            continue
        if not title:
            logger.debug("Skipping event with no title")
            continue

        student_name = identify_student(event, student_data)
        if student_name is None:
            continue
        if students_to_invoice and student_name not in students_to_invoice:
            continue
        if student_name not in student_data:
            logger.error(
                f"Student '{student_name}' not found in students.json. "
                f"Please add their details before generating invoices."
            )
            continue

        # All-day events have a `date` rather than a `dateTime`
        start = event["start"].get("dateTime")
        end = event["end"].get("dateTime")
        if not (start and end):
            logger.warning(f"Skipping all-day event: '{title}'")
            continue

        lesson = Lesson(datetime.fromisoformat(start), datetime.fromisoformat(end))
        lessons.setdefault(student_name, []).append(lesson)

    count = sum(len(student_lessons) for student_lessons in lessons.values())
    logger.info(f"Processed {count} lessons from {len(events)} events")
    return lessons
