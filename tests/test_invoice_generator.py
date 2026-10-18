"""
Tests for src/invoice_generator/invoice_generator.py PDF generation and invoice creation.

PDFs are actually rendered, then read back, to verify the full
pipeline works correctly.
"""

import logging
import pytest
from datetime import datetime, timedelta, UTC
from pypdf import PdfReader

from invoice_generator.invoice_generator import (
    format_invoice,
    get_invoice_period,
    write_invoices,
)
from invoice_generator.event_processing import Lesson
from invoice_generator.models import StudentInfo


class TestGetInvoicePeriod:
    """Tests for get_invoice_period function."""

    def test_full_month_january(self):
        """Full month coverage should return 'Month YYYY' format."""
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 31)
        result = get_invoice_period(start, end)
        assert result == "January 2024"

    def test_full_month_february_leap_year(self):
        """February in leap year should handle 29 days."""
        start = datetime(2024, 2, 1)  # 2024 is a leap year
        end = datetime(2024, 2, 29)
        result = get_invoice_period(start, end)
        assert result == "February 2024"

    def test_full_month_february_non_leap(self):
        """February in non-leap year should handle 28 days."""
        start = datetime(2023, 2, 1)  # 2023 is not a leap year
        end = datetime(2023, 2, 28)
        result = get_invoice_period(start, end)
        assert result == "February 2023"

    def test_partial_month(self):
        """Partial month should return 'DD/MM/YYYY to DD/MM/YYYY' format."""
        start = datetime(2024, 1, 5)
        end = datetime(2024, 1, 20)
        result = get_invoice_period(start, end)
        assert result == "05/01/2024 to 20/01/2024"

    def test_multi_month_period(self):
        """Multi-month period should return date range format."""
        start = datetime(2024, 1, 1)
        end = datetime(2024, 2, 28)
        result = get_invoice_period(start, end)
        assert result == "01/01/2024 to 28/02/2024"

    def test_period_ending_on_a_later_months_last_day(self):
        """Ending on the 31st of a later month is not a single month."""
        start = datetime(2024, 1, 1)
        end = datetime(2024, 3, 31)
        result = get_invoice_period(start, end)
        assert result == "01/01/2024 to 31/03/2024"

    def test_same_month_a_year_later(self):
        """January to the following January is not "January"."""
        start = datetime(2024, 1, 1)
        end = datetime(2025, 1, 31)
        result = get_invoice_period(start, end)
        assert result == "01/01/2024 to 31/01/2025"

    def test_end_time_of_day_is_ignored(self):
        """The CLI's end date runs to 23:59:59; it is still a whole month."""
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 31, 23, 59, 59)
        assert get_invoice_period(start, end) == "January 2024"

    def test_single_day_invoice(self):
        """Single day invoice should return date range format."""
        start = datetime(2024, 1, 15)
        end = datetime(2024, 1, 15)
        result = get_invoice_period(start, end)
        assert result == "15/01/2024 to 15/01/2024"


def lesson(day, hour, minutes=60):
    """A lesson on `day` January 2024, starting at `hour` UTC."""
    start = datetime(2024, 1, day, hour, tzinfo=UTC)
    return Lesson(start, start + timedelta(minutes=minutes))


@pytest.fixture
def write(tmp_path, sample_bank_details_model, sample_contact_details_model):
    """Call write_invoices for January 2024 with the sample details,
    writing to `tmp_path / "invoices"`."""
    def _write(lessons, student_data):
        return write_invoices(
            lessons,
            student_data,
            datetime(2024, 1, 1),
            datetime(2024, 1, 31, 23, 59, 59),
            sample_bank_details_model,
            sample_contact_details_model,
            tmp_path / "invoices",
        )
    return _write


def pdfs(directory):
    """Names of the PDFs in `directory`."""
    return sorted(path.name for path in directory.glob("*.pdf"))


def pages(path):
    """The text of each page of a PDF."""
    return [page.extract_text() for page in PdfReader(path).pages]


