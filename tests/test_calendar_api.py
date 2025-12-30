"""
Tests for src/calendar_api.py Google Calendar API integration.

This module tests authentication and event fetching with mocked Google API
responses to avoid external dependencies.
"""

import pytest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch, call

from src.calendar_api import authenticate, fetch_events


class TestAuthenticate:
    """Tests for authenticate function with Google OAuth."""

    def test_missing_credentials_file_raises_error(self, tmp_path, monkeypatch):
        """Missing credentials.json should raise FileNotFoundError."""
        nonexistent_creds = tmp_path / "nonexistent" / "credentials.json"
        monkeypatch.setattr(
            "src.calendar_api.CREDENTIALS_FILE",
            str(nonexistent_creds)
        )

        with pytest.raises(FileNotFoundError) as exc_info:
            authenticate()

        assert "not found" in str(exc_info.value)

    def test_existing_valid_token_used_for_auth(self, tmp_path, monkeypatch):
        """Existing valid token should be used without refresh."""
        # Create credentials.json and token.json files
        creds_file = tmp_path / "credentials.json"
        token_file = tmp_path / "token.json"
        creds_file.write_text('{"installed": {}}')
        token_file.write_text('{"token": "valid_token"}')

        monkeypatch.setattr(
            "src.calendar_api.CREDENTIALS_FILE",
            str(creds_file)
        )
        monkeypatch.setattr(
            "src.calendar_api.TOKEN_FILE",
            str(token_file)
        )

        # Mock Credentials
        mock_creds = MagicMock()
        mock_creds.valid = True
        mock_creds.expired = False

        # Mock build to return service
        mock_service = MagicMock()

        with patch("src.calendar_api.Credentials.from_authorized_user_file") as mock_from_file, \
             patch("src.calendar_api.build") as mock_build:
            mock_from_file.return_value = mock_creds
            mock_build.return_value = mock_service

            result = authenticate()

            # Should load existing creds and build service
            mock_from_file.assert_called_once()
            mock_build.assert_called_once_with(
                "calendar", "v3", credentials=mock_creds
            )
            assert result == mock_service

    def test_expired_token_with_refresh_token_triggers_refresh(
        self, tmp_path, monkeypatch
    ):
        """Expired token with refresh_token should trigger refresh."""
        creds_file = tmp_path / "credentials.json"
        token_file = tmp_path / "token.json"
        creds_file.write_text('{"installed": {}}')
        token_file.write_text('{"token": "expired_token"}')

        monkeypatch.setattr(
            "src.calendar_api.CREDENTIALS_FILE",
            str(creds_file)
        )
        monkeypatch.setattr(
            "src.calendar_api.TOKEN_FILE",
            str(token_file)
        )

        # Mock expired credentials with refresh token
        mock_creds = MagicMock()
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = "refresh_token_123"
        mock_creds.to_json.return_value = '{"token": "refreshed_token"}'

        mock_service = MagicMock()

        with patch("src.calendar_api.Credentials.from_authorized_user_file") as mock_from_file, \
             patch("src.calendar_api.Request") as mock_request, \
             patch("src.calendar_api.build") as mock_build:
            mock_from_file.return_value = mock_creds
            mock_build.return_value = mock_service

            result = authenticate()

            # Should refresh the credentials
            mock_creds.refresh.assert_called_once()
            # Should save refreshed token
            assert token_file.read_text() == '{"token": "refreshed_token"}'
            assert result == mock_service

    def test_invalid_token_triggers_new_oauth_flow(
        self, tmp_path, monkeypatch
    ):
        """Invalid token without refresh should trigger new OAuth flow."""
        creds_file = tmp_path / "credentials.json"
        token_file = tmp_path / "token.json"
        creds_file.write_text('{"installed": {}}')
        token_file.write_text('{"token": "invalid_token"}')

        monkeypatch.setattr(
            "src.calendar_api.CREDENTIALS_FILE",
            str(creds_file)
        )
        monkeypatch.setattr(
            "src.calendar_api.TOKEN_FILE",
            str(token_file)
        )

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

        with patch("src.calendar_api.Credentials.from_authorized_user_file") as mock_from_file, \
             patch("src.calendar_api.InstalledAppFlow.from_client_secrets_file") as mock_flow_create, \
             patch("src.calendar_api.build") as mock_build:
            mock_from_file.return_value = mock_creds_invalid
            mock_flow_create.return_value = mock_flow
            mock_build.return_value = mock_service

            result = authenticate()

            # Should create new OAuth flow
            mock_flow_create.assert_called_once()
            mock_flow.run_local_server.assert_called_once_with(port=0)
            # Should save new token
            assert token_file.read_text() == '{"token": "new_token"}'
            assert result == mock_service

    def test_no_token_file_triggers_new_oauth_flow(
        self, tmp_path, monkeypatch
    ):
        """Missing token file should trigger new OAuth flow."""
        creds_file = tmp_path / "credentials.json"
        token_file = tmp_path / "token.json"
        creds_file.write_text('{"installed": {}}')
        # Don't create token_file - it should not exist

        monkeypatch.setattr(
            "src.calendar_api.CREDENTIALS_FILE",
            str(creds_file)
        )
        monkeypatch.setattr(
            "src.calendar_api.TOKEN_FILE",
            str(token_file)
        )

        # Mock new credentials from OAuth flow
        mock_creds = MagicMock()
        mock_creds.to_json.return_value = '{"token": "new_token"}'

        mock_flow = MagicMock()
        mock_flow.run_local_server.return_value = mock_creds

        mock_service = MagicMock()

        with patch("src.calendar_api.InstalledAppFlow.from_client_secrets_file") as mock_flow_create, \
             patch("src.calendar_api.build") as mock_build:
            mock_flow_create.return_value = mock_flow
            mock_build.return_value = mock_service

            result = authenticate()

            # Should create OAuth flow
            mock_flow_create.assert_called_once()
            mock_flow.run_local_server.assert_called_once_with(port=0)
            # Should create and save token
            assert token_file.exists()
            assert token_file.read_text() == '{"token": "new_token"}'
            assert result == mock_service

    def test_returns_google_calendar_service_object(
        self, tmp_path, monkeypatch
    ):
        """Should return Google Calendar service object."""
        creds_file = tmp_path / "credentials.json"
        token_file = tmp_path / "token.json"
        creds_file.write_text('{"installed": {}}')
        token_file.write_text('{"token": "valid_token"}')

        monkeypatch.setattr(
            "src.calendar_api.CREDENTIALS_FILE",
            str(creds_file)
        )
        monkeypatch.setattr(
            "src.calendar_api.TOKEN_FILE",
            str(token_file)
        )

        mock_creds = MagicMock()
        mock_creds.valid = True
        mock_creds.expired = False  # Explicitly set to False

        mock_service = MagicMock()

        with patch("src.calendar_api.Credentials.from_authorized_user_file") as mock_from_file, \
             patch("src.calendar_api.build") as mock_build:
            mock_from_file.return_value = mock_creds
            mock_build.return_value = mock_service

            result = authenticate()

            # Verify build was called with correct arguments
            mock_build.assert_called_once_with(
                "calendar", "v3", credentials=mock_creds
            )
            assert result == mock_service


