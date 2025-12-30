"""
Tests for src/invoice_generator.py PDF generation and invoice creation.

This module tests invoice generation logic including PDF creation,
calculations, and formatting. PDFs are actually generated to verify
the full rendering pipeline works correctly.
"""

import pytest
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone
import calendar

from src.invoice_generator import (
    get_invoice_period,
    extract_page_content,
    write_invoices,
    print_inactive_students,
)
from src.models import StudentInfo


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


class TestWriteInvoices:
    """Tests for write_invoices function."""

    def test_creates_output_directory_if_not_exists(
        self, tmp_path, monkeypatch, sample_lessons_dataframe,
        sample_bank_details_model, sample_contact_details_model
    ):
        """Should create output directory if it doesn't exist."""
        output_dir = tmp_path / "new_output"
        assert not output_dir.exists()

        monkeypatch.setattr("src.invoice_generator.OUTPUT_DIR", str(output_dir))

        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 31, tzinfo=timezone.utc)

        write_invoices(
            sample_lessons_dataframe,
            start,
            end,
            sample_bank_details_model,
            sample_contact_details_model
        )

        assert output_dir.exists()
        assert output_dir.is_dir()

    def test_generates_pdf_for_private_client(
        self, tmp_path, monkeypatch, sample_bank_details_model,
        sample_contact_details_model
    ):
        """Should generate PDF file for private client."""
        output_dir = tmp_path / "invoices"
        monkeypatch.setattr("src.invoice_generator.OUTPUT_DIR", str(output_dir))

        # Create lessons DataFrame with private client
        lessons = pd.DataFrame({
            "student": ["Alice Smith"],
            "start": [datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)],
            "end": [datetime(2024, 1, 15, 11, 0, tzinfo=timezone.utc)],
            "rate": [50.0],
            "client_type": ["private"]
        })

        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 31, tzinfo=timezone.utc)

        write_invoices(
            lessons,
            start,
            end,
            sample_bank_details_model,
            sample_contact_details_model
        )

        pdf_file = output_dir / "alice-smith-invoice.pdf"
        assert pdf_file.exists()
        assert pdf_file.stat().st_size > 0

    def test_private_client_filename_format(
        self, tmp_path, monkeypatch, sample_bank_details_model,
        sample_contact_details_model
    ):
        """Private client PDFs should use lowercase-hyphenated filenames."""
        output_dir = tmp_path / "invoices"
        monkeypatch.setattr("src.invoice_generator.OUTPUT_DIR", str(output_dir))

        lessons = pd.DataFrame({
            "student": ["Alice Mary Smith"],
            "start": [datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)],
            "end": [datetime(2024, 1, 15, 11, 0, tzinfo=timezone.utc)],
            "rate": [50.0],
            "client_type": ["private"]
        })

        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 31, tzinfo=timezone.utc)

        write_invoices(
            lessons,
            start,
            end,
            sample_bank_details_model,
            sample_contact_details_model
        )

        # Check filename is lowercase with hyphens
        pdf_file = output_dir / "alice-mary-smith-invoice.pdf"
        assert pdf_file.exists()

    def test_generates_combined_pdf_for_agency(
        self, tmp_path, monkeypatch, sample_bank_details_model,
        sample_contact_details_model
    ):
        """Should generate combined PDF for agency clients."""
        output_dir = tmp_path / "invoices"
        monkeypatch.setattr("src.invoice_generator.OUTPUT_DIR", str(output_dir))

        lessons = pd.DataFrame({
            "student": ["Bob Jones"],
            "start": [datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)],
            "end": [datetime(2024, 1, 15, 11, 30, tzinfo=timezone.utc)],
            "rate": [40.0],
            "client_type": ["tutors4u"]
        })

        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 31, tzinfo=timezone.utc)

        write_invoices(
            lessons,
            start,
            end,
            sample_bank_details_model,
            sample_contact_details_model
        )

        pdf_file = output_dir / "tutors4u-invoice.pdf"
        assert pdf_file.exists()
        assert pdf_file.stat().st_size > 0

    def test_agency_pdf_contains_multiple_students(
        self, tmp_path, monkeypatch, sample_bank_details_model,
        sample_contact_details_model
    ):
        """Agency PDF should combine multiple students in one file."""
        output_dir = tmp_path / "invoices"
        monkeypatch.setattr("src.invoice_generator.OUTPUT_DIR", str(output_dir))

        # Two students from same agency
        lessons = pd.DataFrame({
            "student": ["Student A", "Student A", "Student B"],
            "start": [
                datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc),
                datetime(2024, 1, 16, 10, 0, tzinfo=timezone.utc),
                datetime(2024, 1, 17, 10, 0, tzinfo=timezone.utc)
            ],
            "end": [
                datetime(2024, 1, 15, 11, 0, tzinfo=timezone.utc),
                datetime(2024, 1, 16, 11, 0, tzinfo=timezone.utc),
                datetime(2024, 1, 17, 11, 0, tzinfo=timezone.utc)
            ],
            "rate": [40.0, 40.0, 40.0],
            "client_type": ["tutors4u", "tutors4u", "tutors4u"]
        })

        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 31, tzinfo=timezone.utc)

        write_invoices(
            lessons,
            start,
            end,
            sample_bank_details_model,
            sample_contact_details_model
        )

        # Should have one combined PDF, not separate PDFs
        pdf_file = output_dir / "tutors4u-invoice.pdf"
        assert pdf_file.exists()
        # Should be larger than single student PDF (contains both)
        assert pdf_file.stat().st_size > 1000

    def test_qr_code_url_amount_in_pence(
        self, tmp_path, monkeypatch, sample_contact_details_model
    ):
        """QR code URL should format amount in pence (£50.00 → 5000)."""
        from src.models import BankDetails

        # Create bank details with QR code template
        bank = BankDetails(
            name="Test",
            sort_code="040004",
            account_number="12345678",
            bank="Test Bank",
            link="https://pay.test?amt={amount}",
            QR_code="https://qr.test?amt={amount}"
        )

        output_dir = tmp_path / "invoices"
        monkeypatch.setattr("src.invoice_generator.OUTPUT_DIR", str(output_dir))

        # £125.00 charge (1h @ £50/h + 1.5h @ £50/h = 2.5h × £50/h)
        lessons = pd.DataFrame({
            "student": ["Test Student", "Test Student"],
            "start": [
                datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc),
                datetime(2024, 1, 16, 10, 0, tzinfo=timezone.utc)
            ],
            "end": [
                datetime(2024, 1, 15, 11, 0, tzinfo=timezone.utc),
                datetime(2024, 1, 16, 11, 30, tzinfo=timezone.utc)
            ],
            "rate": [50.0, 50.0],
            "client_type": ["private", "private"]
        })

        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 31, tzinfo=timezone.utc)

        # Capture the rendered HTML by mocking HTML.write_pdf
        rendered_html_capture = []

        def capture_html(string):
            class MockHTML:
                def __init__(self, string):
                    rendered_html_capture.append(string)
                def write_pdf(self, path, stylesheets=None):
                    pass
            return MockHTML(string)

        monkeypatch.setattr("src.invoice_generator.HTML", capture_html)

        write_invoices(
            lessons,
            start,
            end,
            bank,
            sample_contact_details_model
        )

        # QR code should have amount in pence: 125.00 * 100 = 12500
        assert "https://qr.test?amt=12500" in rendered_html_capture[0]

    def test_payment_link_url_amount_in_pounds(
        self, tmp_path, monkeypatch, sample_contact_details_model
    ):
        """Payment link URL should format amount in pounds (£50.00 → 50.0)."""
        from src.models import BankDetails

        bank = BankDetails(
            name="Test",
            sort_code="040004",
            account_number="12345678",
            bank="Test Bank",
            link="https://pay.test?amt={amount}",
            QR_code="https://qr.test?amt={amount}"
        )

        output_dir = tmp_path / "invoices"
        monkeypatch.setattr("src.invoice_generator.OUTPUT_DIR", str(output_dir))

        # £50.00 charge
        lessons = pd.DataFrame({
            "student": ["Test Student"],
            "start": [datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)],
            "end": [datetime(2024, 1, 15, 11, 0, tzinfo=timezone.utc)],
            "rate": [50.0],
            "client_type": ["private"]
        })

        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 31, tzinfo=timezone.utc)

        rendered_html_capture = []

        def capture_html(string):
            class MockHTML:
                def __init__(self, string):
                    rendered_html_capture.append(string)
                def write_pdf(self, path, stylesheets=None):
                    pass
            return MockHTML(string)

        monkeypatch.setattr("src.invoice_generator.HTML", capture_html)

        write_invoices(
            lessons,
            start,
            end,
            bank,
            sample_contact_details_model
        )

        # Payment link should have amount in pounds: 50.0
        assert "https://pay.test?amt=50.0" in rendered_html_capture[0]

    def test_calculates_total_hours_correctly(
        self, tmp_path, monkeypatch, sample_bank_details_model,
        sample_contact_details_model
    ):
        """Should correctly sum session durations (1h + 1.5h = 2.5h)."""
        output_dir = tmp_path / "invoices"
        monkeypatch.setattr("src.invoice_generator.OUTPUT_DIR", str(output_dir))

        lessons = pd.DataFrame({
            "student": ["Test Student", "Test Student"],
            "start": [
                datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc),
                datetime(2024, 1, 16, 10, 0, tzinfo=timezone.utc)
            ],
            "end": [
                datetime(2024, 1, 15, 11, 0, tzinfo=timezone.utc),  # 1 hour
                datetime(2024, 1, 16, 11, 30, tzinfo=timezone.utc)  # 1.5 hours
            ],
            "rate": [50.0, 50.0],
            "client_type": ["private", "private"]
        })

        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 31, tzinfo=timezone.utc)

        rendered_html_capture = []

        def capture_html(string):
            class MockHTML:
                def __init__(self, string):
                    rendered_html_capture.append(string)
                def write_pdf(self, path, stylesheets=None):
                    pass
            return MockHTML(string)

        monkeypatch.setattr("src.invoice_generator.HTML", capture_html)

        write_invoices(
            lessons,
            start,
            end,
            sample_bank_details_model,
            sample_contact_details_model
        )

        # Total charge: 2.5h * £50/h = £125
        html = rendered_html_capture[0]
        # The HTML should contain the calculated charge somewhere
        assert "125" in html  # Total charge should be present

    def test_returns_absolute_path_to_output_directory(
        self, tmp_path, monkeypatch, sample_lessons_dataframe,
        sample_bank_details_model, sample_contact_details_model
    ):
        """Should return absolute path to output directory."""
        output_dir = tmp_path / "invoices"
        monkeypatch.setattr("src.invoice_generator.OUTPUT_DIR", str(output_dir))

        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 31, tzinfo=timezone.utc)

        result = write_invoices(
            sample_lessons_dataframe,
            start,
            end,
            sample_bank_details_model,
            sample_contact_details_model
        )

        assert Path(result).is_absolute()
        assert str(output_dir.resolve()) == result

    def test_logs_invoice_generation_for_private_clients(
        self, tmp_path, monkeypatch, sample_bank_details_model,
        sample_contact_details_model, caplog
    ):
        """Should log invoice generation for private clients."""
        import logging

        output_dir = tmp_path / "invoices"
        monkeypatch.setattr("src.invoice_generator.OUTPUT_DIR", str(output_dir))

        lessons = pd.DataFrame({
            "student": ["Alice Smith"],
            "start": [datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)],
            "end": [datetime(2024, 1, 15, 11, 0, tzinfo=timezone.utc)],
            "rate": [50.0],
            "client_type": ["private"]
        })

        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 31, tzinfo=timezone.utc)

        with caplog.at_level(logging.INFO):
            write_invoices(
                lessons,
                start,
                end,
                sample_bank_details_model,
                sample_contact_details_model
            )

        assert "Generated invoice for Alice Smith" in caplog.text

    def test_logs_combined_invoice_for_agencies(
        self, tmp_path, monkeypatch, sample_bank_details_model,
        sample_contact_details_model, caplog
    ):
        """Should log combined invoice generation for agencies."""
        import logging

        output_dir = tmp_path / "invoices"
        monkeypatch.setattr("src.invoice_generator.OUTPUT_DIR", str(output_dir))

        lessons = pd.DataFrame({
            "student": ["Bob Jones"],
            "start": [datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)],
            "end": [datetime(2024, 1, 15, 11, 0, tzinfo=timezone.utc)],
            "rate": [40.0],
            "client_type": ["tutors4u"]
        })

        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 31, tzinfo=timezone.utc)

        with caplog.at_level(logging.INFO):
            write_invoices(
                lessons,
                start,
                end,
                sample_bank_details_model,
                sample_contact_details_model
            )

        assert "Generated combined invoice for tutors4u" in caplog.text


