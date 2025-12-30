"""
Event classification and student name extraction logic.

This module handles the business logic for matching Google Calendar events
to students, including special handling for different client types.
"""

from typing import Optional, Any
from src.constants import PMT_PREFIX, BAC_PREFIX, TUTORING_PREFIX


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

        >>> classify_event("BAC John Smith", [{"self": True}])
        ('blue_education', 'John Smith')

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

    # Blue Education events: "BAC FirstName LastName [other text]"
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

    Blue Education events are formatted as "BAC FirstName LastName [additional info]"

    Args:
        event_title: Event title starting with "BAC"

    Returns:
        Student name (first and last name only)

    Examples:
        >>> extract_blue_education_name("BAC John Smith - Physics")
        'John Smith'
    """
    # Split on whitespace and take first two words after "BAC"
    parts = event_title.split()
    if len(parts) >= 3:  # At minimum: "BAC", "FirstName", "LastName"
        return f"{parts[1]} {parts[2]}"
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
    student_data: dict[str, Any],
) -> Optional[str]:
    """
    Match event attendees to students via email addresses.

    Args:
        attendees: List of attendee dicts with 'email' field
        student_data: Student database with email lists

    Returns:
        Student name if match found, None otherwise

    Examples:
        >>> students = {"Alice": {"emails": ["alice@example.com"]}}
        >>> match_attendee_email([{"email": "alice@example.com"}], students)
        'Alice'
    """
    for attendee in attendees:
        email = attendee.get("email")
        if not email:
            continue

        for student_name, info in student_data.items():
            if email in info.get("emails", []):
                return student_name

    return None
