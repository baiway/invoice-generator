"""
Tests for invoice_generator/cli.py argument parsing and validation.

This module tests the command line surface: flag parsing, student name
validation against `students.json`, and invoice period resolution.
"""

import logging
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

from invoice_generator.cli import (
    main,
    parse_args,
    print_inactive_students,
    validate_students,
    validate_invoice_period,
)
from invoice_generator.models import StudentInfo
from invoice_generator.utils import get_last_full_month


class TestParseArgs:
    """Tests for parse_args function."""

    def test_defaults_to_empty_selection(self):
        """No flags should leave every option unset."""
        args = parse_args([])
        assert args.only == []
        assert args.start is None
        assert args.end is None

    def test_only_accepts_several_names(self):
        """`--only` should collect all following names."""
        args = parse_args(["--only", "Alice Smith", "Bob Jones"])
        assert args.only == ["Alice Smith", "Bob Jones"]

    def test_from_and_to_map_to_start_and_end(self):
        """`--from` and `--to` should land in `start` and `end`."""
        args = parse_args(["--from", "2024-01-01", "--to", "2024-01-31"])
        assert args.start == "2024-01-01"
        assert args.end == "2024-01-31"

    def test_directories_default_to_cwd_relative_paths(self):
        """Data and output directories default to the documented names."""
        args = parse_args([])
        assert args.data_dir == "data"
        assert args.output_dir == "invoices"

    def test_directories_can_be_overridden(self):
        """`--data-dir` and `--output-dir` should be honoured."""
        args = parse_args(["--data-dir", "/srv/tutoring",
                           "--output-dir", "/srv/invoices"])
        assert args.data_dir == "/srv/tutoring"
        assert args.output_dir == "/srv/invoices"

    def test_unknown_flag_exits(self):
        """argparse should reject unrecognised flags."""
        with pytest.raises(SystemExit):
            parse_args(["--nonsense"])


class TestValidateStudents:
    """Tests for validate_students function."""

    def test_no_names_is_accepted(self, sample_students_data):
        """No `--only` means all students, so nothing needs validating."""
        validate_students([], sample_students_data)

    def test_known_names_are_accepted(self, sample_students_data):
        """Names present in students.json should pass."""
        validate_students(["Alice Smith", "Bob Jones"], sample_students_data)

    def test_unknown_name_raises(self, sample_students_data):
        """An unrecognised name should raise, naming the offender."""
        with pytest.raises(ValueError, match="Carol Brown"):
            validate_students(["Alice Smith", "Carol Brown"], sample_students_data)

    def test_names_are_case_sensitive(self, sample_students_data):
        """Matching is case-sensitive, as documented in `--only`."""
        with pytest.raises(ValueError, match="alice smith"):
            validate_students(["alice smith"], sample_students_data)


class TestValidateInvoicePeriod:
    """Tests for validate_invoice_period function."""

    def test_end_without_start_raises(self):
        """`--to` alone is ambiguous and should be rejected."""
        with pytest.raises(ValueError, match="cannot be specified without"):
            validate_invoice_period(None, "2024-01-31")

    def test_explicit_range_is_parsed(self):
        """Both dates given should come back as datetimes."""
        start, end = validate_invoice_period("2024-01-01", "2024-01-31")
        assert start == datetime(2024, 1, 1)
        assert end == datetime(2024, 1, 31, 23, 59, 59)

    def test_end_covers_the_whole_final_day(self):
        """The end date should stretch to the last second of the day."""
        _, end = validate_invoice_period("2024-01-01", "2024-01-01")
        assert (end.hour, end.minute, end.second) == (23, 59, 59)

    def test_start_only_ends_today(self):
        """`--from` without `--to` should run up to today."""
        start, end = validate_invoice_period("2024-01-01", None)
        assert start == datetime(2024, 1, 1)
        assert end.date() == datetime.today().date()

    def test_neither_uses_last_full_month(self):
        """No dates at all should fall back to the last full month."""
        expected_start, expected_end = get_last_full_month()
        start, end = validate_invoice_period(None, None)
        assert start.strftime("%Y-%m-%d") == expected_start
        assert end.strftime("%Y-%m-%d") == expected_end

    def test_invalid_format_raises(self):
        """Dates outside YYYY-MM-DD should be rejected."""
        with pytest.raises(ValueError, match="Invalid date format"):
            validate_invoice_period("01/01/2024", "31/01/2024")

    def test_start_after_end_raises(self):
        """A reversed range should be rejected."""
        with pytest.raises(ValueError, match="cannot be later than"):
            validate_invoice_period("2024-02-01", "2024-01-01")


