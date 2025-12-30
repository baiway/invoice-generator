"""
Pytest configuration and shared fixtures.
"""

from typing import Any
import pytest


@pytest.fixture
def sample_students_data() -> dict[str, Any]:
    """Sample student data for testing."""
    return {
        "Alice Smith": {
            "client_type": "private",
            "rate": 50,
            "emails": ["alice@example.com", "alice@school.edu"]
        },
        "Bob Jones": {
            "client_type": "tutors4u",
            "rate": 40,
            "emails": ["bob@example.com"]
        }
    }


@pytest.fixture
def sample_bank_details() -> dict[str, str]:
    """Sample bank details for testing."""
    return {
        "name": "Test User",
        "sort_code": "04-00-04",
        "account_number": "1234 5678",
        "bank": "Test Bank",
        "link": "https://example.com/pay?amount=amt",
        "QR_code": "https://example.com/qr?amount=amt"
    }


@pytest.fixture
def sample_contact_details() -> dict[str, str]:
    """Sample contact details for testing."""
    return {
        "mobile": "07123 456789",
        "email": "tutor@example.com"
    }


@pytest.fixture
def sample_calendar_events() -> list[dict[str, Any]]:
    """Sample Google Calendar events for testing."""
    return [
        {
            "summary": "Tutoring Alice Smith",
            "attendees": [{"email": "tutor@example.com", "self": True}],
            "start": {"dateTime": "2024-01-15T10:00:00Z"},
            "end": {"dateTime": "2024-01-15T11:00:00Z"}
        },
        {
            "summary": "Session with student",
            "attendees": [
                {"email": "tutor@example.com", "self": True},
                {"email": "bob@example.com", "self": False}
            ],
            "start": {"dateTime": "2024-01-16T14:00:00Z"},
            "end": {"dateTime": "2024-01-16T15:30:00Z"}
        },
        {
            "summary": "BAC Alice Smith Physics",
            "attendees": [{"email": "tutor@example.com", "self": True}],
            "start": {"dateTime": "2024-01-17T10:00:00Z"},
            "end": {"dateTime": "2024-01-17T11:00:00Z"}
        },
        {
            "summary": "PMT - Payment received",
            "attendees": [{"email": "tutor@example.com", "self": True}],
            "start": {"dateTime": "2024-01-18T10:00:00Z"},
            "end": {"dateTime": "2024-01-18T10:15:00Z"}
        }
    ]
