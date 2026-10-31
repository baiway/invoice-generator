"""
Tests for invoice_generator/cli.py argument parsing and validation.

This module tests the command line surface: flag parsing, student name
validation against `students.json`, and invoice period resolution.
"""

import io
import logging
import pytest
from rich.console import Console
from datetime import date, datetime, time, timedelta
from pathlib import Path
from unittest.mock import MagicMock

from invoice_generator.cli import (
    event_time,
    main,
    parse_args,
    print_inactive_students,
    print_skipped_events,
    validate_students,
)
from invoice_generator.event_processing import SkipReason, SkippedEvent
from invoice_generator.models import StudentInfo
from invoice_generator.utils import get_last_full_month


class TestParseArgs:
    """Tests for parse_args function."""

    def test_defaults_to_all_students(self):
        """No `--only` should mean every student."""
        assert parse_args([]).only == []

    def test_only_accepts_several_names(self):
        """`--only` should collect all following names."""
        args = parse_args(["--only", "Alice Smith", "Bob Jones"])
        assert args.only == ["Alice Smith", "Bob Jones"]

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


class TestInvoicePeriod:
    """Tests for how parse_args resolves `--from` and `--to`."""

    def test_explicit_range_is_parsed(self):
        """Both dates given should come back as datetimes, the end
        stretching to the last second of its day."""
        args = parse_args(["--from", "2024-01-01", "--to", "2024-01-31"])
        assert args.start == datetime(2024, 1, 1)
        assert args.end == datetime(2024, 1, 31, 23, 59, 59)

    def test_single_day_period(self):
        """`--from` and `--to` may be the same day."""
        args = parse_args(["--from", "2024-01-01", "--to", "2024-01-01"])
        assert args.end - args.start == timedelta(hours=23, minutes=59, seconds=59)

    def test_start_only_ends_today(self):
        """`--from` without `--to` should run up to the end of today."""
        args = parse_args(["--from", "2024-01-01"])
        assert args.start == datetime(2024, 1, 1)
        assert args.end == datetime.combine(date.today(), time(23, 59, 59))

    def test_neither_uses_last_full_month(self):
        """No dates at all should fall back to the last full month."""
        first_day, last_day = get_last_full_month()
        args = parse_args([])
        assert args.start == first_day
        assert args.end == last_day.replace(hour=23, minute=59, second=59)

    @pytest.mark.parametrize("argv, message", [
        (["--to", "2024-01-31"],
         "argument --to: not allowed without --from"),
        (["--from", "01/01/2024"],
         "argument --from: invalid date '01/01/2024' (expected YYYY-MM-DD)"),
        (["--from", "2024-01-01", "--to", "2024-13-01"],
         "argument --to: invalid date '2024-13-01' (expected YYYY-MM-DD)"),
        (["--from", "2024-02-01", "--to", "2024-01-01"],
         "argument --from: 2024-02-01 is after the end of the invoice "
         "period (2024-01-01)"),
        (["--from", "9999-01-01"],
         "argument --from: 9999-01-01 is after the end of the invoice period"),
    ])
    def test_invalid_period_is_a_usage_error(self, argv, message, capsys):
        """Bad dates should exit with a one-line usage error, as argparse
        does for its own checks, rather than a traceback."""
        with pytest.raises(SystemExit) as exc_info:
            parse_args(argv)

        assert exc_info.value.code == 2
        error = capsys.readouterr().err
        assert error.startswith("usage: ")
        assert message in error


def calendar_event(summary, start, end):
    """A calendar event; `start` and `end` are dateTimes, or dates for an
    all-day event."""
    key = "dateTime" if "T" in start else "date"
    return {"summary": summary, "start": {key: start}, "end": {key: end}}


class TestEventTime:
    """Tests for event_time function."""

    def test_timed_event_in_uk_time(self):
        """Times are shown in UK time: 18:00 UTC is 19:00 in October."""
        e = calendar_event("Tutoring Joe", "2026-10-13T18:00:00Z",
                           "2026-10-13T19:30:00Z")
        assert event_time(e) == "13/10/2026 19:00–20:30"

    def test_all_day_event_has_date_only(self):
        """All-day events have no times to show."""
        e = calendar_event("Mock exams", "2026-10-18", "2026-10-19")
        assert event_time(e) == "18/10/2026"


