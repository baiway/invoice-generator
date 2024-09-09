import pandas as pd
from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build, Resource
from datetime import datetime
from typing import List, Dict, Any, Union

def authenticate() -> Resource:
    """Authenticate using Google's API. Expects `credentials.json` in
    the `data/` directory and uses `token.json` (also in the `data`
    directory) for subsequent authentication. Returns a Google Calendar
    service object.
    """
    credentials_path = Path("data/credentials.json")
    token_path = Path("data/token.json")
    SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

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
    service: Any,
    start_date: datetime,
    end_date: datetime
) -> List[Dict[str, Any]]:
    """Fetch all Google Calendar events between a specified start and
    end date. Requires a Google Calendar service object and date
    range. Returns a list of events.
    """
    print(f"Fetching events from {start_date.strftime("%d %B %Y")} to "
          f"{end_date.strftime("%d %B %Y")}...")
    events_result = (
        service.events()
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
    attendees: List[Any],
    student_data: Dict[str, Dict[str, Union[int, float, str]]]
) -> Union[str, None]:
    """Attempts to match Google Calendar attendees with email address
    in `students.json`.
    """
    for attendee in attendees:
        email = attendee.get("email")
        for student_name, info in student_data.items():
            if email in info["emails"]:
                return student_name
    print("attendees not found in 'students.json': ", attendees)
    return None


def process_events(
    events: List[Dict[str, Any]],
    student_data: Dict[str, Dict[str, Union[int, float, str]]],
    students_to_invoice: List[str]
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
    lessons = []

    for event in events:
        event_title = event["summary"]
        attendees = event.get("attendees", [])
        student_name = None

        # Attempt to extract `student_name`
        if attendees:
            student_name = attendee_match(attendees, student_data)
        elif "PMT" in event_title: # ignore these (invoices handled by PMT)
            continue
        elif event_title.startswith("Tutoring "):
            student_name = event_title.split("Tutoring ")[1].strip()
        else:
            print(f"Skipping event with unexpected format: '{event_title}'")
            continue

        # Skip event if no name match by this point
        if not student_name:
            print(f"Could not extract `student_name` from '{event_title}`. " \
                  "Skipping event.")
            continue

        # Skip event if student is not in students_to_invoice
        if students_to_invoice and student_name not in students_to_invoice:
            continue

        # Handle missing student in `student_data` or KeyError
        try:
            rate = student_data[student_name]["rate"]
            client_type = student_data[student_name]["client_type"]
        except KeyError:
            print(f"KeyError with `student_name`: {student_name}. Likely not " \
                  "added to `students.json`.")
            continue

        # Extract start and end dates
        start = event["start"]["dateTime"]
        end = event["end"]["dateTime"]

        lessons.append([student_name, start, end, rate, client_type])

    df = pd.DataFrame(
        lessons, columns=["student", "start", "end", "rate", "client_type"]
    )

    # Convert start and end columns to datetime for proper handling
    df["start"] = pd.to_datetime(df["start"], utc=True)
    df["end"] = pd.to_datetime(df["end"], utc=True)

    return df
