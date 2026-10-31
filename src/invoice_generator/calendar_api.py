"""
Google Calendar API integration.

This module fetches events from Google Calendar. Signing in is handled by
`google_auth`.
"""

from typing import Any, cast
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build, Resource
from datetime import datetime

from invoice_generator.logging_config import get_logger

logger = get_logger(__name__)


def calendar_service(creds: Credentials) -> Resource:
    """The Google Calendar API, signed in with `creds` from
    `google_auth.authenticate`."""
    return build("calendar", "v3", credentials=creds)


def fetch_events(
    service: Resource,
    start_date: datetime,
    end_date: datetime
) -> list[dict[str, Any]]:
    """Fetch all Google Calendar events between a specified date range.

    Args:
        service: Google Calendar API, from `calendar_service`
        start_date: Start of date range. Naive datetimes are taken to be
            in the local timezone.
        end_date: End of date range, likewise

    Returns:
        List of calendar events as dictionaries, ordered by start time
    """
    logger.info(f"Fetching events from {start_date.strftime('%d %B %Y')} to "
                f"{end_date.strftime('%d %B %Y')}")
    # googleapiclient builds the per-API methods (`events()` and friends)
    # onto `Resource` at runtime from the discovery document, so no type
    # checker can resolve them statically
    events_api = cast(Any, service).events()

    # Results come back a page (at most 250 events) at a time
    events: list[dict[str, Any]] = []
    page_token = None
    while True:
        response = events_api.list(
            calendarId="primary",
            # `astimezone()` gives naive datetimes the local UTC offset,
            # which the API requires
            timeMin=start_date.astimezone().isoformat(),
            timeMax=end_date.astimezone().isoformat(),
            singleEvents=True,
            orderBy="startTime",
            showDeleted=False,
            pageToken=page_token,
        ).execute()
        events.extend(response.get("items", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            return events
