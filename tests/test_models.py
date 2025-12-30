"""
Tests for src/models.py Pydantic model validation.

This module tests all Pydantic models including validators, properties,
and error handling for invalid data.
"""

import pytest
from pydantic import ValidationError
from src.models import StudentInfo, BankDetails, ContactDetails, StudentsData


class TestStudentInfo:
    """Tests for StudentInfo model validation."""

    def test_valid_student_info(self):
        """Valid student data should create model successfully."""
        student = StudentInfo(
            client_type="private",
            rate=50.0,
            emails=["alice@example.com"]
        )
        assert student.client_type == "private"
        assert student.rate == 50.0
        assert student.emails == ["alice@example.com"]

    def test_student_info_missing_client_type(
        self, invalid_student_data_missing_rate
    ):
        """Missing rate should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            StudentInfo(**invalid_student_data_missing_rate["Alice Smith"])
        assert "rate" in str(exc_info.value).lower()

    def test_student_info_negative_rate(
        self, invalid_student_data_negative_rate
    ):
        """Negative rate should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            StudentInfo(**invalid_student_data_negative_rate["Alice Smith"])
        assert "greater than 0" in str(exc_info.value)

    def test_student_info_zero_rate(self):
        """Zero rate should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            StudentInfo(client_type="private", rate=0.0, emails=[])
        assert "greater than 0" in str(exc_info.value)

    def test_student_info_invalid_email(self, invalid_student_data_bad_email):
        """Invalid email format should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            StudentInfo(**invalid_student_data_bad_email["Alice Smith"])
        assert "email" in str(exc_info.value).lower()

    def test_student_info_empty_emails(self):
        """Empty email list should be allowed (for title-matched students)."""
        student = StudentInfo(
            client_type="blue_education",
            rate=45.0,
            emails=[]  # Matched by event title only
        )
        assert student.emails == []

    def test_formatted_rate_property(self):
        """formatted_rate should format to 2 decimal places."""
        student1 = StudentInfo(client_type="private", rate=50.0, emails=[])
        assert student1.formatted_rate == "50.00"

        student2 = StudentInfo(client_type="private", rate=45.5, emails=[])
        assert student2.formatted_rate == "45.50"

        student3 = StudentInfo(client_type="private", rate=123.456, emails=[])
        assert student3.formatted_rate == "123.46"


class TestBankDetails:
    """Tests for BankDetails model validation and formatting."""

    def test_valid_bank_details(self, sample_bank_details):
        """Valid bank details should create model successfully."""
        details = BankDetails(**sample_bank_details)
        assert details.name == "Test User"
        assert details.bank == "Test Bank"

    def test_sort_code_normalization_with_dashes(self):
        """Sort code with dashes should be normalized to digits."""
        details = BankDetails(
            name="Test",
            sort_code="04-00-04",
            account_number="12345678",
            bank="Test Bank",
            link="https://example.com?amount={amount}",
            QR_code="https://example.com/qr?amount={amount}"
        )
        assert details.sort_code == "040004"

    def test_sort_code_normalization_with_spaces(self):
        """Sort code with spaces should be normalized."""
        details = BankDetails(
            name="Test",
            sort_code="04 00 04",
            account_number="12345678",
            bank="Test Bank",
            link="https://example.com?amount={amount}",
            QR_code="https://example.com/qr?amount={amount}"
        )
        assert details.sort_code == "040004"

    def test_sort_code_invalid_length(
        self, invalid_bank_details_bad_sort_code
    ):
        """Sort code not 6 digits should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            BankDetails(**invalid_bank_details_bad_sort_code)
        assert "6 digits" in str(exc_info.value)

    def test_sort_code_non_numeric(self):
        """Sort code with letters should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            BankDetails(
                name="Test",
                sort_code="04-AB-04",
                account_number="12345678",
                bank="Test Bank",
                link="https://example.com?amount={amount}",
                QR_code="https://example.com/qr?amount={amount}"
            )
        assert "6 digits" in str(exc_info.value)

    def test_account_number_normalization(self):
        """Account number with spaces should be normalized."""
        details = BankDetails(
            name="Test",
            sort_code="040004",
            account_number="1234 5678",
            bank="Test Bank",
            link="https://example.com?amount={amount}",
            QR_code="https://example.com/qr?amount={amount}"
        )
        assert details.account_number == "12345678"

    def test_account_number_invalid_length(self):
        """Account number not 8 digits should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            BankDetails(
                name="Test",
                sort_code="040004",
                account_number="1234567",  # 7 digits
                bank="Test Bank",
                link="https://example.com?amount={amount}",
                QR_code="https://example.com/qr?amount={amount}"
            )
        assert "8 digits" in str(exc_info.value)

    def test_account_number_non_numeric(self):
        """Account number with letters should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            BankDetails(
                name="Test",
                sort_code="040004",
                account_number="1234ABCD",
                bank="Test Bank",
                link="https://example.com?amount={amount}",
                QR_code="https://example.com/qr?amount={amount}"
            )
        assert "8 digits" in str(exc_info.value)

    def test_link_missing_placeholder(
        self, invalid_bank_details_no_placeholder
    ):
        """Link without {amount} placeholder should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            BankDetails(**invalid_bank_details_no_placeholder)
        assert "{amount}" in str(exc_info.value)

    def test_qr_code_missing_placeholder(self):
        """QR code without {amount} placeholder should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            BankDetails(
                name="Test",
                sort_code="040004",
                account_number="12345678",
                bank="Test Bank",
                link="https://example.com?amount={amount}",
                QR_code="https://example.com/qr"  # Missing {amount}
            )
        assert "{amount}" in str(exc_info.value)

    def test_formatted_sort_code_property(self):
        """formatted_sort_code should format as XX-XX-XX."""
        details = BankDetails(
            name="Test",
            sort_code="040004",
            account_number="12345678",
            bank="Test Bank",
            link="https://example.com?amount={amount}",
            QR_code="https://example.com/qr?amount={amount}"
        )
        assert details.formatted_sort_code == "04-00-04"

    def test_formatted_account_number_property(self):
        """formatted_account_number should format as XXXX XXXX."""
        details = BankDetails(
            name="Test",
            sort_code="040004",
            account_number="12345678",
            bank="Test Bank",
            link="https://example.com?amount={amount}",
            QR_code="https://example.com/qr?amount={amount}"
        )
        assert details.formatted_account_number == "1234 5678"