class TestFetchEvents:
    """Tests for fetch_events function."""

    def test_fetches_events_in_date_range(self):
        """Should fetch events between specified dates."""
        mock_service = MagicMock()
        mock_events = MagicMock()
        mock_list = MagicMock()
        mock_execute = MagicMock()

        # Set up mock chain: service.events().list().execute()
        mock_service.events.return_value = mock_events
        mock_events.list.return_value = mock_list
        mock_list.execute.return_value = {"items": [
            {"summary": "Event 1"},
            {"summary": "Event 2"}
        ]}

        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 31, tzinfo=timezone.utc)

        result = fetch_events(mock_service, start, end)

        assert len(result) == 2
        assert result[0]["summary"] == "Event 1"
        assert result[1]["summary"] == "Event 2"

    def test_date_formatting_iso8601_with_z_suffix(self):
        """Should format dates as ISO 8601 with 'Z' suffix."""
        mock_service = MagicMock()
        mock_events = MagicMock()
        mock_list = MagicMock()

        mock_service.events.return_value = mock_events
        mock_events.list.return_value = mock_list
        mock_list.execute.return_value = {"items": []}

        start = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        end = datetime(2024, 2, 20, 14, 45, 0, tzinfo=timezone.utc)

        fetch_events(mock_service, start, end)

        # Check that list was called with ISO formatted dates + 'Z'
        mock_events.list.assert_called_once()
        call_kwargs = mock_events.list.call_args[1]
        assert call_kwargs["timeMin"] == "2024-01-15T10:30:00+00:00Z"
        assert call_kwargs["timeMax"] == "2024-02-20T14:45:00+00:00Z"

    def test_uses_primary_calendar_id(self):
        """Should use 'primary' as calendar ID."""
        mock_service = MagicMock()
        mock_events = MagicMock()
        mock_list = MagicMock()

        mock_service.events.return_value = mock_events
        mock_events.list.return_value = mock_list
        mock_list.execute.return_value = {"items": []}

        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 31, tzinfo=timezone.utc)

        fetch_events(mock_service, start, end)

        call_kwargs = mock_events.list.call_args[1]
        assert call_kwargs["calendarId"] == "primary"

    def test_requests_single_events_ordered_by_start_time(self):
        """Should request single events ordered by start time."""
        mock_service = MagicMock()
        mock_events = MagicMock()
        mock_list = MagicMock()

        mock_service.events.return_value = mock_events
        mock_events.list.return_value = mock_list
        mock_list.execute.return_value = {"items": []}

        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 31, tzinfo=timezone.utc)

        fetch_events(mock_service, start, end)

        call_kwargs = mock_events.list.call_args[1]
        assert call_kwargs["singleEvents"] is True
        assert call_kwargs["orderBy"] == "startTime"

    def test_returns_items_list(self):
        """Should return the items list from API response."""
        mock_service = MagicMock()
        mock_events = MagicMock()
        mock_list = MagicMock()

        expected_items = [
            {"summary": "Meeting 1", "start": {"dateTime": "2024-01-15T10:00:00Z"}},
            {"summary": "Meeting 2", "start": {"dateTime": "2024-01-16T14:00:00Z"}},
            {"summary": "Meeting 3", "start": {"dateTime": "2024-01-17T09:00:00Z"}}
        ]

        mock_service.events.return_value = mock_events
        mock_events.list.return_value = mock_list
        mock_list.execute.return_value = {"items": expected_items}

        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 31, tzinfo=timezone.utc)

        result = fetch_events(mock_service, start, end)

        assert result == expected_items

    def test_empty_response_returns_empty_list(self):
        """Should return empty list when no events found."""
        mock_service = MagicMock()
        mock_events = MagicMock()
        mock_list = MagicMock()

        mock_service.events.return_value = mock_events
        mock_events.list.return_value = mock_list
        # API returns empty dict or dict without 'items' key
        mock_list.execute.return_value = {}

        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 31, tzinfo=timezone.utc)

        result = fetch_events(mock_service, start, end)

        assert result == []

    def test_logs_date_range_being_fetched(self, caplog):
        """Should log the date range being fetched."""
        import logging

        mock_service = MagicMock()
        mock_events = MagicMock()
        mock_list = MagicMock()

        mock_service.events.return_value = mock_events
        mock_events.list.return_value = mock_list
        mock_list.execute.return_value = {"items": []}

        start = datetime(2024, 1, 15, tzinfo=timezone.utc)
        end = datetime(2024, 2, 20, tzinfo=timezone.utc)

        with caplog.at_level(logging.INFO):
            fetch_events(mock_service, start, end)

        assert "Fetching events from" in caplog.text
        assert "15 January 2024" in caplog.text
        assert "20 February 2024" in caplog.text
