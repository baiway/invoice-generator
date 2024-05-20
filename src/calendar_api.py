from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build


def authenticate_google_calendar(
    credentials_path="data/credentials.json", token_path="data/token.json"
):
    """Setup the Google API authentication.
    Expects `credentials.json` in the `data` directory for the initial setup
    and uses `token.json` (also in the `data` directory) for subsequent authentication.

    Returns a Google Calendar service object.
    """
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


def fetch_events(service, start_date, end_date):
    """Fetch all Google Calendar events between a specified start and end date.
    Requires a Google Calendar service object and date range.

    Returns a list of events.
    """
    print("Fetching events...")
    events_result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=start_date.isoformat(),
            timeMax=end_date.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    return events_result.get("items", [])


def attendee_match(attendees, student_data):
    for attendee in attendees:
        email = attendee.get("email")
        for student_name, info in student_data.items():
            if email in info["emails"]:
                return student_name
    print("attendees not found in 'students.json': ", attendees)
    return None


def process_events(events, student_data):
    """Matches Google Calendar events to students listed in `students.json` based on
    attendee email addresses. If no match is found, the following checks are performed:
    - If no email match but the event name contains "PMT", the event is ignored 
      (payments handled separately)
    - If no email match but event still starts with "Tutoring [student name]", 
      it is assumed that this client is only seen in-person, so the student name can
      be extracted from the event title.
    If a match still isn't found, then the event probably doesn't correspond to a 
    tutoring session (e.g. it could be a call with a parent), but a warning is still 
    printed to the screen in case, for example, you forgot to add a new student's 
    details to `students.json`.

    Returns a dictionary with the following structure:
        lessons["student"] = [
            (lesson1_start_time, lesson1_end_time),
            (lesson2_start_time, lesson2_end_time),
            ...
        ]
    where start_time and end_time are datetime strings in ISO 8601 format. For example,
    2023-11-05T11:15:00Z corresponds to the 11:15am ("Zulu" time, aka UTC) on 5th
    November 2023."""
    lessons = {}
    for event in events:
        event_title = event["summary"]
        attendees = event.get("attendees", [])
        student_name = None

        if attendees:
            student_name = attendee_match(attendees, student_data)
        elif "PMT" in event_title:
            # print(f"PMT event: {event_title}")
            continue
        elif event_title.startswith("Tutoring "):
            student_name = event_title.split("Tutoring ")[1].strip()
        else:
            print(f"Skipping event with unexpected format: '{event_title}'")
            continue

        start = event["start"].get("dateTime", event["start"].get("date"))
        end = event["end"].get("dateTime", event["end"].get("date"))

        if student_name not in lessons:
            try:
                rate = student_data[student_name]["rate"]
                client_type = student_data[student_name]["client_type"]
                lessons[student_name] = {
                    "start": [], 
                    "end": [], 
                    "rate": rate,
                    "client_type": client_type
                }
            except KeyError:
                print(f"KeyError with student_name: {student_name}. Likely not " \
                      "added to 'students.json'."
                )

        lessons[student_name]["start"].append(start)
        lessons[student_name]["end"].append(end)

    return lessons
