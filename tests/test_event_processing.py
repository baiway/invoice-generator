"""
Tests for src/event_processing.py event classification logic.
"""

import pytest
from src.event_processing import (
    classify_event,
    extract_blue_education_name,
    extract_in_person_name,
    match_attendee_email,
)


class TestClassifyEvent:
    """Tests for classify_event function."""

    def test_email_classification(self):
        """Events with non-self attendees should be classified as 'email'."""
        attendees = [
            {"email": "tutor@example.com", "self": True},
            {"email": "student@example.com", "self": False}
        ]
        event_type, name = classify_event("Any title", attendees)
        assert event_type == "email"
        assert name is None

    def test_pmt_classification(self):
        """Events with PMT in title should be classified as 'pmt'."""
        attendees = [{"email": "tutor@example.com", "self": True}]
        event_type, name = classify_event("PMT payment", attendees)
        assert event_type == "pmt"
        assert name is None

    def test_blue_education_classification(self):
        """Blue Education events should extract student name."""
        attendees = [{"email": "tutor@example.com", "self": True}]
        event_type, name = classify_event("John Smith BAC Physics", attendees)
        assert event_type == "blue_education"
        assert name == "John Smith"

    def test_in_person_classification(self):
        """In-person events should extract student name."""
        attendees = [{"email": "tutor@example.com", "self": True}]
        event_type, name = classify_event("Tutoring Alice Johnson", attendees)
        assert event_type == "in_person"
        assert name == "Alice Johnson"

    def test_unknown_classification(self):
        """Events that don't match patterns should be 'unknown'."""
        attendees = [{"email": "tutor@example.com", "self": True}]
        event_type, name = classify_event("Random meeting", attendees)
        assert event_type == "unknown"
        assert name is None


class TestExtractBlueEducationName:
    """Tests for extract_blue_education_name function."""

    def test_standard_format(self):
        """Standard BAC format should extract first and last name."""
        assert extract_blue_education_name("John Smith BAC") == "John Smith"

    def test_with_additional_info(self):
        """Additional info should be ignored."""
        assert extract_blue_education_name("Alice Jones BAC Maths") == "Alice Jones"

    def test_insufficient_parts(self):
        """Events with only one word should raise IndexError."""
        with pytest.raises(IndexError):
            extract_blue_education_name("BAC")


class TestExtractInPersonName:
    """Tests for extract_in_person_name function."""

    def test_simple_name(self):
        """Simple names should be extracted correctly."""
        assert extract_in_person_name("Tutoring Alice") == "Alice"

    def test_full_name(self):
        """Full names with spaces should be preserved."""
        assert extract_in_person_name("Tutoring Bob Smith Jones") == "Bob Smith Jones"

    def test_whitespace_handling(self):
        """Leading/trailing whitespace should be stripped."""
        assert extract_in_person_name("Tutoring  Alice  ") == "Alice"


class TestMatchAttendeeEmail:
    """Tests for match_attendee_email function."""

    def test_successful_match(self, sample_students_data):
        """Email match should return student name."""
        attendees = [{"email": "alice@example.com"}]
        result = match_attendee_email(attendees, sample_students_data)
        assert result == "Alice Smith"

    def test_secondary_email_match(self, sample_students_data):
        """Should match any email in student's email list."""
        attendees = [{"email": "alice@school.edu"}]
        result = match_attendee_email(attendees, sample_students_data)
        assert result == "Alice Smith"

    def test_no_match(self, sample_students_data):
        """Unknown email should return None."""
        attendees = [{"email": "unknown@example.com"}]
        result = match_attendee_email(attendees, sample_students_data)
        assert result is None

    def test_empty_attendees(self, sample_students_data):
        """Empty attendee list should return None."""
        result = match_attendee_email([], sample_students_data)
        assert result is None

    def test_attendee_without_email(self, sample_students_data):
        """Attendees without email field should be skipped."""
        attendees = [{"name": "Someone"}]
        result = match_attendee_email(attendees, sample_students_data)
        assert result is None


class TestAttendeeMatch:
    """Tests for attendee_match function."""

    def test_successful_email_match_returns_student_name(
        self, sample_students_data
    ):
        """Successful email match should return student name."""
        from src.event_processing import attendee_match

        attendees = [{"email": "alice@example.com"}]
        result = attendee_match(attendees, sample_students_data)
        assert result == "Alice Smith"

    def test_no_match_logs_warning_and_returns_empty_string(
        self, sample_students_data, caplog
    ):
        """No match should log warning and return empty string."""
        import logging
        from src.event_processing import attendee_match

        attendees = [{"email": "unknown@example.com"}]

        with caplog.at_level(logging.WARNING):
            result = attendee_match(attendees, sample_students_data)

        assert result == ""
        assert "Attendees not found in students.json" in caplog.text
        assert "unknown@example.com" in caplog.text


