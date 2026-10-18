"""
Tests for src/invoice_generator/invoice_generator.py PDF generation and invoice creation.

This module tests invoice generation logic including PDF creation,
calculations, and formatting. PDFs are actually generated to verify
the full rendering pipeline works correctly.
"""

import logging
import pytest
from datetime import datetime, timedelta, UTC

from invoice_generator.invoice_generator import (
    get_invoice_period,
    extract_page_content,
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

    def test_single_day_invoice(self):
        """Single day invoice should return date range format."""
        start = datetime(2024, 1, 15)
        end = datetime(2024, 1, 15)
        result = get_invoice_period(start, end)
        assert result == "15/01/2024 to 15/01/2024"


class TestExtractPageContent:
    """Tests for extract_page_content function."""

    def test_extract_container_div(self):
        """Should extract content inside <div class='container'>."""
        html = """
        <html>
        <body>
            <div class="container">
                <h1>Invoice</h1>
                <p>Content here</p>
            </div>
        </body>
        </html>
        """
        result = extract_page_content(html)
        assert '<div class="container">' in result
        assert '<h1>Invoice</h1>' in result
        assert '<p>Content here</p>' in result

    def test_extract_from_complete_html_document(self):
        """Should extract container from complete HTML structure."""
        html = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>Invoice</title>
        </head>
        <body>
            <div class="header">Header content</div>
            <div class="container">
                <h1>Main Invoice Content</h1>
            </div>
            <div class="footer">Footer content</div>
        </body>
        </html>
        """
        result = extract_page_content(html)
        assert '<div class="container">' in result
        assert '<h1>Main Invoice Content</h1>' in result
        assert "Header content" not in result  # Outside container
        assert "Footer content" not in result  # Outside container


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
        """Private clients get one PDF each, named after them."""
        student_data = {
            "Alice Mary Smith": StudentInfo(client_type="private", rate=50.0)
        }

        write({"Alice Mary Smith": [lesson(15, 10)]}, student_data)

        assert pdfs(tmp_path / "invoices") == ["alice-mary-smith-invoice.pdf"]

    def test_agency_students_share_one_pdf(self, tmp_path, write):
        """Students from one agency are combined into the agency's PDF."""
        student_data = {
            "Student A": StudentInfo(client_type="tutors4u", rate=40.0),
            "Student B": StudentInfo(client_type="tutors4u", rate=40.0),
            "Student C": StudentInfo(client_type="private", rate=50.0),
        }
        lessons = {
            "Student A": [lesson(15, 10), lesson(16, 10)],
            "Student B": [lesson(17, 10)],
            "Student C": [lesson(18, 10)],
        }

        write(lessons, student_data)

        assert pdfs(tmp_path / "invoices") == [
            "student-c-invoice.pdf", "tutors4u-invoice.pdf"
        ]

    def test_amount_owed_is_hours_times_rate(self, write, monkeypatch):
        """1 hour + 1.5 hours at £50/hour should come to £125."""
        rendered = []

        class CapturingHTML:
            def __init__(self, string):
                rendered.append(string)

            def write_pdf(self, path, stylesheets=None):
                pass

        monkeypatch.setattr(
            "invoice_generator.invoice_generator.HTML", CapturingHTML
        )
        student_data = {"Alice": StudentInfo(client_type="private", rate=50.0)}

        write({"Alice": [lesson(15, 10), lesson(16, 10, 90)]}, student_data)

        (html,) = rendered
        assert "2 hours 30 mins" in html
        assert "£125.00" in html

    def test_logs_each_pdf(
        self, write, sample_lessons, sample_students_data, caplog
    ):
        """Should log each private and agency invoice written."""
        with caplog.at_level(logging.INFO):
            write(sample_lessons, sample_students_data)

        assert "Generated invoice for Alice Smith" in caplog.text
        assert "Generated combined invoice for tutors4u" in caplog.text

