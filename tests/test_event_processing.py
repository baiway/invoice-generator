"""
Tests for src/invoice_generator/event_processing.py event classification logic.
"""

import logging
import pytest
import pandas as pd
from invoice_generator.event_processing import (
    identify_student,
    is_billable,
    process_events,
)


class TestIsBillable:
    """Tests for is_billable filter that excludes cancelled events."""

    def test_confirmed_event_is_billable(self):
        event = {
            "status": "confirmed",
            "summary": "Mark Mai BAC Bailey iG_GCSE Physics AQA_5",
        }
        assert is_billable(event) is True

    def test_cancelled_status_is_not_billable(self):
        event = {
            "status": "cancelled",
            "summary": "Mark Mai BAC Bailey iG_GCSE Physics AQA_5",
        }
        assert is_billable(event) is False

    def test_canceled_summary_prefix_is_not_billable(self):
        event = {
            "status": "confirmed",
            "summary": "Canceled: Mark Mai BAC Bailey iG_GCSE Physics AQA_5",
        }
        assert is_billable(event) is False

    def test_cancelled_summary_prefix_is_not_billable(self):
        event = {
            "status": "confirmed",
            "summary": "Cancelled: Mark Mai BAC Bailey iG_GCSE Physics AQA_5",
        }
        assert is_billable(event) is False

    def test_both_cancelled_status_and_summary_prefix_is_not_billable(self):
        event = {
            "status": "cancelled",
            "summary": "Cancelled: Mark Mai BAC Bailey iG_GCSE Physics AQA_5",
        }
        assert is_billable(event) is False

    def test_summary_prefix_check_is_case_insensitive(self):
        event = {"status": "confirmed", "summary": "CANCELLED: Some session"}
        assert is_billable(event) is False

    def test_missing_status_field_defaults_to_billable(self):
        event = {"summary": "Some session"}
        assert is_billable(event) is True

    def test_empty_summary_is_still_billable(self):
        event = {"status": "confirmed", "summary": ""}
        assert is_billable(event) is True

    def test_none_summary_is_still_billable(self):
        event = {"status": "confirmed", "summary": None}
        assert is_billable(event) is True


ME = {"email": "tutor@example.com", "self": True}


def event(summary, *attendees):
    """A minimal calendar event."""
    return {"summary": summary, "attendees": [ME, *attendees]}


