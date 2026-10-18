"""
Google Calendar API integration.

This module handles authentication and fetching events from Google Calendar.
"""

from pathlib import Path
from typing import Any, cast
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build, Resource
from datetime import datetime

from invoice_generator.constants import GOOGLE_CALENDAR_SCOPES
from invoice_generator.logging_config import get_logger

logger = get_logger(__name__)


def authenticate(credentials_path: Path, token_path: Path) -> Resource:
    """Authenticate using Google's API.

    Signs in through the browser the first time, then caches the result
    in `token_path` for subsequent runs.

    Args:
        credentials_path: Path to the OAuth client's `credentials.json`
        token_path: Path to the cached `token.json`, created if missing

    Returns:
        Google Calendar service object

    Raises:
        FileNotFoundError: If credentials.json is not found
    """
    if not credentials_path.is_file():
        raise FileNotFoundError(f"`{credentials_path.resolve()}` not found")

    # Load existing credentials if available
    creds = None
    if token_path.is_file():
        creds = Credentials.from_authorized_user_file(
            token_path, GOOGLE_CALENDAR_SCOPES
        )

    # Refresh or obtain new credentials if needed
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.write_text(creds.to_json())
    elif not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(
            credentials_path, GOOGLE_CALENDAR_SCOPES
        )
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
    # googleapiclient builds the per-API methods (`events()` and friends)
    # onto `Resource` at runtime from the discovery document, so no type
    # checker can resolve them statically
    events_result = (
        cast(Any, service)
        .events()
        .list(
            calendarId="primary",
            timeMin=start_date.isoformat() + "Z",
            timeMax=end_date.isoformat() + "Z",
            singleEvents=True,
            orderBy="startTime",
            showDeleted=False,
        )
        .execute()
    )
    events: list[dict[str, Any]] = events_result.get("items", [])
    return events
