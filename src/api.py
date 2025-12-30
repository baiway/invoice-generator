import pandas as pd
from pathlib import Path
from typing import Any, Optional
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
from src.schema import classify_event, match_attendee_email
from src.logging_config import get_logger

logger = get_logger(__name__)


def authenticate() -> Resource:
    """Authenticate using Google's API. Expects `credentials.json` in
    the `data/` directory and uses `token.json` (also in the `data`
    directory) for subsequent authentication. Returns a Google Calendar
    service object.
    """
    credentials_path = Path(CREDENTIALS_FILE)
    token_path = Path(TOKEN_FILE)
    SCOPES = GOOGLE_CALENDAR_SCOPES

    if not Path(credentials_path).is_file():
        raise FileNotFoundError(f"credentials.json not found at `{credentials_path}`")

    creds = None
    if Path(token_path).is_file():
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w") as token:
            token.write(creds.to_json())
    service = build("calendar", "v3", credentials=creds)
    return service


def fetch_events(
    service: Resource,
    start_date: datetime,
    end_date: datetime
) -> list[dict[str, Any]]:  # FIX: was list[dict[str, str]], now correct
    """Fetch all Google Calendar events between a specified start and
    end date. Requires a Google Calendar service object and date
    range. Returns a list of events.
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


def attendee_match(
    attendees: list[dict[str, Any]],
    student_data: dict[str, Any],
) -> str:
    """Attempts to match Google Calendar attendees with email address
    in `students.json`.
    """
    student_name = match_attendee_email(attendees, student_data)

    if student_name:
        return student_name

    logger.warning(f"Attendees not found in students.json: {attendees}")
    return ""


def process_events(
    events: list[dict[str, Any]],
    student_data: dict[str, Any],
    students_to_invoice: list[str],
    contact_details: dict[str, str]
) -> pd.DataFrame:
    """Matches Google Calendar events to students listed in
    `students.json` based on attendee email addresses and stores the
    lesson information in a Pandas DataFrame.

    Returns a DataFrame with the following structure:
        student |    start (datetime)    |     end (datetime)     | rate | client_type
        ------------------------------------------------------------------------------
         Alice  | 2024-09-08 11:00:00+00 | 2024-09-08 12:00:00+00 |  50  |   private
         Bob    | 2024-09-08 14:00:00+00 | 2024-09-08 15:00:00+00 |  40  |   agency
        ...

    If no match is found using attendee email addresses, the following
    checks are performed:
       - If event name contains "PMT", the event is ignored (payments
         handled separately by Physics and Maths Tutor)
       - If event name conforms to "Tutoring [student name]", it is
         assumed that this client is only seen in-person, so the
         student name can be extracted from the event title.
       - If an event relates to a student not in `students_to_invoice`,
         it is skipped.
    If a match still isn't found, then the event probably doesn't
    correspond to a tutoring session (e.g. it could be a call with a
    parent), but a warning is still printed to the screen in case,
    for example, you may have just forgotten to add a new student's
    details to `students.json`.
    """
    my_email = contact_details["email"]  # Note: extracted but not currently used
    lessons: list[list[Any]] = []

    for event in events:
        event_title = event.get("summary", "")
        if not event_title:
            logger.debug("Skipping event with no title")
            continue

        attendees = event.get("attendees", [])
        student_name: Optional[str] = None

        # Use schema module for event classification
        event_type, extracted_name = classify_event(event_title, attendees)

        if event_type == "email":
            student_name = attendee_match(attendees, student_data)
        elif event_type == "pmt":
            logger.debug(f"Skipping PMT event: {event_title}")
            continue
        elif event_type in ("blue_education", "in_person"):
            student_name = extracted_name
        else:
            logger.warning(f"Skipping event with unexpected format: '{event_title}'")
            continue

        # Validate student name was extracted
        if not student_name:
            logger.warning(
                f"Could not extract student_name from '{event_title}'. Skipping event."
            )
            continue

        # Filter by students_to_invoice if specified
        if students_to_invoice and student_name not in students_to_invoice:
            continue

        # Extract student details from student_data
        try:
            rate = student_data[student_name]["rate"]
            client_type = student_data[student_name]["client_type"]
        except KeyError:
            logger.error(
                f"Student '{student_name}' not found in students.json. "
                f"Please add their details before generating invoices."
            )
            continue

        # Extract event times
        start = event["start"]["dateTime"]
        end = event["end"]["dateTime"]

        lessons.append([student_name, start, end, rate, client_type])

    df = pd.DataFrame(
        lessons, columns=["student", "start", "end", "rate", "client_type"]
    )

    # Convert start and end columns to datetime for proper handling
    df["start"] = pd.to_datetime(df["start"], utc=True)
    df["end"] = pd.to_datetime(df["end"], utc=True)

    logger.info(f"Processed {len(df)} lessons from {len(events)} events")
    return df
