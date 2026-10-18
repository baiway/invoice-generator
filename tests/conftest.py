"""
Pytest configuration and shared fixtures.
"""

import pytest
from invoice_generator.models import StudentInfo
from datetime import UTC


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
        "bank": "Test Bank"
    }


@pytest.fixture
def sample_contact_details() -> dict[str, str]:
    """Sample contact details for testing."""
    return {
        "country_code": "+44",
        "phone_number": "07123 456789",
        "email": "tutor@example.com"
    }


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
    from invoice_generator.models import BankDetails
    return BankDetails(
        name="Test User",
        sort_code="04-00-04",  # Will be normalized to "040004"
        account_number="1234 5678",  # Will be normalized to "12345678"
        bank="Test Bank"
    )


@pytest.fixture
def sample_contact_details_model():
    """ContactDetails Pydantic model instance."""
    from invoice_generator.models import ContactDetails
    return ContactDetails(
        country_code="+44",
        phone_number="07123456789",  # Will be normalized to digits only
        email="tutor@example.com"
    )


@pytest.fixture
def sample_lessons_dataframe():
    """Sample lessons DataFrame for invoice generation."""
    import pandas as pd
    from datetime import datetime

    data = {
        "student": ["Alice Smith", "Alice Smith", "Bob Jones"],
        "start": [
            datetime(2024, 1, 15, 10, 0, tzinfo=UTC),
            datetime(2024, 1, 17, 14, 0, tzinfo=UTC),
            datetime(2024, 1, 16, 10, 0, tzinfo=UTC)
        ],
        "end": [
            datetime(2024, 1, 15, 11, 0, tzinfo=UTC),
            datetime(2024, 1, 17, 15, 30, tzinfo=UTC),
            datetime(2024, 1, 16, 11, 30, tzinfo=UTC)
        ],
        "rate": [50.0, 50.0, 40.0],
        "client_type": ["private", "private", "tutors4u"]
    }

    return pd.DataFrame(data)
