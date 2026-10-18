"""
Event processing and classification logic.

This module matches Google Calendar events to students, either by the
email addresses of invited attendees or, for events with no one else
invited, by the event title.
"""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from invoice_generator.models import StudentInfo
from invoice_generator.logging_config import get_logger

logger = get_logger(__name__)

# Title formats for events with no other attendees
PMT = re.compile(r"\bPMT\b")  # paid through the agency, so not invoiced
# "Joe Bloggs BAC Maths", "Joe Bloggs+BAC Maths": the name is everything
# before "BAC", whatever separates them
BLUE_EDUCATION = re.compile(r"^(.*?\w)\W*\bBAC\b")
IN_PERSON = re.compile(r"^Tutoring\s+(\S.*)")  # "Tutoring Joe"


class SkipReason(Enum):
    """Why an event that may be a lesson couldn't be invoiced, phrased to
    follow "Skipped events"."""

    UNEXPECTED_FORMAT = "with an unexpected format"
    UNKNOWN_ATTENDEES = "whose attendees aren't in students.json"
    UNKNOWN_STUDENT = "naming a student not in students.json"
    AMBIGUOUS_STUDENT = "that could be for more than one student"
    ALL_DAY = "lasting all day"


class Unmatched(Exception):
    """Raised when an event can't be matched to a student."""

    def __init__(self, reason: SkipReason, detail: str = "") -> None:
        super().__init__(f"{reason.value} ({detail})" if detail else reason.value)
        self.reason = reason
        self.detail = detail


@dataclass(frozen=True)
class SkippedEvent:
    """An event that may be a lesson but couldn't be invoiced."""

    event: dict[str, Any]
    reason: SkipReason
    detail: str = ""


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


def find_student(
    name: str,
    student_data: dict[str, StudentInfo],
) -> str:
    """Find the student a name from an event title refers to.

    The name can be a student's full name or the start of it, such as
    their first name, so long as that picks out only one student.
    Matching ignores case.

    Args:
        name: Name taken from an event title
        student_data: Dictionary mapping student names to StudentInfo models

    Returns:
        The student's full name as in `students.json`

    Raises:
        Unmatched: If no student, or more than one, matches

    Examples:
        >>> students = {"Joe Bloggs": StudentInfo(client_type="private", rate=50)}
        >>> find_student("Joe", students)
        'Joe Bloggs'
    """
    words = name.casefold().split()
    matches = [
        student for student in student_data
        if student.casefold().split()[:len(words)] == words
    ]
    # A full name wins over longer names it is the start of, so "Sam"
    # can still be told apart from "Sam Smith"
    exact = [student for student in matches if len(student.split()) == len(words)]
    candidates = exact or matches

    if len(candidates) == 1:
        return candidates[0]
    if candidates:
        raise Unmatched(
            SkipReason.AMBIGUOUS_STUDENT,
            f"'{name}' could be {' or '.join(candidates)}; use their full name",
        )
    raise Unmatched(SkipReason.UNKNOWN_STUDENT, name)


def identify_student(
    event: dict[str, Any],
    student_data: dict[str, StudentInfo],
) -> str | None:
    """Work out which student a calendar event is a lesson with.

    Events with invited attendees are matched by email address. Events
    with no one else invited are matched by title, using `find_student`:
    - "PMT ..." events are paid through the agency, so are skipped
    - Blue Education: "FirstName LastName BAC [additional info]"
    - In-person: "Tutoring StudentName"

    Args:
        event: Google Calendar event
        student_data: Dictionary mapping student names to StudentInfo models

    Returns:
        The student's name as in `students.json`, or None if the event is
        not a lesson to invoice

    Raises:
        Unmatched: If the event may be a lesson but can't be matched
    """
    title = event.get("summary", "")
    attendees = event.get("attendees", [])

    invitees = [attendee for attendee in attendees if not attendee.get("self", False)]
    if invitees:
        for attendee in invitees:
            for student_name, info in student_data.items():
                if attendee.get("email") in info.emails:
                    return student_name
        emails = [attendee.get("email", "<no email>") for attendee in invitees]
        raise Unmatched(SkipReason.UNKNOWN_ATTENDEES, ", ".join(emails))

    if PMT.search(title):
        logger.debug(f"Skipping PMT event: {title}")
        return None

    match = BLUE_EDUCATION.match(title) or IN_PERSON.match(title)
    if match is None:
        raise Unmatched(SkipReason.UNEXPECTED_FORMAT)
    return find_student(match.group(1), student_data)


def process_events(
    events: list[dict[str, Any]],
    student_data: dict[str, StudentInfo],
    students_to_invoice: list[str],
) -> tuple[dict[str, list[Lesson]], list[SkippedEvent]]:
    """Match Google Calendar events to students.

    Args:
        events: List of Google Calendar events, ordered by start time
        student_data: Dictionary mapping student names to StudentInfo models
        students_to_invoice: List of specific students to process (empty = all)

    Returns:
        Each student seen, mapped to their lessons in calendar order, and
        the events that may be lessons but couldn't be invoiced
    """
    lessons: dict[str, list[Lesson]] = {}
    skipped: list[SkippedEvent] = []

    for event in events:
        title = event.get("summary")
        if not is_billable(event):
            logger.debug(f"Skipping cancelled event: {title or '<no title>'}")
            continue
        if not title:
            logger.debug("Skipping event with no title")
            continue

        try:
            student_name = identify_student(event, student_data)
        except Unmatched as e:
            logger.info(f"Skipped '{title}' {e}")
            skipped.append(SkippedEvent(event, e.reason, e.detail))
            continue
        if student_name is None:
            continue
        if students_to_invoice and student_name not in students_to_invoice:
            continue

        # All-day events have a `date` rather than a `dateTime`
        start = event["start"].get("dateTime")
        end = event["end"].get("dateTime")
        if not (start and end):
            logger.info(f"Skipped '{title}' {SkipReason.ALL_DAY.value}")
            skipped.append(SkippedEvent(event, SkipReason.ALL_DAY))
            continue

        lesson = Lesson(datetime.fromisoformat(start), datetime.fromisoformat(end))
        lessons.setdefault(student_name, []).append(lesson)

    count = sum(len(student_lessons) for student_lessons in lessons.values())
    logger.info(f"Processed {count} lessons from {len(events)} events")
    return lessons, skipped