class TestPrintInactiveStudents:
    """Tests for print_inactive_students function."""

    def test_prints_and_logs_inactive_students_only(
        self, sample_lessons, sample_students_data, capsys, caplog
    ):
        """Students not seen should be shown on screen, and only them."""
        student_data = {
            **sample_students_data,
            "Charlie Brown": StudentInfo(client_type="private", rate=45.0),
        }

        with caplog.at_level(logging.INFO):
            print_inactive_students(sample_lessons, student_data)

        output = capsys.readouterr().out
        assert "Not seen in this period" in output
        assert "Charlie Brown" in output
        assert "Alice Smith" not in output
        assert "Bob Jones" not in output
        assert "Charlie Brown not seen in this period" in caplog.text

    def test_prints_nothing_when_all_students_active(
        self, sample_lessons, sample_students_data, capsys
    ):
        """Should stay quiet when every student had a lesson."""
        print_inactive_students(sample_lessons, sample_students_data)

        assert capsys.readouterr().out == ""


class TestMain:
    """Tests for the main entry point."""

    @pytest.fixture
    def pipeline(self, monkeypatch):
        """Replace every stage main() drives with a mock."""
        mocks = {}
        for name in (
            "setup_logging", "validate_students", "load_student_data",
            "load_bank_details", "load_contact_details", "authenticate",
            "fetch_events", "process_events", "print_inactive_students",
            "write_invoices", "console",
        ):
            mock = MagicMock(name=name)
            monkeypatch.setattr(f"invoice_generator.cli.{name}", mock)
            mocks[name] = mock
        mocks["setup_logging"].return_value = "invoice-generator.log"
        mocks["write_invoices"].return_value = Path("invoices")
        return mocks

    def test_runs_the_pipeline_in_order(self, pipeline):
        """Events should be fetched, processed, then written as invoices."""
        main(["--from", "2024-01-01", "--to", "2024-01-31"])

        pipeline["authenticate"].assert_called_once()
        pipeline["fetch_events"].assert_called_once_with(
            pipeline["authenticate"].return_value,
            datetime(2024, 1, 1),
            datetime(2024, 1, 31, 23, 59, 59),
        )
        pipeline["process_events"].assert_called_once()
        assert (pipeline["process_events"].call_args.args[0]
                is pipeline["fetch_events"].return_value)
        assert (pipeline["write_invoices"].call_args.args[0]
                is pipeline["process_events"].return_value)

    def test_reports_inactive_students_for_a_full_run(self, pipeline):
        """Without `--only`, inactive students should be reported."""
        main([])

        pipeline["print_inactive_students"].assert_called_once_with(
            pipeline["process_events"].return_value,
            pipeline["load_student_data"].return_value,
        )

    def test_data_dir_flag_reaches_every_loader(self, pipeline):
        """`--data-dir` should redirect all four data files."""
        main(["--data-dir", "/srv/tutoring"])

        data_dir = Path("/srv/tutoring")
        pipeline["load_student_data"].assert_called_once_with(
            data_dir / "students.json"
        )
        pipeline["load_bank_details"].assert_called_once_with(
            data_dir / "bank_details.json"
        )
        pipeline["load_contact_details"].assert_called_once_with(
            data_dir / "contact_details.json"
        )
        pipeline["authenticate"].assert_called_once_with(
            data_dir / "credentials.json", data_dir / "token.json"
        )

    def test_output_dir_flag_reaches_the_renderer(self, pipeline):
        """`--output-dir` should be passed to write_invoices."""
        main(["--output-dir", "/srv/invoices"])

        assert pipeline["write_invoices"].call_args.args[-1] == Path("/srv/invoices")

    def test_skips_inactive_report_when_filtering(self, pipeline):
        """With `--only`, the inactive student report is not wanted."""
        main(["--only", "Alice Smith"])

        pipeline["validate_students"].assert_called_once_with(
            ["Alice Smith"], pipeline["load_student_data"].return_value
        )
        pipeline["print_inactive_students"].assert_not_called()
