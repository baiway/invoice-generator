import os.path
import re
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build


def authenticate_google_calendar():
    """Setup the Google API authentication.
    Expects `credentials.json` in the `data` directory for the initial setup
    and uses `token.json` (also in the `data` directory) for subsequent authentication.

    Returns a Google Calendar service object.
    """
    SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
    creds = None
    if os.path.exists("data/token.json"):
        creds = Credentials.from_authorized_user_file("data/token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "data/credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open("data/token.json", "w") as token:
            token.write(creds.to_json())
    service = build("calendar", "v3", credentials=creds)
    return service


def fetch_calendar_events(service, start_date, end_date):
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


def process_events(events, student_data):
    """Processes a list of calendar events and categorises them based on student names.
    Uses regex to parse the event summary for student names, handling aliases as specified
    in `students.json`. Events that do not match the expected format are skipped.

    Returns a dictionary with the following structure:
        lessons["student"] = [
            (lesson1_start_time, lesson1_end_time),
            (lesson2_start_time, lesson2_end_time),
            ...
        ]
    where start_time and end_time are datetime objects.
    """
    lessons = {}
    for event in events:
        summary = event["summary"]
        student_name = None

        # This regex search is used to determine whether parents
        # have booked a session under their name using my booking page.
        # If they do, the event is always titled "Tutoring (Firstname Lastname)"
        # Sometimes there are trailing spaces in the firstname and lastname fields;
        # these are removed here.
        match = re.search(r"\((.*?)\)", summary)
        if match:
            extracted_name = match.group(1).strip()  # extract and strip spaces
            extracted_name = re.sub(r"\s+", " ", extracted_name)
            for student, info in student_data.items():
                if extracted_name in info["aliases"]:
                    student_name = student
                    break
        elif summary.startswith("Tutoring "):
            student_name = summary.split("Tutoring ")[1].strip()

        if not student_name:
            print(f"Skipping event with unexpected format: '{summary}'")
            continue

        start = event["start"].get("dateTime", event["start"].get("date"))
        end = event["end"].get("dateTime", event["end"].get("date"))

        if student_name not in lessons:
            lessons[student_name] = {"start": [], "end": []}

        lessons[student_name]["start"].append(start)
        lessons[student_name]["end"].append(end)

    return lessons