class TestFormatInvoice:
    """Tests for format_invoice function."""

    def test_formats_sessions_and_totals(self):
        """1 hour + 1.5 hours at £50/hour should come to £125."""
        invoice = format_invoice(
            "Alice", [lesson(15, 10), lesson(16, 10, 90)], 50.0
        )

        assert invoice == {
            "student": "Alice",
            "sessions": [
                {"date": "15/01/2024", "time": "10:00 until 11:00 (1 hour)"},
                {"date": "16/01/2024",
                 "time": "10:00 until 11:30 (1 hour 30 mins)"},
            ],
            "total_time": "2 hours 30 mins",
            "rate": "£50.00/hour",
            "amount_owed": "£125.00",
        }

    def test_times_are_shown_in_uk_time(self):
        """A 10:00 UTC lesson in summer took place at 11:00 BST."""
        start = datetime(2024, 7, 15, 10, tzinfo=UTC)
        invoice = format_invoice(
            "Alice", [Lesson(start, start + timedelta(hours=1))], 50.0
        )

        assert invoice["sessions"][0]["time"] == "11:00 until 12:00 (1 hour)"


class TestWriteInvoices:
    """Tests for write_invoices function."""

    def test_creates_output_directory_and_returns_its_path(
        self, tmp_path, write, sample_lessons, sample_students_data
    ):
        """Should create the output directory and return its absolute path."""
        result = write(sample_lessons, sample_students_data)

        assert result == (tmp_path / "invoices").resolve()
        assert result.is_dir()

    def test_private_client_gets_their_own_pdf(self, tmp_path, write):
        """Private clients get a one-page PDF each, named after them."""
        student_data = {
            "Alice Mary Smith": StudentInfo(client_type="private", rate=50.0)
        }

        write({"Alice Mary Smith": [lesson(15, 10)]}, student_data)

        assert pdfs(tmp_path / "invoices") == ["alice-mary-smith-invoice.pdf"]
        (page,) = pages(tmp_path / "invoices" / "alice-mary-smith-invoice.pdf")
        assert "Alice Mary Smith invoice for January 2024" in page

    def test_agency_students_share_one_pdf_a_page_each(self, tmp_path, write):
        """Students from one agency are combined into the agency's PDF,
        in alphabetical order."""
        student_data = {
            "Student A": StudentInfo(client_type="tutors4u", rate=40.0),
            "Student B": StudentInfo(client_type="tutors4u", rate=40.0),
            "Student C": StudentInfo(client_type="private", rate=50.0),
        }
        lessons = {
            "Student B": [lesson(17, 10)],
            "Student A": [lesson(15, 10), lesson(16, 10)],
            "Student C": [lesson(18, 10)],
        }

        write(lessons, student_data)

        assert pdfs(tmp_path / "invoices") == [
            "student-c-invoice.pdf", "tutors4u-invoice.pdf"
        ]
        first, second = pages(tmp_path / "invoices" / "tutors4u-invoice.pdf")
        assert "Student A invoice" in first
        assert "Student B invoice" in second

    def test_invoice_shows_lessons_totals_and_payment_details(
        self, tmp_path, write
    ):
        """Everything on the invoice should make it into the PDF."""
        student_data = {"Alice": StudentInfo(client_type="private", rate=50.0)}

        write({"Alice": [lesson(15, 10), lesson(16, 10, 90)]}, student_data)

        (page,) = pages(tmp_path / "invoices" / "alice-invoice.pdf")
        for text in [
            "15/01/2024 10:00 until 11:00 (1 hour)",
            "16/01/2024 10:00 until 11:30 (1 hour 30 mins)",
            "Total time 2 hours 30 mins",
            "Rate £50.00/hour",
            "Amount owed £125.00",
            "Name: Test User",
            "Sort code: 04-00-04",
            "Account no: 1234 5678",
            "Bank: Test Bank",
            "Mobile: +44 0712 3456789",
            "Email: tutor@example.com",
        ]:
            assert text in page

    def test_names_are_not_interpreted_as_markup(self, tmp_path, write):
        """Student names reach Typst as data, so markup characters in
        them are printed as they are."""
        name = "Ana *Bold* #emph[x]"
        student_data = {name: StudentInfo(client_type="tutors4u", rate=40.0)}

        write({name: [lesson(15, 10)]}, student_data)

        (page,) = pages(tmp_path / "invoices" / "tutors4u-invoice.pdf")
        assert f"{name} invoice for January 2024" in page

    def test_logs_each_pdf(
        self, write, sample_lessons, sample_students_data, caplog
    ):
        """Should log each PDF written."""
        with caplog.at_level(logging.INFO):
            write(sample_lessons, sample_students_data)

        assert "Generated alice-smith-invoice.pdf" in caplog.text
        assert "Generated tutors4u-invoice.pdf" in caplog.text
