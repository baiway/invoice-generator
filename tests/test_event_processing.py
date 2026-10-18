"""
Tests for src/invoice_generator/event_processing.py event classification logic.
"""

import logging
import pytest
from datetime import UTC, date, datetime, timedelta
from invoice_generator.event_processing import (
    SkipReason,
    Unmatched,
    find_student,
    identify_student,
    is_billable,
    process_events,
)
from invoice_generator.models import StudentInfo


class TestIsBillable:
    """Tests for is_billable filter that excludes cancelled events."""

    def test_confirmed_event_is_billable(self):
        event = {
            "status": "confirmed",
            "summary": "Jane Doe BAC Bailey iG_GCSE Physics AQA_5",
        }
        assert is_billable(event) is True

    def test_cancelled_status_is_not_billable(self):
        event = {
            "status": "cancelled",
            "summary": "Jane Doe BAC Bailey iG_GCSE Physics AQA_5",
        }
        assert is_billable(event) is False

    def test_canceled_summary_prefix_is_not_billable(self):
        event = {
            "status": "confirmed",
            "summary": "Canceled: Jane Doe BAC Bailey iG_GCSE Physics AQA_5",
        }
        assert is_billable(event) is False

    def test_cancelled_summary_prefix_is_not_billable(self):
        event = {
            "status": "confirmed",
            "summary": "Cancelled: Jane Doe BAC Bailey iG_GCSE Physics AQA_5",
        }
        assert is_billable(event) is False

    def test_both_cancelled_status_and_summary_prefix_is_not_billable(self):
        event = {
            "status": "cancelled",
            "summary": "Cancelled: Jane Doe BAC Bailey iG_GCSE Physics AQA_5",
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


def students(*names):
    """A students.json listing `names`, all private clients."""
    return {name: StudentInfo(client_type="private", rate=50.0) for name in names}


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

    def test_unknown_attendee_raises(self, sample_students_data):
        """No email match should raise, naming the attendees."""
        e = event("Any title", {"email": "unknown@example.com"})

        with pytest.raises(Unmatched) as exc_info:
            identify_student(e, sample_students_data)

        assert exc_info.value.reason is SkipReason.UNKNOWN_ATTENDEES
        assert exc_info.value.detail == "unknown@example.com"

    def test_attendee_without_email_is_ignored(self, sample_students_data):
        """Attendees without an email field should not match anyone."""
        with pytest.raises(Unmatched) as exc_info:
            identify_student(event("Any", {"name": "Someone"}), sample_students_data)
        assert exc_info.value.detail == "<no email>"

    def test_no_attendees_falls_back_to_title(self):
        """Events with no attendee list at all are matched by title."""
        assert identify_student({"summary": "Tutoring Alice"}, students("Alice")) == "Alice"

    def test_pmt_events_are_skipped(self, caplog):
        """PMT events are paid through the agency and so not invoiced."""
        with caplog.at_level(logging.DEBUG):
            assert identify_student(event("PMT - Payment received"), {}) is None
        assert "Skipping PMT event" in caplog.text

    @pytest.mark.parametrize("title, name", [
        ("John Smith BAC", "John Smith"),
        ("Alice Jones BAC Maths", "Alice Jones"),
        ("Jane Doe BAC Bailey iG_GCSE Physics AQA_5", "Jane Doe"),
        ("Anna Maria Lopez BAC Physics", "Anna Maria Lopez"),
        ("Lee Brown+BAC Bailey IB CS/Python_1", "Lee Brown"),
        ("Joe Bloggs - BAC Maths", "Joe Bloggs"),
    ])
    def test_blue_education_title(self, title, name):
        """The student's name is everything before "BAC", whatever
        separates the two."""
        assert identify_student(event(title), students(name)) == name

    @pytest.mark.parametrize("title, name", [
        ("Tutoring Alice", "Alice"),
        ("Tutoring Bob Smith Jones", "Bob Smith Jones"),
        ("Tutoring  Alice  ", "Alice"),
        ("Tutoring Joe", "Joe Bloggs"),  # first name only
    ])
    def test_in_person_title(self, title, name):
        """The student's name is everything after "Tutoring"."""
        assert identify_student(event(title), students(name)) == name

    def test_bac_must_be_a_whole_word(self):
        """A surname starting "BAC" is not a Blue Education booking."""
        title = "Tutoring Joe BACKHOUSE"
        assert identify_student(event(title), students("Joe BACKHOUSE")) == "Joe BACKHOUSE"

    def test_title_naming_unknown_student_raises(self):
        """A lesson with someone not in students.json should say who."""
        with pytest.raises(Unmatched) as exc_info:
            identify_student(event("Tutoring Zed"), students("Alice"))
        assert exc_info.value.reason is SkipReason.UNKNOWN_STUDENT
        assert exc_info.value.detail == "Zed"

    @pytest.mark.parametrize("title", [
        "Random meeting",
        "Look at Alice's Physics IA",  # names a student, but not a lesson
        "BAC",  # no name before it
        "Tutoring",  # no name after it
        "Tutoring   ",
    ])
    def test_unrecognised_title_raises(self, title):
        """Titles that aren't lessons are reported as unexpected."""
        with pytest.raises(Unmatched) as exc_info:
            identify_student(event(title), students("Alice"))
        assert exc_info.value.reason is SkipReason.UNEXPECTED_FORMAT


class TestFindStudent:
    """Tests for find_student function."""

    ROSTER = students("Alice Smith", "Joe Bloggs", "Anna Lee", "Lee Brown",
                      "Anna Maria Lopez", "Sam", "Sam Smith")

    @pytest.mark.parametrize("name, student", [
        ("Alice Smith", "Alice Smith"),  # full name
        ("Joe", "Joe Bloggs"),  # first name
        ("Anna Maria", "Anna Maria Lopez"),  # first and middle names
        ("joe BLOGGS", "Joe Bloggs"),  # case is ignored
        ("Lee", "Lee Brown"),  # not Anna Lee: names match from the start
        ("Sam", "Sam"),  # a full name wins over "Sam Smith"
    ])
    def test_matches(self, name, student):
        """A full name, or the start of one, picks out the student."""
        assert find_student(name, self.ROSTER) == student

    @pytest.mark.parametrize("name", [
        "Al",  # part of a word
        "Smith",  # surname alone
        "Alice Smithson",
        "Zed",
    ])
    def test_no_match_raises(self, name):
        """Names that aren't the start of anyone's name don't match."""
        with pytest.raises(Unmatched) as exc_info:
            find_student(name, self.ROSTER)
        assert exc_info.value.reason is SkipReason.UNKNOWN_STUDENT
        assert exc_info.value.detail == name

    def test_shared_first_name_is_not_guessed(self):
        """Two students with the same first name: skip, naming both."""
        roster = students("Alice Smith", "Alice Jones")

        with pytest.raises(Unmatched) as exc_info:
            find_student("Alice", roster)

        assert exc_info.value.reason is SkipReason.AMBIGUOUS_STUDENT
        assert "Alice Smith or Alice Jones" in exc_info.value.detail


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

        lessons, skipped = process_events(
            events,
            sample_students_data,
            []
        )

        assert list(lessons) == ["Alice Smith"]
        assert len(lessons["Alice Smith"]) == 1

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

        lessons, skipped = process_events(
            events,
            comprehensive_students_data,
            []
        )

        assert list(lessons) == ["Charlie Brown"]

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

        lessons, skipped = process_events(
            events,
            sample_students_data,
            []
        )

        assert list(lessons) == ["Alice Smith"]

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
            lessons, skipped = process_events(
                events,
                sample_students_data,
                []
            )

        assert (lessons, skipped) == ({}, [])
        assert "Skipping PMT event" in caplog.text

    def test_skip_unknown_format_events(
        self, sample_students_data
    ):
        """Unknown format events should be skipped and reported."""

        events = [
            {
                "summary": "Doctor appointment",
                "attendees": [{"email": "tutor@example.com", "self": True}],
                "start": {"dateTime": "2024-01-19T09:00:00Z"},
                "end": {"dateTime": "2024-01-19T09:30:00Z"}
            }
        ]

        lessons, skipped = process_events(
            events,
            sample_students_data,
            []
        )

        assert lessons == {}
        assert [(s.reason, s.event["summary"]) for s in skipped] == [
            (SkipReason.UNEXPECTED_FORMAT, "Doctor appointment")
        ]

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
            lessons, skipped = process_events(
                events,
                sample_students_data,
                []
            )

        assert (lessons, skipped) == ({}, [])
        assert "Skipping event with no title" in caplog.text

    def test_skip_events_with_unknown_attendees(
        self, sample_students_data
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

        lessons, skipped = process_events(
            events,
            sample_students_data,
            []
        )

        assert lessons == {}
        assert [s.reason for s in skipped] == [SkipReason.UNKNOWN_ATTENDEES]

    def test_skips_are_logged_quietly(self, sample_students_data, caplog):
        """Skipped events are listed at the end of the run, so they are
        logged for the file only, below the console's WARNING level."""
        events = [{"summary": "Doctor appointment",
                   "start": {"dateTime": "2024-01-19T09:00:00Z"},
                   "end": {"dateTime": "2024-01-19T09:30:00Z"}}]

        with caplog.at_level(logging.INFO):
            process_events(events, sample_students_data, [])

        (record,) = [r for r in caplog.records if "Skipped" in r.message]
        assert record.levelno == logging.INFO
        assert record.message == (
            "Skipped 'Doctor appointment' with an unexpected format"
        )

    def test_skip_all_day_events(self, sample_students_data):
        """All-day events have no times to bill, so are skipped, not a crash."""
        events = [
            {
                "summary": "Tutoring Alice Smith",
                "start": {"date": "2024-01-15"},
                "end": {"date": "2024-01-16"}
            }
        ]

        lessons, skipped = process_events(events, sample_students_data, [])

        assert lessons == {}
        assert [s.reason for s in skipped] == [SkipReason.ALL_DAY]

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
        lessons, skipped = process_events(
            events,
            sample_students_data,
            ["Alice Smith"]
        )

        assert list(lessons) == ["Alice Smith"]

    def test_student_not_in_student_data_is_skipped(
        self, sample_students_data
    ):
        """A title naming someone not in students.json is skipped, saying who."""

        events = [
            {
                "summary": "Tutoring Unknown Student",
                "attendees": [{"email": "tutor@example.com", "self": True}],
                "start": {"dateTime": "2024-01-15T10:00:00Z"},
                "end": {"dateTime": "2024-01-15T11:00:00Z"}
            }
        ]

        lessons, skipped = process_events(
            events,
            sample_students_data,
            []
        )

        assert lessons == {}
        assert [(s.reason, s.detail) for s in skipped] == [
            (SkipReason.UNKNOWN_STUDENT, "Unknown Student")
        ]

    def test_lessons_have_timezone_aware_times(self, sample_students_data):
        """Lesson times should keep the offset Google gives them."""
        events = [
            {
                "summary": "Tutoring Alice Smith",
                "start": {"dateTime": "2024-07-15T10:00:00+01:00"},
                "end": {"dateTime": "2024-07-15T11:30:00+01:00"}
            }
        ]

        lessons, _ = process_events(events, sample_students_data, [])
        (lesson,) = lessons["Alice Smith"]

        assert lesson.start == datetime(2024, 7, 15, 9, 0, tzinfo=UTC)
        assert lesson.duration == timedelta(hours=1, minutes=30)

    def test_lessons_are_grouped_by_student_in_calendar_order(
        self, sample_students_data
    ):
        """Each student's lessons should stay in the order Google gave."""
        events = [
            {"summary": f"Tutoring {name}",
             "start": {"dateTime": f"2024-01-{day}T10:00:00Z"},
             "end": {"dateTime": f"2024-01-{day}T11:00:00Z"}}
            for name, day in [("Bob Jones", 15), ("Alice Smith", 16),
                              ("Bob Jones", 17)]
        ]

        lessons, _ = process_events(events, sample_students_data, [])

        assert list(lessons) == ["Bob Jones", "Alice Smith"]
        assert [lesson.start.day for lesson in lessons["Bob Jones"]] == [15, 17]

    def test_empty_events_list_returns_no_lessons(self, sample_students_data):
        """Empty events list should give no lessons."""
        assert process_events([], sample_students_data, []) == ({}, [])

    def test_cancelled_events_excluded(
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

        lessons, skipped = process_events(
            events,
            sample_students_data,
            []
        )

        assert [lesson.start.date() for lesson in lessons["Alice Smith"]] == [
            date(2024, 1, 15)
        ]

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