class TestIdentifyStudent:
    """Tests for identify_student function."""

    def test_matches_invited_attendee_by_email(self, sample_students_data):
        """Events with other attendees should be matched by email."""
        e = event("Any title", {"email": "alice@example.com"})
        assert identify_student(e, sample_students_data) == "Alice Smith"

    def test_matches_any_of_a_students_emails(self, sample_students_data):
        """Should match any email in the student's list."""
        e = event("Any title", {"email": "alice@school.edu"})
        assert identify_student(e, sample_students_data) == "Alice Smith"

    def test_attendees_take_precedence_over_title(self, sample_students_data):
        """A recognisable title should not override the attendee list."""
        e = event("Tutoring Bob Jones", {"email": "alice@example.com"})
        assert identify_student(e, sample_students_data) == "Alice Smith"

    def test_unknown_attendee_logs_warning(self, sample_students_data, caplog):
        """No email match should log the attendees and return None."""
        e = event("Any title", {"email": "unknown@example.com"})

        with caplog.at_level(logging.WARNING):
            assert identify_student(e, sample_students_data) is None

        assert "Attendees not found in students.json" in caplog.text
        assert "unknown@example.com" in caplog.text

    def test_attendee_without_email_is_ignored(self, sample_students_data):
        """Attendees without an email field should not match anyone."""
        assert identify_student(event("Any", {"name": "Someone"}), sample_students_data) is None

    def test_no_attendees_falls_back_to_title(self):
        """Events with no attendee list at all are matched by title."""
        assert identify_student({"summary": "Tutoring Alice"}, {}) == "Alice"

    def test_pmt_events_are_skipped(self, caplog):
        """PMT events are paid through the agency and so not invoiced."""
        with caplog.at_level(logging.DEBUG):
            assert identify_student(event("PMT - Payment received"), {}) is None
        assert "Skipping PMT event" in caplog.text

    @pytest.mark.parametrize("title, name", [
        ("John Smith BAC", "John Smith"),
        ("Alice Jones BAC Maths", "Alice Jones"),
        ("Mark Mai BAC Bailey iG_GCSE Physics AQA_5", "Mark Mai"),
        ("Anna Maria Lopez BAC Physics", "Anna Maria Lopez"),
    ])
    def test_blue_education_title(self, title, name):
        """The student's name is everything before "BAC"."""
        assert identify_student(event(title), {}) == name

    @pytest.mark.parametrize("title, name", [
        ("Tutoring Alice", "Alice"),
        ("Tutoring Bob Smith Jones", "Bob Smith Jones"),
        ("Tutoring  Alice  ", "Alice"),
    ])
    def test_in_person_title(self, title, name):
        """The student's name is everything after "Tutoring"."""
        assert identify_student(event(title), {}) == name

    def test_bac_must_be_a_whole_word(self):
        """A surname starting "BAC" is not a Blue Education booking."""
        assert identify_student(event("Tutoring Joe BACKHOUSE"), {}) == "Joe BACKHOUSE"

    @pytest.mark.parametrize("title", [
        "Random meeting",
        "BAC",  # no name before it
        "Tutoring",  # no name after it
        "Tutoring   ",
    ])
    def test_unrecognised_title_logs_warning(self, title, caplog):
        """Titles that don't name a student are logged and skipped."""
        with caplog.at_level(logging.WARNING):
            assert identify_student(event(title), {}) is None
        assert "unexpected format" in caplog.text


