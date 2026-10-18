"""
Tests for src/invoice_generator/calendar_api.py Google Calendar API integration.

This module tests authentication and event fetching with mocked Google API
responses to avoid external dependencies.
"""

import pytest
from datetime import datetime, UTC
from unittest.mock import MagicMock, patch

from invoice_generator.calendar_api import authenticate, fetch_events


class TestAuthenticate:
    """Tests for authenticate function with Google OAuth."""

    def test_missing_credentials_file_raises_error(self, tmp_path):
        """Missing credentials.json should raise FileNotFoundError."""
        nonexistent_creds = tmp_path / "nonexistent" / "credentials.json"

        with pytest.raises(FileNotFoundError) as exc_info:
            authenticate(nonexistent_creds, tmp_path / "token.json")

        assert "not found" in str(exc_info.value)

    def test_existing_valid_token_used_for_auth(self, tmp_path):
        """Existing valid token should be used without refresh."""
        # Create credentials.json and token.json files
        creds_file = tmp_path / "credentials.json"
        token_file = tmp_path / "token.json"
        creds_file.write_text('{"installed": {}}')
        token_file.write_text('{"token": "valid_token"}')


        # Mock Credentials
        mock_creds = MagicMock()
        mock_creds.valid = True
        mock_creds.expired = False

        # Mock build to return service
        mock_service = MagicMock()

        with patch("invoice_generator.calendar_api.Credentials.from_authorized_user_file") as mock_from_file, \
             patch("invoice_generator.calendar_api.build") as mock_build:
            mock_from_file.return_value = mock_creds
            mock_build.return_value = mock_service

            result = authenticate(creds_file, token_file)

            # Should load existing creds and build service
            mock_from_file.assert_called_once()
            mock_build.assert_called_once_with(
                "calendar", "v3", credentials=mock_creds
            )
            assert result == mock_service

    def test_expired_token_with_refresh_token_triggers_refresh(
        self, tmp_path
    ):
        """Expired token with refresh_token should trigger refresh."""
        creds_file = tmp_path / "credentials.json"
        token_file = tmp_path / "token.json"
        creds_file.write_text('{"installed": {}}')
        token_file.write_text('{"token": "expired_token"}')


        # Mock expired credentials with refresh token
        mock_creds = MagicMock()
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = "refresh_token_123"
        mock_creds.to_json.return_value = '{"token": "refreshed_token"}'

        mock_service = MagicMock()

        with patch("invoice_generator.calendar_api.Credentials.from_authorized_user_file") as mock_from_file, \
             patch("invoice_generator.calendar_api.Request"), \
             patch("invoice_generator.calendar_api.build") as mock_build:
            mock_from_file.return_value = mock_creds
            mock_build.return_value = mock_service

            result = authenticate(creds_file, token_file)

            # Should refresh the credentials
            mock_creds.refresh.assert_called_once()
            # Should save refreshed token
            assert token_file.read_text() == '{"token": "refreshed_token"}'
            assert result == mock_service

    def test_invalid_token_triggers_new_oauth_flow(
        self, tmp_path
    ):
        """Invalid token without refresh should trigger new OAuth flow."""
        creds_file = tmp_path / "credentials.json"
        token_file = tmp_path / "token.json"
        creds_file.write_text('{"installed": {}}')
        token_file.write_text('{"token": "invalid_token"}')


        # Mock invalid credentials (no refresh token)
        mock_creds_invalid = MagicMock()
        mock_creds_invalid.valid = False
        mock_creds_invalid.expired = True
        mock_creds_invalid.refresh_token = None  # No refresh token

        # Mock new credentials from OAuth flow
        mock_creds_new = MagicMock()
        mock_creds_new.to_json.return_value = '{"token": "new_token"}'

        mock_flow = MagicMock()
        mock_flow.run_local_server.return_value = mock_creds_new

        mock_service = MagicMock()

        with patch("invoice_generator.calendar_api.Credentials.from_authorized_user_file") as mock_from_file, \
             patch("invoice_generator.calendar_api.InstalledAppFlow.from_client_secrets_file") as mock_flow_create, \
             patch("invoice_generator.calendar_api.build") as mock_build:
            mock_from_file.return_value = mock_creds_invalid
            mock_flow_create.return_value = mock_flow
            mock_build.return_value = mock_service

            result = authenticate(creds_file, token_file)

            # Should create new OAuth flow
            mock_flow_create.assert_called_once()
            mock_flow.run_local_server.assert_called_once_with(port=0)
            # Should save new token
            assert token_file.read_text() == '{"token": "new_token"}'
            assert result == mock_service

    def test_no_token_file_triggers_new_oauth_flow(
        self, tmp_path
    ):
        """Missing token file should trigger new OAuth flow."""
        creds_file = tmp_path / "credentials.json"
        token_file = tmp_path / "token.json"
        creds_file.write_text('{"installed": {}}')
        # Don't create token_file - it should not exist


        # Mock new credentials from OAuth flow
        mock_creds = MagicMock()
        mock_creds.to_json.return_value = '{"token": "new_token"}'

        mock_flow = MagicMock()
        mock_flow.run_local_server.return_value = mock_creds

        mock_service = MagicMock()

        with patch("invoice_generator.calendar_api.InstalledAppFlow.from_client_secrets_file") as mock_flow_create, \
             patch("invoice_generator.calendar_api.build") as mock_build:
            mock_flow_create.return_value = mock_flow
            mock_build.return_value = mock_service

            result = authenticate(creds_file, token_file)

            # Should create OAuth flow
            mock_flow_create.assert_called_once()
            mock_flow.run_local_server.assert_called_once_with(port=0)
            # Should create and save token
            assert token_file.exists()
            assert token_file.read_text() == '{"token": "new_token"}'
            assert result == mock_service

    def test_returns_google_calendar_service_object(
        self, tmp_path
    ):
        """Should return Google Calendar service object."""
        creds_file = tmp_path / "credentials.json"
        token_file = tmp_path / "token.json"
        creds_file.write_text('{"installed": {}}')
        token_file.write_text('{"token": "valid_token"}')


        mock_creds = MagicMock()
        mock_creds.valid = True
        mock_creds.expired = False  # Explicitly set to False

        mock_service = MagicMock()

        with patch("invoice_generator.calendar_api.Credentials.from_authorized_user_file") as mock_from_file, \
             patch("invoice_generator.calendar_api.build") as mock_build:
            mock_from_file.return_value = mock_creds
            mock_build.return_value = mock_service

            result = authenticate(creds_file, token_file)

            # Verify build was called with correct arguments
            mock_build.assert_called_once_with(
                "calendar", "v3", credentials=mock_creds
            )
            assert result == mock_service


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
