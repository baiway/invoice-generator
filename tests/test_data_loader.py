"""
Tests for src/data_loader.py JSON loading and validation.

This module tests all data loading functions including error handling
for missing files, malformed JSON, and validation errors.
"""

import json
import pytest
from pathlib import Path
from pydantic import ValidationError

from src.data_loader import (
    load_json_with_model,
    load_student_data,
    load_bank_details,
    load_contact_details,
)
from src.models import StudentInfo, BankDetails, ContactDetails, StudentsData


class TestLoadJsonWithModel:
    """Tests for load_json_with_model generic loader function."""

    def test_successful_load_with_valid_json(self, tmp_path):
        """Valid JSON should be loaded and validated successfully."""
        # Create valid bank details JSON
        valid_data = {
            "name": "Test User",
            "sort_code": "04-00-04",
            "account_number": "12345678",
            "bank": "Test Bank",
            "link": "https://example.com?amount={amount}",
            "QR_code": "https://example.com/qr?amount={amount}"
        }
        test_file = tmp_path / "test.json"
        test_file.write_text(json.dumps(valid_data))

        result = load_json_with_model(
            BankDetails,
            str(test_file),
            "test bank details"
        )

        assert isinstance(result, BankDetails)
        assert result.name == "Test User"
        assert result.bank == "Test Bank"

    def test_file_not_found_error(self):
        """Missing file should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_json_with_model(
                BankDetails,
                "/nonexistent/path/file.json",
                "test data"
            )

    def test_malformed_json_error(self, malformed_json_file):
        """Malformed JSON should raise JSONDecodeError."""
        with pytest.raises(json.JSONDecodeError):
            load_json_with_model(
                BankDetails,
                malformed_json_file,
                "malformed data"
            )

    def test_validation_error_for_invalid_schema(self, tmp_path):
        """Data not matching schema should raise ValidationError."""
        # Create JSON with missing required field
        invalid_data = {
            "name": "Test User",
            "sort_code": "040004",
            # Missing account_number, bank, link, QR_code
        }
        test_file = tmp_path / "invalid.json"
        test_file.write_text(json.dumps(invalid_data))

        with pytest.raises(ValidationError):
            load_json_with_model(
                BankDetails,
                str(test_file),
                "invalid bank details"
            )

    def test_validation_error_message_formatting(self, tmp_path, caplog):
        """ValidationError should log formatted error messages."""
        import logging

        # Create JSON with invalid sort code
        invalid_data = {
            "name": "Test User",
            "sort_code": "12345",  # Invalid: must be 6 digits
            "account_number": "12345678",
            "bank": "Test Bank",
            "link": "https://example.com?amount={amount}",
            "QR_code": "https://example.com/qr?amount={amount}"
        }
        test_file = tmp_path / "invalid.json"
        test_file.write_text(json.dumps(invalid_data))

        with caplog.at_level(logging.ERROR):
            with pytest.raises(ValidationError):
                load_json_with_model(
                    BankDetails,
                    str(test_file),
                    "invalid bank details"
                )

        # Verify error was logged
        assert "Validation failed" in caplog.text


class TestLoadStudentData:
    """Tests for load_student_data function."""

    def test_successful_load_returns_dict(self, tmp_path, monkeypatch):
        """Successful load should return dict[str, StudentInfo]."""
        # Create valid students.json
        valid_students = {
            "Alice Smith": {
                "client_type": "private",
                "rate": 50.0,
                "emails": ["alice@example.com"]
            },
            "Bob Jones": {
                "client_type": "tutors4u",
                "rate": 40.0,
                "emails": ["bob@example.com"]
            }
        }
        test_file = tmp_path / "students.json"
        test_file.write_text(json.dumps(valid_students))

        # Monkeypatch the STUDENTS_FILE constant
        monkeypatch.setattr("src.data_loader.STUDENTS_FILE", str(test_file))

        result = load_student_data()

        assert isinstance(result, dict)
        assert "Alice Smith" in result
        assert isinstance(result["Alice Smith"], StudentInfo)
        assert result["Alice Smith"].rate == 50.0

    def test_returns_dict_not_students_data_model(self, tmp_path, monkeypatch):
        """Should return plain dict, not StudentsData model instance."""
        valid_students = {
            "Alice Smith": {
                "client_type": "private",
                "rate": 50.0,
                "emails": ["alice@example.com"]
            }
        }
        test_file = tmp_path / "students.json"
        test_file.write_text(json.dumps(valid_students))

        monkeypatch.setattr("src.data_loader.STUDENTS_FILE", str(test_file))

        result = load_student_data()

        # Should be dict, not StudentsData
        assert type(result) is dict
        assert not isinstance(result, StudentsData)

    def test_file_not_found_handling(self, monkeypatch):
        """Missing students.json should raise FileNotFoundError."""
        monkeypatch.setattr(
            "src.data_loader.STUDENTS_FILE",
            "/nonexistent/students.json"
        )

        with pytest.raises(FileNotFoundError):
            load_student_data()

    def test_validation_error_for_invalid_data(self, tmp_path, monkeypatch):
        """Invalid student data should raise ValidationError."""
        invalid_students = {
            "Alice Smith": {
                "client_type": "private",
                "rate": -50.0,  # Invalid: must be > 0
                "emails": ["alice@example.com"]
            }
        }
        test_file = tmp_path / "students.json"
        test_file.write_text(json.dumps(invalid_students))

        monkeypatch.setattr("src.data_loader.STUDENTS_FILE", str(test_file))

        with pytest.raises(ValidationError):
            load_student_data()


class TestLoadBankDetails:
    """Tests for load_bank_details function."""

    def test_successful_load_returns_bank_details(self, tmp_path, monkeypatch):
        """Successful load should return BankDetails instance."""
        valid_bank = {
            "name": "Test User",
            "sort_code": "04-00-04",
            "account_number": "12345678",
            "bank": "Test Bank",
            "link": "https://example.com?amount={amount}",
            "QR_code": "https://example.com/qr?amount={amount}"
        }
        test_file = tmp_path / "bank_details.json"
        test_file.write_text(json.dumps(valid_bank))

        monkeypatch.setattr("src.data_loader.BANK_DETAILS_FILE", str(test_file))

        result = load_bank_details()

        assert isinstance(result, BankDetails)
        assert result.name == "Test User"
        assert result.bank == "Test Bank"

    def test_type_verification(self, tmp_path, monkeypatch):
        """Result should be BankDetails instance with correct attributes."""
        valid_bank = {
            "name": "Test User",
            "sort_code": "040004",
            "account_number": "12345678",
            "bank": "Test Bank",
            "link": "https://example.com?amount={amount}",
            "QR_code": "https://example.com/qr?amount={amount}"
        }
        test_file = tmp_path / "bank_details.json"
        test_file.write_text(json.dumps(valid_bank))

        monkeypatch.setattr("src.data_loader.BANK_DETAILS_FILE", str(test_file))

        result = load_bank_details()

        # Verify it has expected properties
        assert hasattr(result, 'formatted_sort_code')
        assert hasattr(result, 'formatted_account_number')
        assert result.formatted_sort_code == "04-00-04"

    def test_file_not_found_handling(self, monkeypatch):
        """Missing bank_details.json should raise FileNotFoundError."""
        monkeypatch.setattr(
            "src.data_loader.BANK_DETAILS_FILE",
            "/nonexistent/bank_details.json"
        )

        with pytest.raises(FileNotFoundError):
            load_bank_details()

    def test_validation_error_for_invalid_data(self, tmp_path, monkeypatch):
        """Invalid bank details should raise ValidationError."""
        invalid_bank = {
            "name": "Test User",
            "sort_code": "12345",  # Invalid: must be 6 digits
            "account_number": "12345678",
            "bank": "Test Bank",
            "link": "https://example.com?amount={amount}",
            "QR_code": "https://example.com/qr?amount={amount}"
        }
        test_file = tmp_path / "bank_details.json"
        test_file.write_text(json.dumps(invalid_bank))

        monkeypatch.setattr("src.data_loader.BANK_DETAILS_FILE", str(test_file))

        with pytest.raises(ValidationError):
            load_bank_details()


class TestLoadContactDetails:
    """Tests for load_contact_details function."""

    def test_successful_load_returns_contact_details(self, tmp_path, monkeypatch):
        """Successful load should return ContactDetails instance."""
        valid_contact = {
            "country_code": "+44",
            "phone_number": "07123456789",
            "email": "tutor@example.com"
        }
        test_file = tmp_path / "contact_details.json"
        test_file.write_text(json.dumps(valid_contact))

        monkeypatch.setattr("src.data_loader.CONTACT_DETAILS_FILE", str(test_file))

        result = load_contact_details()

        assert isinstance(result, ContactDetails)
        assert result.email == "tutor@example.com"
        assert result.country_code == "+44"

    def test_type_verification(self, tmp_path, monkeypatch):
        """Result should be ContactDetails instance with correct attributes."""
        valid_contact = {
            "country_code": "+44",
            "phone_number": "07123456789",
            "email": "tutor@example.com"
        }
        test_file = tmp_path / "contact_details.json"
        test_file.write_text(json.dumps(valid_contact))

        monkeypatch.setattr("src.data_loader.CONTACT_DETAILS_FILE", str(test_file))

        result = load_contact_details()

        # Verify it has expected properties
        assert hasattr(result, 'formatted_mobile')
        assert result.formatted_mobile == "+44 0712 3456789"

    def test_file_not_found_handling(self, monkeypatch):
        """Missing contact_details.json should raise FileNotFoundError."""
        monkeypatch.setattr(
            "src.data_loader.CONTACT_DETAILS_FILE",
            "/nonexistent/contact_details.json"
        )

        with pytest.raises(FileNotFoundError):
            load_contact_details()

    def test_validation_error_for_invalid_data(self, tmp_path, monkeypatch):
        """Invalid contact details should raise ValidationError."""
        invalid_contact = {
            "country_code": "44",  # Invalid: must start with +
            "phone_number": "07123456789",
            "email": "tutor@example.com"
        }
        test_file = tmp_path / "contact_details.json"
        test_file.write_text(json.dumps(invalid_contact))

        monkeypatch.setattr("src.data_loader.CONTACT_DETAILS_FILE", str(test_file))

        with pytest.raises(ValidationError):
            load_contact_details()