class TestProcessEvents:
    """Tests for process_events function."""

    def test_process_email_based_events(
        self, sample_students_data
    ):
        """Email-based events should be matched via attendee email."""

        events = [
            {
                "summary": "Tutoring Session",
                "attendees": [
                    {"email": "tutor@example.com", "self": True},
                    {"email": "alice@example.com", "self": False}
                ],
                "start": {"dateTime": "2024-01-15T10:00:00Z"},
                "end": {"dateTime": "2024-01-15T11:00:00Z"}
            }
        ]

        df = process_events(
            events,
            sample_students_data,
            []
        )

        assert len(df) == 1
        assert df.iloc[0]["student"] == "Alice Smith"
        assert df.iloc[0]["rate"] == 50.0

    def test_process_blue_education_events(
        self, comprehensive_students_data
    ):
        """Blue Education events should extract name from title."""

        events = [
            {
                "summary": "Charlie Brown BAC Physics",
                "attendees": [{"email": "tutor@example.com", "self": True}],
                "start": {"dateTime": "2024-01-16T14:00:00Z"},
                "end": {"dateTime": "2024-01-16T15:30:00Z"}
            }
        ]

        df = process_events(
            events,
            comprehensive_students_data,
            []
        )

        assert len(df) == 1
        assert df.iloc[0]["student"] == "Charlie Brown"
        assert df.iloc[0]["client_type"] == "blue_education"

    def test_process_in_person_events(
        self, sample_students_data
    ):
        """In-person events should extract name from title."""

        events = [
            {
                "summary": "Tutoring Alice Smith",
                "attendees": [{"email": "tutor@example.com", "self": True}],
                "start": {"dateTime": "2024-01-17T10:00:00Z"},
                "end": {"dateTime": "2024-01-17T11:00:00Z"}
            }
        ]

        df = process_events(
            events,
            sample_students_data,
            []
        )

        assert len(df) == 1
        assert df.iloc[0]["student"] == "Alice Smith"

    def test_skip_pmt_events(
        self, sample_students_data, caplog
    ):
        """PMT events should be skipped with debug log."""

        events = [
            {
                "summary": "PMT - Payment received",
                "attendees": [{"email": "tutor@example.com", "self": True}],
                "start": {"dateTime": "2024-01-18T10:00:00Z"},
                "end": {"dateTime": "2024-01-18T10:15:00Z"}
            }
        ]

        with caplog.at_level(logging.DEBUG):
            df = process_events(
                events,
                sample_students_data,
                []
            )

        assert len(df) == 0
        assert "Skipping PMT event" in caplog.text

    def test_skip_unknown_format_events(
        self, sample_students_data, caplog
    ):
        """Unknown format events should be skipped with warning log."""

        events = [
            {
                "summary": "Doctor appointment",
                "attendees": [{"email": "tutor@example.com", "self": True}],
                "start": {"dateTime": "2024-01-19T09:00:00Z"},
                "end": {"dateTime": "2024-01-19T09:30:00Z"}
            }
        ]

        with caplog.at_level(logging.WARNING):
            df = process_events(
                events,
                sample_students_data,
                []
            )

        assert len(df) == 0
        assert "Skipping event with unexpected format" in caplog.text
        assert "Doctor appointment" in caplog.text

    def test_skip_events_with_no_title(
        self, sample_students_data, caplog
    ):
        """Events with no title should be skipped with debug log."""

        events = [
            {
                "summary": "",
                "attendees": [{"email": "tutor@example.com", "self": True}],
                "start": {"dateTime": "2024-01-20T10:00:00Z"},
                "end": {"dateTime": "2024-01-20T11:00:00Z"}
            }
        ]

        with caplog.at_level(logging.DEBUG):
            df = process_events(
                events,
                sample_students_data,
                []
            )

        assert len(df) == 0
        assert "Skipping event with no title" in caplog.text

    def test_skip_events_with_unknown_attendees(
        self, sample_students_data, caplog
    ):
        """Events whose attendees match no student should be skipped."""

        # Email-based event but attendee not in student_data
        events = [
            {
                "summary": "Random Session",
                "attendees": [
                    {"email": "tutor@example.com", "self": True},
                    {"email": "unknown@example.com", "self": False}
                ],
                "start": {"dateTime": "2024-01-21T10:00:00Z"},
                "end": {"dateTime": "2024-01-21T11:00:00Z"}
            }
        ]

        with caplog.at_level(logging.WARNING):
            df = process_events(
                events,
                sample_students_data,
                []
            )

        assert len(df) == 0
        assert "Attendees not found in students.json" in caplog.text

    def test_skip_all_day_events(self, sample_students_data, caplog):
        """All-day events have no times to bill, so are skipped, not a crash."""
        events = [
            {
                "summary": "Tutoring Alice Smith",
                "start": {"date": "2024-01-15"},
                "end": {"date": "2024-01-16"}
            }
        ]

        with caplog.at_level(logging.WARNING):
            df = process_events(events, sample_students_data, [])

        assert len(df) == 0
        assert "Skipping all-day event: 'Tutoring Alice Smith'" in caplog.text

    def test_filter_by_students_to_invoice_list(
        self, sample_students_data
    ):
        """Should only process events for specified students."""

        events = [
            {
                "summary": "Tutoring Alice Smith",
                "attendees": [{"email": "tutor@example.com", "self": True}],
                "start": {"dateTime": "2024-01-15T10:00:00Z"},
                "end": {"dateTime": "2024-01-15T11:00:00Z"}
            },
            {
                "summary": "Tutoring Bob Jones",
                "attendees": [{"email": "tutor@example.com", "self": True}],
                "start": {"dateTime": "2024-01-16T10:00:00Z"},
                "end": {"dateTime": "2024-01-16T11:00:00Z"}
            }
        ]

        # Only process Alice Smith
        df = process_events(
            events,
            sample_students_data,
            ["Alice Smith"]
        )

        assert len(df) == 1
        assert df.iloc[0]["student"] == "Alice Smith"

    def test_student_not_in_student_data_logs_error(
        self, sample_students_data, caplog
    ):
        """Student not found in student_data should log error."""

        events = [
            {
                "summary": "Tutoring Unknown Student",
                "attendees": [{"email": "tutor@example.com", "self": True}],
                "start": {"dateTime": "2024-01-15T10:00:00Z"},
                "end": {"dateTime": "2024-01-15T11:00:00Z"}
            }
        ]

        with caplog.at_level(logging.ERROR):
            df = process_events(
                events,
                sample_students_data,
                []
            )

        assert len(df) == 0
        assert "Student 'Unknown Student' not found in students.json" in caplog.text

    def test_dataframe_datetime_conversion_to_utc(
        self, sample_students_data
    ):
        """DataFrame start/end columns should be converted to UTC datetime."""

        events = [
            {
                "summary": "Tutoring Alice Smith",
                "attendees": [{"email": "tutor@example.com", "self": True}],
                "start": {"dateTime": "2024-01-15T10:00:00Z"},
                "end": {"dateTime": "2024-01-15T11:00:00Z"}
            }
        ]

        df = process_events(
            events,
            sample_students_data,
            []
        )

        # Verify datetime columns are pandas datetime with UTC timezone
        assert pd.api.types.is_datetime64_any_dtype(df["start"])
        assert pd.api.types.is_datetime64_any_dtype(df["end"])
        assert df["start"].dt.tz is not None  # Has timezone

    def test_empty_events_list_returns_empty_dataframe(
        self, sample_students_data
    ):
        """Empty events list should return empty DataFrame with correct columns."""

        df = process_events(
            [],
            sample_students_data,
            []
        )

        assert len(df) == 0
        assert list(df.columns) == ["student", "start", "end", "rate", "client_type"]

    def test_cancelled_events_excluded_from_dataframe(
        self, sample_students_data
    ):
        """Cancelled events should be filtered out before invoice generation."""

        events = [
            {
                "summary": "Tutoring Alice Smith",
                "status": "confirmed",
                "attendees": [{"email": "tutor@example.com", "self": True}],
                "start": {"dateTime": "2024-01-15T10:00:00Z"},
                "end": {"dateTime": "2024-01-15T11:00:00Z"},
            },
            {
                "summary": "Tutoring Alice Smith",
                "status": "cancelled",
                "attendees": [{"email": "tutor@example.com", "self": True}],
                "start": {"dateTime": "2024-01-16T10:00:00Z"},
                "end": {"dateTime": "2024-01-16T11:00:00Z"},
            },
            {
                "summary": "Cancelled: Tutoring Alice Smith",
                "status": "confirmed",
                "attendees": [{"email": "tutor@example.com", "self": True}],
                "start": {"dateTime": "2024-01-17T10:00:00Z"},
                "end": {"dateTime": "2024-01-17T11:00:00Z"},
            },
        ]

        df = process_events(
            events,
            sample_students_data,
            []
        )

        assert len(df) == 1
        assert df.iloc[0]["student"] == "Alice Smith"
        assert df.iloc[0]["start"].strftime("%Y-%m-%d") == "2024-01-15"

    def test_logging_summary_processed_lessons(
        self, sample_students_data, caplog
    ):
        """Should log summary of processed lessons."""

        events = [
            {
                "summary": "Tutoring Alice Smith",
                "attendees": [{"email": "tutor@example.com", "self": True}],
                "start": {"dateTime": "2024-01-15T10:00:00Z"},
                "end": {"dateTime": "2024-01-15T11:00:00Z"}
            },
            {
                "summary": "Tutoring Bob Jones",
                "attendees": [{"email": "tutor@example.com", "self": True}],
                "start": {"dateTime": "2024-01-16T10:00:00Z"},
                "end": {"dateTime": "2024-01-16T11:00:00Z"}
            }
        ]

        with caplog.at_level(logging.INFO):
            process_events(
                events,
                sample_students_data,
                []
            )

        assert "Processed 2 lessons from 2 events" in caplog.text