class TestContactDetails:
    """Tests for ContactDetails model validation and formatting."""

    def test_valid_contact_details(self, sample_contact_details):
        """Valid contact details should create model successfully."""
        # Need to update sample_contact_details to use country_code
        details = ContactDetails(
            country_code="+44",
            phone_number=sample_contact_details["mobile"],
            email=sample_contact_details["email"]
        )
        assert details.country_code == "+44"
        assert details.email == "tutor@example.com"

    def test_phone_number_normalization(self):
        """Phone number should be normalized to digits only."""
        details = ContactDetails(
            country_code="+44",
            phone_number="07123 456789",
            email="test@example.com"
        )
        assert details.phone_number == "07123456789"

        details2 = ContactDetails(
            country_code="+44",
            phone_number="(0712) 345-6789",
            email="test@example.com"
        )
        assert details2.phone_number == "07123456789"

    def test_phone_number_too_short(
        self, invalid_contact_details_short_phone
    ):
        """Phone number < 10 digits should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ContactDetails(**invalid_contact_details_short_phone)
        assert "10" in str(exc_info.value)  # Checks for "10 characters" message

    def test_invalid_country_code_format(
        self, invalid_contact_details_bad_country_code
    ):
        r"""Country code not matching ^\+\d+$ should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ContactDetails(**invalid_contact_details_bad_country_code)
        # Pydantic pattern validation error
        assert "pattern" in str(exc_info.value).lower() or "match" in str(exc_info.value).lower()

    def test_invalid_email(self):
        """Invalid email should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ContactDetails(
                country_code="+44",
                phone_number="1234567890",
                email="not-an-email"
            )
        assert "email" in str(exc_info.value).lower()

    def test_formatted_mobile_property(self):
        """formatted_mobile should format as international number."""
        details = ContactDetails(
            country_code="+44",
            phone_number="1234567890",
            email="test@example.com"
        )
        assert details.formatted_mobile == "+44 1234 567890"

        details2 = ContactDetails(
            country_code="+1",
            phone_number="2025551234",
            email="test@example.com"
        )
        assert details2.formatted_mobile == "+1 2025 551234"

    def test_phone_number_exactly_10_digits(self):
        """Phone number with exactly 10 digits should be valid."""
        details = ContactDetails(
            country_code="+44",
            phone_number="1234567890",  # Exactly 10 digits
            email="test@example.com"
        )
        assert details.phone_number == "1234567890"
        assert len(details.phone_number) == 10

    def test_phone_number_9_digits_raises_error(self):
        """Phone number with 9 digits should raise specific ValueError."""
        with pytest.raises(ValidationError) as exc_info:
            ContactDetails(
                country_code="+44",
                phone_number="123456789",  # Only 9 digits
                email="test@example.com"
            )
        # Check that the error mentions the digit requirement
        error_str = str(exc_info.value)
        assert "10" in error_str or "digit" in error_str.lower()


class TestStudentsData:
    """Tests for StudentsData root model."""

    def test_valid_students_data(self, sample_students_data):
        """Valid students dictionary should create model successfully."""
        students = StudentsData(root=sample_students_data)
        assert "Alice Smith" in students.root
        assert "Bob Jones" in students.root

    def test_iteration(self, sample_students_data):
        """Should support iteration over student names."""
        students = StudentsData(root=sample_students_data)
        names = list(students)
        assert "Alice Smith" in names
        assert "Bob Jones" in names

    def test_getitem(self, sample_students_data):
        """Should support dictionary-style access."""
        students = StudentsData(root=sample_students_data)
        alice = students["Alice Smith"]
        assert isinstance(alice, StudentInfo)
        assert alice.client_type == "private"

    def test_items_method(self, sample_students_data):
        """Should support .items() access."""
        students = StudentsData(root=sample_students_data)
        items = list(students.items())
        assert len(items) == 2
        assert all(isinstance(info, StudentInfo) for _, info in items)

    def test_keys_method(self, sample_students_data):
        """Should support .keys() access."""
        students = StudentsData(root=sample_students_data)
        keys = list(students.keys())
        assert "Alice Smith" in keys
        assert "Bob Jones" in keys

    def test_values_method(self, sample_students_data):
        """Should support .values() access."""
        students = StudentsData(root=sample_students_data)
        values = list(students.values())
        assert len(values) == 2
        assert all(isinstance(info, StudentInfo) for info in values)