class TestProcessEvents:
    """Tests for process_events function."""

    def test_process_email_based_events(
        self, sample_students_data, sample_contact_details_model
    ):
        """Email-based events should be matched via attendee email."""
        from src.event_processing import process_events

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
            [],
            sample_contact_details_model
        )

        assert len(df) == 1
        assert df.iloc[0]["student"] == "Alice Smith"
        assert df.iloc[0]["rate"] == 50.0

    def test_process_blue_education_events(
        self, comprehensive_students_data, sample_contact_details_model
    ):
        """Blue Education events should extract name from title."""
        from src.event_processing import process_events

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
            [],
            sample_contact_details_model
        )

        assert len(df) == 1
        assert df.iloc[0]["student"] == "Charlie Brown"
        assert df.iloc[0]["client_type"] == "blue_education"

    def test_process_in_person_events(
        self, sample_students_data, sample_contact_details_model
    ):
        """In-person events should extract name from title."""
        from src.event_processing import process_events

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
            [],
            sample_contact_details_model
        )

        assert len(df) == 1
        assert df.iloc[0]["student"] == "Alice Smith"

    def test_skip_pmt_events(
        self, sample_students_data, sample_contact_details_model, caplog
    ):
        """PMT events should be skipped with debug log."""
        import logging
        from src.event_processing import process_events

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
                [],
                sample_contact_details_model
            )

        assert len(df) == 0
        assert "Skipping PMT event" in caplog.text

    def test_skip_unknown_format_events(
        self, sample_students_data, sample_contact_details_model, caplog
    ):
        """Unknown format events should be skipped with warning log."""
        import logging
        from src.event_processing import process_events

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
                [],
                sample_contact_details_model
            )

        assert len(df) == 0
        assert "Skipping event with unexpected format" in caplog.text
        assert "Doctor appointment" in caplog.text

    def test_skip_events_with_no_title(
        self, sample_students_data, sample_contact_details_model, caplog
    ):
        """Events with no title should be skipped with debug log."""
        import logging
        from src.event_processing import process_events

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
                [],
                sample_contact_details_model
            )

        assert len(df) == 0
        assert "Skipping event with no title" in caplog.text

    def test_skip_events_where_student_name_cannot_be_extracted(
        self, sample_students_data, sample_contact_details_model, caplog
    ):
        """Events where student name can't be extracted should be skipped."""
        import logging
        from src.event_processing import process_events

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
                [],
                sample_contact_details_model
            )

        assert len(df) == 0
        assert "Could not extract student_name" in caplog.text

    def test_filter_by_students_to_invoice_list(
        self, sample_students_data, sample_contact_details_model
    ):
        """Should only process events for specified students."""
        from src.event_processing import process_events

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
            ["Alice Smith"],
            sample_contact_details_model
        )

        assert len(df) == 1
        assert df.iloc[0]["student"] == "Alice Smith"

    def test_student_not_in_student_data_logs_error(
        self, sample_students_data, sample_contact_details_model, caplog
    ):
        """Student not found in student_data should log error."""
        import logging
        from src.event_processing import process_events

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
                [],
                sample_contact_details_model
            )

        assert len(df) == 0
        assert "Student 'Unknown Student' not found in students.json" in caplog.text

    def test_dataframe_datetime_conversion_to_utc(
        self, sample_students_data, sample_contact_details_model
    ):
        """DataFrame start/end columns should be converted to UTC datetime."""
        import pandas as pd
        from src.event_processing import process_events

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
            [],
            sample_contact_details_model
        )

        # Verify datetime columns are pandas datetime with UTC timezone
        assert pd.api.types.is_datetime64_any_dtype(df["start"])
        assert pd.api.types.is_datetime64_any_dtype(df["end"])
        assert df["start"].dt.tz is not None  # Has timezone

    def test_empty_events_list_returns_empty_dataframe(
        self, sample_students_data, sample_contact_details_model
    ):
        """Empty events list should return empty DataFrame with correct columns."""
        from src.event_processing import process_events

        df = process_events(
            [],
            sample_students_data,
            [],
            sample_contact_details_model
        )

        assert len(df) == 0
        assert list(df.columns) == ["student", "start", "end", "rate", "client_type"]

    def test_logging_summary_processed_lessons(
        self, sample_students_data, sample_contact_details_model, caplog
    ):
        """Should log summary of processed lessons."""
        import logging
        from src.event_processing import process_events

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
            df = process_events(
                events,
                sample_students_data,
                [],
                sample_contact_details_model
            )

        assert "Processed 2 lessons from 2 events" in caplog.text
