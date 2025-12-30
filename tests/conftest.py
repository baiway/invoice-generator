"""
Pytest configuration and shared fixtures.
"""

from typing import Any
import pytest
from src.models import StudentInfo


@pytest.fixture
def sample_students_data() -> dict[str, StudentInfo]:
    """Sample student data for testing."""
    return {
        "Alice Smith": StudentInfo(
            client_type="private",
            rate=50.0,
            emails=["alice@example.com", "alice@school.edu"]
        ),
        "Bob Jones": StudentInfo(
            client_type="tutors4u",
            rate=40.0,
            emails=["bob@example.com"]
        )
    }


@pytest.fixture
def sample_bank_details() -> dict[str, str]:
    """Sample bank details for testing."""
    return {
        "name": "Test User",
        "sort_code": "04-00-04",
        "account_number": "1234 5678",
        "bank": "Test Bank",
        "link": "https://example.com/pay?amount={amount}",
        "QR_code": "https://example.com/qr?amount={amount}"
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
            "summary": "Alice Smith BAC Physics",
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


# ===================================================================
# Invalid Data Fixtures (for validation testing)
# ===================================================================

@pytest.fixture
def invalid_student_data_missing_rate() -> dict[str, Any]:
    """Student data missing required 'rate' field."""
    return {
        "Alice Smith": {
            "client_type": "private",
            "emails": ["alice@example.com"]
            # Missing 'rate' field
        }
    }


@pytest.fixture
def invalid_student_data_negative_rate() -> dict[str, Any]:
    """Student data with invalid negative rate."""
    return {
        "Alice Smith": {
            "client_type": "private",
            "rate": -50.0,  # Invalid: must be > 0
            "emails": ["alice@example.com"]
        }
    }


@pytest.fixture
def invalid_student_data_bad_email() -> dict[str, Any]:
    """Student data with malformed email."""
    return {
        "Alice Smith": {
            "client_type": "private",
            "rate": 50.0,
            "emails": ["not-an-email"]  # Invalid email format
        }
    }


@pytest.fixture
def invalid_bank_details_bad_sort_code() -> dict[str, Any]:
    """Bank details with invalid sort code."""
    return {
        "name": "Test User",
        "sort_code": "12345",  # Invalid: must be 6 digits
        "account_number": "12345678",
        "bank": "Test Bank",
        "link": "https://example.com/pay?amount={amount}",
        "QR_code": "https://example.com/qr?amount={amount}"
    }


@pytest.fixture
def invalid_bank_details_no_placeholder() -> dict[str, Any]:
    """Bank details missing {amount} placeholder in link."""
    return {
        "name": "Test User",
        "sort_code": "040004",
        "account_number": "12345678",
        "bank": "Test Bank",
        "link": "https://example.com/pay",  # Missing {amount}
        "QR_code": "https://example.com/qr?amount={amount}"
    }


@pytest.fixture
def invalid_contact_details_short_phone() -> dict[str, Any]:
    """Contact details with phone number too short."""
    return {
        "country_code": "+44",
        "phone_number": "123",  # Invalid: too short
        "email": "tutor@example.com"
    }


@pytest.fixture
def invalid_contact_details_bad_country_code() -> dict[str, Any]:
    """Contact details with invalid country code format."""
    return {
        "country_code": "44",  # Invalid: must start with +
        "phone_number": "1234567890",
        "email": "tutor@example.com"
    }


# ===================================================================
# File System Fixtures
# ===================================================================

@pytest.fixture
def temp_json_file(tmp_path):
    """Create a temporary JSON file for testing."""
    import json

    def _create_json(data: dict, filename: str = "test.json"):
        file_path = tmp_path / filename
        file_path.write_text(json.dumps(data))
        return str(file_path)

    return _create_json


@pytest.fixture
def malformed_json_file(tmp_path):
    """Create a file with malformed JSON."""
    file_path = tmp_path / "malformed.json"
    file_path.write_text("{invalid json content")
    return str(file_path)


# ===================================================================
# Google API Fixtures
# ===================================================================

@pytest.fixture
def mock_google_calendar_events() -> list[dict[str, Any]]:
    """Comprehensive Google Calendar events covering all patterns."""
    return [
        # Private student - email matching
        {
            "summary": "Tutoring Session",
            "attendees": [
                {"email": "tutor@example.com", "self": True},
                {"email": "alice@example.com", "self": False}
            ],
            "start": {"dateTime": "2024-01-15T10:00:00Z"},
            "end": {"dateTime": "2024-01-15T11:00:00Z"}
        },
        # Blue Education - title parsing
        {
            "summary": "Alice Smith BAC Physics",
            "attendees": [{"email": "tutor@example.com", "self": True}],
            "start": {"dateTime": "2024-01-16T14:00:00Z"},
            "end": {"dateTime": "2024-01-16T15:30:00Z"}
        },
        # In-person - title parsing
        {
            "summary": "Tutoring Bob Jones",
            "attendees": [{"email": "tutor@example.com", "self": True}],
            "start": {"dateTime": "2024-01-17T10:00:00Z"},
            "end": {"dateTime": "2024-01-17T11:00:00Z"}
        },
        # PMT - should be skipped
        {
            "summary": "PMT - Payment received",
            "attendees": [{"email": "tutor@example.com", "self": True}],
            "start": {"dateTime": "2024-01-18T10:00:00Z"},
            "end": {"dateTime": "2024-01-18T10:15:00Z"}
        },
        # Unknown format - should be logged and skipped
        {
            "summary": "Doctor appointment",
            "attendees": [{"email": "tutor@example.com", "self": True}],
            "start": {"dateTime": "2024-01-19T09:00:00Z"},
            "end": {"dateTime": "2024-01-19T09:30:00Z"}
        },
        # Event with no title - should be skipped
        {
            "summary": "",
            "attendees": [{"email": "tutor@example.com", "self": True}],
            "start": {"dateTime": "2024-01-20T10:00:00Z"},
            "end": {"dateTime": "2024-01-20T11:00:00Z"}
        }
    ]


@pytest.fixture
def mock_google_credentials():
    """Mock Google OAuth credentials."""
    from unittest.mock import MagicMock
    creds = MagicMock()
    creds.valid = True
    creds.expired = False
    creds.refresh_token = "mock_refresh_token"
    creds.to_json.return_value = '{"token": "mock_token"}'
    return creds


@pytest.fixture
def mock_google_service():
    """Mock Google Calendar service."""
    from unittest.mock import MagicMock
    service = MagicMock()
    return service


# ===================================================================
# Enhanced Data Fixtures
# ===================================================================

@pytest.fixture
def comprehensive_students_data() -> dict[str, StudentInfo]:
    """Comprehensive student data covering all client types."""
    return {
        "Alice Smith": StudentInfo(
            client_type="private",
            rate=50.0,
            emails=["alice@example.com", "alice@school.edu"]
        ),
        "Bob Jones": StudentInfo(
            client_type="tutors4u",
            rate=40.0,
            emails=["bob@example.com"]
        ),
        "Charlie Brown": StudentInfo(
            client_type="blue_education",
            rate=45.0,
            emails=[]  # Matched by event title only
        ),
        "Diana Prince": StudentInfo(
            client_type="private",
            rate=60.0,
            emails=["diana@example.com"]
        )
    }


@pytest.fixture
def sample_bank_details_model():
    """BankDetails Pydantic model instance."""
    from src.models import BankDetails
    return BankDetails(
        name="Test User",
        sort_code="04-00-04",  # Will be normalized to "040004"
        account_number="1234 5678",  # Will be normalized to "12345678"
        bank="Test Bank",
        link="https://example.com/pay?amount={amount}",
        QR_code="https://example.com/qr?amount={amount}"
    )


@pytest.fixture
def sample_contact_details_model():
    """ContactDetails Pydantic model instance."""
    from src.models import ContactDetails
    return ContactDetails(
        country_code="+44",
        phone_number="07123456789",  # Will be normalized to digits only
        email="tutor@example.com"
    )


@pytest.fixture
def sample_lessons_dataframe():
    """Sample lessons DataFrame for invoice generation."""
    import pandas as pd
    from datetime import datetime, timezone

    data = {
        "student": ["Alice Smith", "Alice Smith", "Bob Jones"],
        "start": [
            datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc),
            datetime(2024, 1, 17, 14, 0, tzinfo=timezone.utc),
            datetime(2024, 1, 16, 10, 0, tzinfo=timezone.utc)
        ],
        "end": [
            datetime(2024, 1, 15, 11, 0, tzinfo=timezone.utc),
            datetime(2024, 1, 17, 15, 30, tzinfo=timezone.utc),
            datetime(2024, 1, 16, 11, 30, tzinfo=timezone.utc)
        ],
        "rate": [50.0, 50.0, 40.0],
        "client_type": ["private", "private", "tutors4u"]
    }

    return pd.DataFrame(data)
