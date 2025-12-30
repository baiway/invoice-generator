"""
Event processing and classification logic.

This module handles matching Google Calendar events to students,
including event classification and student name extraction for
different client types.
"""

import pandas as pd
from typing import Any, Optional

from src.constants import PMT_PREFIX, BAC_PREFIX, TUTORING_PREFIX
from src.models import StudentInfo, ContactDetails
from src.logging_config import get_logger

logger = get_logger(__name__)


# Event Classification Functions

def classify_event(
    event_title: str,
    attendees: list[dict[str, Any]],
) -> tuple[str, Optional[str]]:
    """
    Classify a calendar event and extract the student name.

    Args:
        event_title: The title/summary of the calendar event
        attendees: List of event attendees with 'email' and 'self' fields

    Returns:
        A tuple of (event_type, student_name) where:
        - event_type: One of 'email', 'pmt', 'blue_education', 'in_person', 'unknown'
        - student_name: Extracted student name or None if not extractable

    Examples:
        >>> classify_event("PMT - John", [{"self": True}])
        ('pmt', None)

        >>> classify_event("Oscar Sun BAC", [{"self": True}])
        ('blue_education', 'Oscar Sun')

        >>> classify_event("Tutoring Alice", [{"self": True}])
        ('in_person', 'Alice')
    """
    # Check if event has attendees other than yourself
    just_me = all(attendee.get("self", False) for attendee in attendees)

    # Email-based matching (attendees present)
    if not just_me:
        return ("email", None)  # Name extracted via match_attendee_email()

    # PMT events should be skipped (payment handled by agency)
    if PMT_PREFIX in event_title:
        return ("pmt", None)

    # Blue Education events: "FirstName LastName BAC [other text]"
    if BAC_PREFIX in event_title:
        student_name = extract_blue_education_name(event_title)
        return ("blue_education", student_name)

    # In-person tutoring: "Tutoring StudentName"
    if event_title.startswith(TUTORING_PREFIX):
        student_name = extract_in_person_name(event_title)
        return ("in_person", student_name)

    # Unknown event format
    return ("unknown", None)


def extract_blue_education_name(event_title: str) -> str:
    """
    Extract student name from Blue Education event title.

    Blue Education events are formatted as "FirstName LastName BAC [additional info]"

    Args:
        event_title: Event title containing "BAC"

    Returns:
        Student name (first and last name only)

    Examples:
        >>> extract_blue_education_name("Oscar Sun BAC Maths Tutoring")
        'Oscar Sun'
    """
    # Split on whitespace and find "BAC" position
    parts = event_title.split()

    try:
        bac_index = parts.index(BAC_PREFIX)
        # Student name is the two words before "BAC"
        if bac_index >= 2:
            return f"{parts[bac_index - 2]} {parts[bac_index - 1]}"
    except (ValueError, IndexError):
        pass

    # Fallback: if BAC not found as separate word or not enough parts,
    # try taking first two words (legacy format support)
    if len(parts) >= 2:
        return f"{parts[0]} {parts[1]}"

    return ""


def extract_in_person_name(event_title: str) -> str:
    """
    Extract student name from in-person tutoring event title.

    In-person events are formatted as "Tutoring StudentName"

    Args:
        event_title: Event title starting with "Tutoring "

    Returns:
        Student name (everything after "Tutoring ")

    Examples:
        >>> extract_in_person_name("Tutoring Alice Johnson")
        'Alice Johnson'
    """
    return event_title.split(TUTORING_PREFIX, 1)[1].strip()


def match_attendee_email(
    attendees: list[dict[str, Any]],
    student_data: dict[str, StudentInfo],
) -> Optional[str]:
    """
    Match event attendees to students via email addresses.

    Args:
        attendees: List of attendee dicts with 'email' field
        student_data: Dictionary mapping student names to StudentInfo models

    Returns:
        Student name if match found, None otherwise

    Examples:
        >>> from src.models import StudentInfo
        >>> students = {"Alice": StudentInfo(client_type="private", rate=50.0, emails=["alice@example.com"])}
        >>> match_attendee_email([{"email": "alice@example.com"}], students)
        'Alice'
    """
    for attendee in attendees:
        email = attendee.get("email")
        if not email:
            continue

        for student_name, info in student_data.items():
            if email in info.emails:
                return student_name

    return None


# Event Processing Functions

def attendee_match(
    attendees: list[dict[str, Any]],
    student_data: dict[str, StudentInfo],
) -> str:
    """Attempts to match Google Calendar attendees with email address in students.json.

    Args:
        attendees: List of event attendees
        student_data: Dictionary mapping student names to StudentInfo models

    Returns:
        Student name if found, empty string otherwise
    """
    student_name = match_attendee_email(attendees, student_data)

    if student_name:
        return student_name

    logger.warning(f"Attendees not found in students.json: {attendees}")
    return ""


def process_events(
    events: list[dict[str, Any]],
    student_data: dict[str, StudentInfo],
    students_to_invoice: list[str],
    contact_details: ContactDetails
) -> pd.DataFrame:
    """Match Google Calendar events to students and extract lesson information.

    This function processes calendar events and matches them to students using:
    - Email-based matching via attendee email addresses
    - Event title parsing for specific client types (Blue Education, in-person)
    - Filtering by student names if specified

    Args:
        events: List of Google Calendar events
        student_data: Dictionary mapping student names to StudentInfo models
        students_to_invoice: List of specific students to process (empty = all)
        contact_details: ContactDetails model with contact information

    Returns:
        DataFrame with columns: student, start, end, rate, client_type

    Notes:
        - PMT events are skipped (payments handled separately)
        - Blue Education events: "FirstName LastName BAC [...]"
        - In-person events: "Tutoring StudentName"
        - Events not matching any pattern are logged and skipped
    """
    my_email = contact_details.email  # Note: extracted but not currently used
    lessons: list[list[Any]] = []

    for event in events:
        event_title = event.get("summary", "")
        if not event_title:
            logger.debug("Skipping event with no title")
            continue

        attendees = event.get("attendees", [])
        student_name: Optional[str] = None

        # Classify event and extract student name
        event_type, extracted_name = classify_event(event_title, attendees)

        if event_type == "email":
            student_name = attendee_match(attendees, student_data)
        elif event_type == "pmt":
            logger.debug(f"Skipping PMT event: {event_title}")
            continue
        elif event_type in ("blue_education", "in_person"):
            student_name = extracted_name
        else:
            logger.warning(f"Skipping event with unexpected format: '{event_title}'")
            continue

        # Validate student name was extracted
        if not student_name:
            logger.warning(
                f"Could not extract student_name from '{event_title}'. Skipping event."
            )
            continue

        # Filter by students_to_invoice if specified
        if students_to_invoice and student_name not in students_to_invoice:
            continue

        # Extract student details from student_data
        try:
            student_info = student_data[student_name]
            rate = student_info.rate
            client_type = student_info.client_type
        except KeyError:
            logger.error(
                f"Student '{student_name}' not found in students.json. "
                f"Please add their details before generating invoices."
            )
            continue

        # Extract event times
        start = event["start"]["dateTime"]
        end = event["end"]["dateTime"]

        lessons.append([student_name, start, end, rate, client_type])

    df = pd.DataFrame(
        lessons, columns=["student", "start", "end", "rate", "client_type"]
    )

    # Convert start and end columns to datetime for proper handling
    df["start"] = pd.to_datetime(df["start"], utc=True)
    df["end"] = pd.to_datetime(df["end"], utc=True)

    logger.info(f"Processed {len(df)} lessons from {len(events)} events")
    return df
