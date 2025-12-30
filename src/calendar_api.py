"""
Google Calendar API integration.

This module handles authentication and fetching events from Google Calendar.
"""

from pathlib import Path
from typing import Any
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build, Resource
from datetime import datetime

from src.constants import (
    CREDENTIALS_FILE,
    TOKEN_FILE,
    GOOGLE_CALENDAR_SCOPES,
)
from src.logging_config import get_logger

logger = get_logger(__name__)


def authenticate() -> Resource:
    """Authenticate using Google's API.

    Expects `credentials.json` in the `data/` directory and uses
    `token.json` (also in the `data` directory) for subsequent
    authentication.

    Returns:
        Google Calendar service object

    Raises:
        FileNotFoundError: If credentials.json is not found
    """
    creds_path = Path(CREDENTIALS_FILE)
    token_path = Path(TOKEN_FILE)
    SCOPES = GOOGLE_CALENDAR_SCOPES

    if not creds_path.is_file():
        raise FileNotFoundError(f"`{creds_path.resolve()}` not found")

    # Load existing credentials if available
    creds = None
    if token_path.is_file():
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    # Refresh or obtain new credentials if needed
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.write_text(creds.to_json())
    elif not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
        creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json())

    return build("calendar", "v3", credentials=creds)


def fetch_events(
    service: Resource,
    start_date: datetime,
    end_date: datetime
) -> list[dict[str, Any]]:
    """Fetch all Google Calendar events between a specified date range.

    Args:
        service: Google Calendar service object from authenticate()
        start_date: Start of date range
        end_date: End of date range

    Returns:
        List of calendar events as dictionaries
    """
    logger.info(f"Fetching events from {start_date.strftime('%d %B %Y')} to "
                f"{end_date.strftime('%d %B %Y')}")
    events_result = (
        service.events()  # type: ignore[attr-defined]
        .list(
            calendarId="primary",
            timeMin=start_date.isoformat() + "Z",
            timeMax=end_date.isoformat() + "Z",
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    return events_result.get("items", [])