class TestPrintInactiveStudents:
    """Tests for print_inactive_students function."""

    def test_logs_inactive_students_not_in_lessons(
        self, sample_lessons_dataframe, caplog
    ):
        """Should log students not seen in lesson data."""
        import logging

        student_data = {
            "Alice Smith": StudentInfo(
                client_type="private",
                rate=50.0,
                emails=["alice@example.com"]
            ),
            "Bob Jones": StudentInfo(
                client_type="tutors4u",
                rate=40.0,
                emails=["bob@example.com"]
            ),
            "Charlie Brown": StudentInfo(
                client_type="private",
                rate=45.0,
                emails=["charlie@example.com"]
            )
        }

        # sample_lessons_dataframe only has Alice and Bob
        with caplog.at_level(logging.INFO):
            print_inactive_students(sample_lessons_dataframe, student_data)

        assert "Charlie Brown not seen in this period" in caplog.text

    def test_no_log_for_active_students(self, sample_lessons_dataframe, caplog):
        """Should not log students who appear in lessons."""
        import logging

        student_data = {
            "Alice Smith": StudentInfo(
                client_type="private",
                rate=50.0,
                emails=["alice@example.com"]
            ),
            "Bob Jones": StudentInfo(
                client_type="tutors4u",
                rate=40.0,
                emails=["bob@example.com"]
            )
        }

        with caplog.at_level(logging.INFO):
            print_inactive_students(sample_lessons_dataframe, student_data)

        # Alice and Bob are in lessons, should not be logged as inactive
        assert "Alice Smith not seen" not in caplog.text
        assert "Bob Jones not seen" not in caplog.text

    def test_no_logs_when_all_students_active(
        self, sample_lessons_dataframe, caplog
    ):
        """Should not log anything when all students are active."""
        import logging

        # Only students who are in the lessons DataFrame
        student_data = {
            "Alice Smith": StudentInfo(
                client_type="private",
                rate=50.0,
                emails=["alice@example.com"]
            ),
            "Bob Jones": StudentInfo(
                client_type="tutors4u",
                rate=40.0,
                emails=["bob@example.com"]
            )
        }

        with caplog.at_level(logging.INFO):
            print_inactive_students(sample_lessons_dataframe, student_data)

        assert "not seen in this period" not in caplog.text
