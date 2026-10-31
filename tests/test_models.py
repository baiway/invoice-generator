"""
Tests for src/invoice_generator/models.py Pydantic model validation.

This module tests all Pydantic models including validators, properties,
and error handling for invalid data.
"""

import pytest
from pydantic import ValidationError
from invoice_generator.models import StudentInfo, BankDetails, ContactDetails


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

    def test_student_info_missing_rate(self):
        """Missing rate should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            StudentInfo.model_validate(
                {"client_type": "private", "emails": ["alice@example.com"]}
            )
        assert "rate" in str(exc_info.value).lower()

    def test_student_info_negative_rate(self):
        """Negative rate should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            StudentInfo(client_type="private", rate=-50.0, emails=[])
        assert "greater than 0" in str(exc_info.value)

    def test_student_info_zero_rate(self):
        """Zero rate should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            StudentInfo(client_type="private", rate=0.0, emails=[])
        assert "greater than 0" in str(exc_info.value)

    def test_student_info_invalid_email(self):
        """Invalid email format should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            StudentInfo(client_type="private", rate=50.0, emails=["not-an-email"])
        assert "email" in str(exc_info.value).lower()

    def test_student_info_empty_emails(self):
        """Empty email list should be allowed (for title-matched students)."""
        student = StudentInfo(
            client_type="blue_education",
            rate=45.0,
            emails=[]  # Matched by event title only
        )
        assert student.emails == []

    def test_reports_are_off_by_default(self):
        """Students without `reports` get invoices only."""
        student = StudentInfo(client_type="private", rate=50.0)
        assert student.reports is False
        assert student.folders == []

    @pytest.mark.parametrize("url, folder_id", [
        ("https://drive.google.com/drive/folders/1AbC-d_E?usp=sharing", "1AbC-d_E"),
        ("https://drive.google.com/drive/folders/1AbC-d_E?usp=drive_link", "1AbC-d_E"),
        ("https://drive.google.com/drive/folders/1AbC-d_E", "1AbC-d_E"),
        ("https://drive.google.com/drive/u/0/folders/1AbC-d_E", "1AbC-d_E"),
    ])
    def test_folder_links_give_folder_ids(self, url, folder_id):
        """Links copied from Drive's share dialog or address bar should
        all give the folder's ID."""
        student = StudentInfo(client_type="private", rate=50.0,
                              reports=True, folders=[url])
        assert student.folder_ids == [folder_id]

    def test_folder_ids_keep_the_order_of_folders(self):
        """One folder per subject, in the order listed."""
        student = StudentInfo(
            client_type="private", rate=50.0, reports=True,
            folders=["https://drive.google.com/drive/folders/maths",
                     "https://drive.google.com/drive/folders/physics"],
        )
        assert student.folder_ids == ["maths", "physics"]

    @pytest.mark.parametrize("url", [
        "https://drive.google.com/file/d/1AbC/view",
        "https://docs.google.com/document/d/1AbC/edit",
        "drive.google.com/drive/folders/1AbC",
        "1AbC",
    ])
    def test_links_to_anything_but_a_folder_are_rejected(self, url):
        """Files, documents and bare IDs aren't folders to look in."""
        with pytest.raises(ValidationError, match="not a link to a Google Drive folder"):
            StudentInfo(client_type="private", rate=50.0, folders=[url])

    def test_reports_need_a_folder(self):
        """`reports` without `folders` leaves nowhere to find lessons."""
        with pytest.raises(ValidationError, match="`folders` must list at least one"):
            StudentInfo(client_type="private", rate=50.0, reports=True)


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
            bank="Test Bank"
        )
        assert details.sort_code == "040004"

    def test_sort_code_normalization_with_spaces(self):
        """Sort code with spaces should be normalized."""
        details = BankDetails(
            name="Test",
            sort_code="04 00 04",
            account_number="12345678",
            bank="Test Bank"
        )
        assert details.sort_code == "040004"

    def test_sort_code_invalid_length(self, sample_bank_details):
        """Sort code not 6 digits should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            BankDetails(**{**sample_bank_details, "sort_code": "12345"})
        assert "6 digits" in str(exc_info.value)

    def test_sort_code_non_numeric(self):
        """Sort code with letters should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            BankDetails(
                name="Test",
                sort_code="04-AB-04",
                account_number="12345678",
                bank="Test Bank"
            )
        assert "6 digits" in str(exc_info.value)

    def test_account_number_normalization(self):
        """Account number with spaces should be normalized."""
        details = BankDetails(
            name="Test",
            sort_code="040004",
            account_number="1234 5678",
            bank="Test Bank"
        )
        assert details.account_number == "12345678"

    def test_account_number_invalid_length(self):
        """Account number not 8 digits should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            BankDetails(
                name="Test",
                sort_code="040004",
                account_number="1234567",  # 7 digits
                bank="Test Bank"
            )
        assert "8 digits" in str(exc_info.value)

    def test_account_number_non_numeric(self):
        """Account number with letters should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            BankDetails(
                name="Test",
                sort_code="040004",
                account_number="1234ABCD",
                bank="Test Bank"
            )
        assert "8 digits" in str(exc_info.value)

    def test_formatted_sort_code_property(self):
        """formatted_sort_code should format as XX-XX-XX."""
        details = BankDetails(
            name="Test",
            sort_code="040004",
            account_number="12345678",
            bank="Test Bank"
        )
        assert details.formatted_sort_code == "04-00-04"

    def test_formatted_account_number_property(self):
        """formatted_account_number should format as XXXX XXXX."""
        details = BankDetails(
            name="Test",
            sort_code="040004",
            account_number="12345678",
            bank="Test Bank"
        )
        assert details.formatted_account_number == "1234 5678"


class TestContactDetails:
    """Tests for ContactDetails model validation and formatting."""

    def test_valid_contact_details(self, sample_contact_details):
        """Valid contact details should create model successfully."""
        details = ContactDetails(**sample_contact_details)
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

    def test_phone_number_too_short(self, sample_contact_details):
        """Phone number < 10 digits should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ContactDetails(**{**sample_contact_details, "phone_number": "123"})
        assert "10" in str(exc_info.value)  # Checks for "10 characters" message

    def test_phone_number_too_few_digits_after_normalisation(self):
        """Formatting characters must not disguise a short number.

        `min_length` counts characters, so a number padded with spaces
        clears it; only `normalise_phone_number` counts the digits.
        """
        with pytest.raises(ValidationError, match="at least 10 digits, got 8"):
            ContactDetails(
                country_code="+44",
                phone_number="12 34 56 78",  # 11 characters, 8 digits
                email="tutor@example.com"
            )

    def test_invalid_country_code_format(self, sample_contact_details):
        r"""Country code not matching ^\+\d+$ should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ContactDetails(**{**sample_contact_details, "country_code": "44"})
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