class TestPrintSkippedEvents:
    """Tests for print_skipped_events function."""

    def test_groups_events_by_reason(self, capsys):
        """Each reason gets a heading, in a fixed order, with its events
        and any detail beneath."""
        skipped = [
            SkippedEvent(
                calendar_event("Tutoring Joe", "2026-10-13T18:00:00Z",
                               "2026-10-13T19:00:00Z"),
                SkipReason.UNKNOWN_ATTENDEES, "joe@example.com",
            ),
            SkippedEvent(
                calendar_event("Chat with Anna", "2026-10-14T09:00:00Z",
                               "2026-10-14T09:30:00Z"),
                SkipReason.UNEXPECTED_FORMAT,
            ),
            SkippedEvent(
                calendar_event("Mark Lee's essay", "2026-10-15T09:00:00Z",
                               "2026-10-15T10:00:00Z"),
                SkipReason.UNEXPECTED_FORMAT,
            ),
        ]

        print_skipped_events(skipped)

        assert capsys.readouterr().out == (
            "\n"
            "Skipped events with an unexpected format:\n"
            "  14/10/2026 10:00–10:30  Chat with Anna\n"
            "  15/10/2026 10:00–11:00  Mark Lee's essay\n"
            "\n"
            "Skipped events whose attendees aren't in students.json:\n"
            "  13/10/2026 19:00–20:00  Tutoring Joe (joe@example.com)\n"
        )

    def test_titles_line_up_after_all_day_events(self, capsys):
        """All-day events are padded so their titles line up."""
        skipped = [
            SkippedEvent(calendar_event("Mock exams", "2026-10-18", "2026-10-19"),
                         SkipReason.ALL_DAY),
            SkippedEvent(calendar_event("Revision day", "2026-10-19", "2026-10-20"),
                         SkipReason.ALL_DAY),
        ]

        print_skipped_events(skipped)

        assert "  18/10/2026" + " " * 14 + "Mock exams\n" in capsys.readouterr().out

    def test_date_and_time_share_a_colour(self, monkeypatch):
        """The date and time are one colour, and the title and detail
        aren't highlighted (rich would otherwise colour the times as if
        they were IPv6 addresses, and any numbers in titles)."""
        output = io.StringIO()
        monkeypatch.setattr(
            "invoice_generator.cli.console",
            Console(file=output, force_terminal=True, color_system="standard"),
        )
        e = calendar_event("Jane Doe BAC Physics_40", "2026-10-13T18:00:00Z",
                           "2026-10-13T19:00:00Z")

        print_skipped_events([SkippedEvent(e, SkipReason.UNKNOWN_STUDENT, "Jane Doe")])

        line = output.getvalue().splitlines()[-1]
        bold_cyan = "\x1b[1;36m"
        assert line == (
            f"  {bold_cyan}13/10/2026 19:00–20:00\x1b[0m"
            "  Jane Doe BAC Physics_40 (Jane Doe)"
        )

    def test_titles_are_not_read_as_markup(self, capsys):
        """Square brackets in a title should be printed as they are."""
        e = calendar_event("[Draft] Tutoring Joe", "2026-10-13T18:00:00Z",
                           "2026-10-13T19:00:00Z")

        print_skipped_events([SkippedEvent(e, SkipReason.UNEXPECTED_FORMAT)])

        assert "[Draft] Tutoring Joe" in capsys.readouterr().out

    def test_long_lines_are_not_wrapped(self, capsys):
        """Long lines are left whole, for the terminal to wrap."""
        e = calendar_event("Tutoring " + "Joe " * 30, "2026-10-13T18:00:00Z",
                           "2026-10-13T19:00:00Z")

        print_skipped_events([SkippedEvent(e, SkipReason.UNEXPECTED_FORMAT)])

        lines = capsys.readouterr().out.strip().split("\n")
        assert len(lines) == 2

    def test_prints_nothing_when_nothing_skipped(self, capsys):
        """No skipped events, no output."""
        print_skipped_events([])

        assert capsys.readouterr().out == ""


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
            "calendar_service", "fetch_events", "process_events", "print_skipped_events",
            "print_inactive_students", "write_invoices", "console",
        ):
            mock = MagicMock(name=name)
            monkeypatch.setattr(f"invoice_generator.cli.{name}", mock)
            mocks[name] = mock
        mocks["setup_logging"].return_value = Path("logs/2026-10-18_13-24-01.log")
        mocks["write_invoices"].return_value = Path("invoices")
        mocks["lessons"], mocks["skipped"] = MagicMock(), MagicMock()
        mocks["process_events"].return_value = (mocks["lessons"], mocks["skipped"])
        return mocks

    def test_runs_the_pipeline_in_order(self, pipeline):
        """Events should be fetched, processed, then written as invoices."""
        main(["--from", "2024-01-01", "--to", "2024-01-31"])

        pipeline["authenticate"].assert_called_once()
        pipeline["calendar_service"].assert_called_once_with(
            pipeline["authenticate"].return_value
        )
        pipeline["fetch_events"].assert_called_once_with(
            pipeline["calendar_service"].return_value,
            datetime(2024, 1, 1),
            datetime(2024, 1, 31, 23, 59, 59),
        )
        pipeline["process_events"].assert_called_once()
        assert (pipeline["process_events"].call_args.args[0]
                is pipeline["fetch_events"].return_value)
        assert pipeline["write_invoices"].call_args.args[0] is pipeline["lessons"]

    def test_asks_for_calendar_access_only(self, pipeline):
        """Invoices need read-only calendar access, and nothing more."""
        main([])

        assert pipeline["authenticate"].call_args.args[2] == [
            "https://www.googleapis.com/auth/calendar.readonly"
        ]

    def test_reports_inactive_students_for_a_full_run(self, pipeline):
        """Without `--only`, inactive students should be reported."""
        main([])

        pipeline["print_inactive_students"].assert_called_once_with(
            pipeline["lessons"], pipeline["load_student_data"].return_value
        )

    def test_follow_ups_come_last(self, pipeline):
        """Skipped events, then inactive students, should follow the
        paths to the invoices and log."""
        output = []
        pipeline["console"].print.side_effect = (
            lambda *args, **kwargs: output.append(args[0] if args else "")
        )
        pipeline["print_skipped_events"].side_effect = (
            lambda skipped: output.append("<skipped events>")
        )
        pipeline["print_inactive_students"].side_effect = (
            lambda lessons, student_data: output.append("<inactive students>")
        )

        main([])

        pipeline["print_skipped_events"].assert_called_once_with(pipeline["skipped"])
        logs = next(i for i, line in enumerate(output) if "Detailed logs" in line)
        assert output[logs + 1:logs + 3] == [
            "<skipped events>", "<inactive students>"
        ]

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
        assert pipeline["authenticate"].call_args.args[:2] == (
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
