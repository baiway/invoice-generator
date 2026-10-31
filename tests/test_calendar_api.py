"""
Tests for src/invoice_generator/calendar_api.py Google Calendar API integration.

This module tests event fetching with mocked Google API responses to avoid
external dependencies.
"""

from datetime import datetime, UTC
from unittest.mock import MagicMock, patch

from invoice_generator.calendar_api import calendar_service, fetch_events


class TestCalendarService:
    """Tests for calendar_service function."""

    def test_builds_the_calendar_api_with_the_credentials(self):
        """The service should be Calendar v3, signed in with `creds`."""
        creds = MagicMock()
        with patch("invoice_generator.calendar_api.build") as mock_build:
            assert calendar_service(creds) is mock_build.return_value
        mock_build.assert_called_once_with("calendar", "v3", credentials=creds)


def make_service(*pages):
    """A mock calendar service whose `events().list().execute()` returns
    each of `pages` in turn."""
    service = MagicMock()
    service.events.return_value.list.return_value.execute.side_effect = pages
    return service


def list_calls(service):
    """The keyword arguments of each `events().list()` call."""
    return [c.kwargs for c in service.events.return_value.list.call_args_list]


class TestFetchEvents:
    """Tests for fetch_events function."""

    START = datetime(2024, 1, 1, tzinfo=UTC)
    END = datetime(2024, 1, 31, tzinfo=UTC)

    def test_returns_items_list(self):
        """Should return the items list from API response."""
        items = [{"summary": "Event 1"}, {"summary": "Event 2"}]
        service = make_service({"items": items})

        assert fetch_events(service, self.START, self.END) == items

    def test_empty_response_returns_empty_list(self):
        """A response with no 'items' key should give an empty list."""
        service = make_service({})

        assert fetch_events(service, self.START, self.END) == []

    def test_follows_page_tokens(self):
        """Events beyond the first page should be fetched too."""
        service = make_service(
            {"items": [{"summary": "Event 1"}], "nextPageToken": "page-2"},
            {"items": [{"summary": "Event 2"}], "nextPageToken": "page-3"},
            {"items": [{"summary": "Event 3"}]},
        )

        result = fetch_events(service, self.START, self.END)

        assert [e["summary"] for e in result] == ["Event 1", "Event 2", "Event 3"]
        assert [c["pageToken"] for c in list_calls(service)] == [
            None, "page-2", "page-3"
        ]

    def test_every_page_uses_the_same_query(self):
        """Only the page token should change between requests."""
        service = make_service({"nextPageToken": "page-2"}, {})

        fetch_events(service, self.START, self.END)

        first, second = list_calls(service)
        del first["pageToken"], second["pageToken"]
        assert first == second

    def test_dates_are_sent_with_a_utc_offset(self):
        """The API needs RFC 3339 timestamps, which carry an offset."""
        service = make_service({})
        start = datetime(2024, 1, 15, 10, 30, tzinfo=UTC)
        end = datetime(2024, 2, 20, 14, 45, tzinfo=UTC)

        fetch_events(service, start, end)

        (kwargs,) = list_calls(service)
        assert datetime.fromisoformat(kwargs["timeMin"]) == start
        assert datetime.fromisoformat(kwargs["timeMax"]) == end

    def test_naive_dates_are_local_time(self):
        """The CLI passes naive dates, which mean local midnight."""
        service = make_service({})
        start = datetime(2024, 7, 1)

        fetch_events(service, start, datetime(2024, 7, 31))

        (kwargs,) = list_calls(service)
        sent = datetime.fromisoformat(kwargs["timeMin"])
        assert sent.utcoffset() is not None
        assert sent == start.astimezone()

    def test_query_parameters(self):
        """Should ask for single, non-deleted events from the primary
        calendar, ordered by start time."""
        service = make_service({})

        fetch_events(service, self.START, self.END)

        (kwargs,) = list_calls(service)
        assert kwargs["calendarId"] == "primary"
        assert kwargs["singleEvents"] is True
        assert kwargs["orderBy"] == "startTime"
        # Cancellation tombstones are excluded at source
        assert kwargs["showDeleted"] is False

    def test_logs_date_range_being_fetched(self, caplog):
        """Should log the date range being fetched."""
        import logging

        service = make_service({})
        start = datetime(2024, 1, 15, tzinfo=UTC)
        end = datetime(2024, 2, 20, tzinfo=UTC)

        with caplog.at_level(logging.INFO):
            fetch_events(service, start, end)

        assert "Fetching events from" in caplog.text
        assert "15 January 2024" in caplog.text
        assert "20 February 2024" in caplog.text
