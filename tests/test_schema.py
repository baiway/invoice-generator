"""
Tests for src/schema.py event classification logic.
"""

import pytest
from src.schema import (
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
        event_type, name = classify_event("BAC John Smith Physics", attendees)
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
        assert extract_blue_education_name("BAC John Smith") == "John Smith"

    def test_with_additional_info(self):
        """Additional info should be ignored."""
        assert extract_blue_education_name("BAC Alice Jones - Maths") == "Alice Jones"

    def test_insufficient_parts(self):
        """Malformed BAC events should return empty string."""
        assert extract_blue_education_name("BAC John") == ""
        assert extract_blue_education_name("BAC") == ""


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
