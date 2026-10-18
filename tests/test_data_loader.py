"""
Tests for src/invoice_generator/data_loader.py JSON loading and validation.

The field-level rules live in the models and are tested in
`test_models.py`; these tests cover reading the files.
"""

import json
import pytest
from pydantic import ValidationError

from invoice_generator.data_loader import (
    load_student_data,
    load_bank_details,
    load_contact_details,
)
from invoice_generator.models import StudentInfo, BankDetails, ContactDetails


@pytest.fixture
def write_json(tmp_path):
    """Write `data` to a JSON file in a temporary directory."""
    def _write(data, filename="data.json"):
        path = tmp_path / filename
        path.write_text(json.dumps(data))
        return path
    return _write


class TestLoadStudentData:
    """Tests for load_student_data function."""

    def test_returns_students_by_name(self, write_json):
        """Should map each student's name to a StudentInfo."""
        path = write_json({
            "Alice Smith": {
                "client_type": "private",
                "rate": 50.0,
                "emails": ["alice@example.com"]
            },
            "Bob Jones": {"client_type": "tutors4u", "rate": 40.0}
        })

        result = load_student_data(path)

        assert list(result) == ["Alice Smith", "Bob Jones"]
        assert isinstance(result["Alice Smith"], StudentInfo)
        assert result["Alice Smith"].rate == 50.0
        assert result["Bob Jones"].emails == []

    def test_invalid_student_names_the_file_and_field(self, write_json):
        """Errors should say which file and which student was wrong."""
        path = write_json({
            "Alice Smith": {"client_type": "private", "rate": -50.0}
        })

        with pytest.raises(ValidationError) as exc_info:
            load_student_data(path)

        message = str(exc_info.value)
        assert "students.json" in message
        assert "Alice Smith.rate" in message

    def test_malformed_json_raises_validation_error(self, tmp_path):
        """Malformed JSON should be reported like any other invalid file."""
        path = tmp_path / "students.json"
        path.write_text("{invalid json content")

        with pytest.raises(ValidationError, match="Invalid JSON"):
            load_student_data(path)

    def test_missing_file_raises(self, tmp_path):
        """A missing file should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_student_data(tmp_path / "students.json")


class TestLoadBankDetails:
    """Tests for load_bank_details function."""

    def test_returns_bank_details(self, write_json, sample_bank_details):
        """Should return a validated BankDetails."""
        result = load_bank_details(write_json(sample_bank_details))

        assert isinstance(result, BankDetails)
        assert result.formatted_sort_code == "04-00-04"

    def test_invalid_data_raises(self, write_json, sample_bank_details):
        """Invalid bank details should raise ValidationError."""
        path = write_json({**sample_bank_details, "sort_code": "12345"})

        with pytest.raises(ValidationError, match="sort_code"):
            load_bank_details(path)


class TestLoadContactDetails:
    """Tests for load_contact_details function."""

    def test_returns_contact_details(self, write_json, sample_contact_details):
        """Should return a validated ContactDetails."""
        result = load_contact_details(write_json(sample_contact_details))

        assert isinstance(result, ContactDetails)
        assert result.formatted_mobile == "+44 0712 3456789"

    def test_invalid_data_raises(self, write_json, sample_contact_details):
        """Invalid contact details should raise ValidationError."""
        path = write_json({**sample_contact_details, "country_code": "44"})

        with pytest.raises(ValidationError, match="country_code"):
            load_contact_details(path)
