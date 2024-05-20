import json
from pathlib import Path
from src.calendar_api import authenticate_google_calendar, fetch_events, process_events
from src.utils import get_user_choice, get_last_full_month, get_date_input
from src.format_outputs import write_invoices, print_inactive_students


def generate_invoices():
    # Load `students.json`
    student_data_path = Path("data/students.json")
    try:
        with open(student_data_path, "r") as f:
            student_data = json.load(f)
    except FileNotFoundError:
        print(f"Error: 'students.json' file not found in {student_data_path}.")
        return
    except json.JSONDecodeError:
        print("Error: 'students.json' file is not a valid JSON.")
        return

    # Authenticate Google Calendar
    service = authenticate_google_calendar()

    # Determine date range over which to invoice
    use_custom_range = get_user_choice()
    if use_custom_range:
        start_date = get_date_input("start")
        end_date = get_date_input("end")
    else:
        start_date, end_date = get_last_full_month()

    # Adjust end_date to include the entire day
    end_date = end_date.replace(hour=23, minute=59, second=59)

    # Fetch and process events
    events = fetch_events(service, start_date, end_date)
    lessons = process_events(events, student_data)

    # Print list of students not seen this month
    print_inactive_students(lessons, student_data)

    # Write invoices
    output_dir = Path("./invoices")
    if not output_dir.exists():
        output_dir.mkdir()
    write_invoices(output_dir, lessons, start_date, end_date)
    print(f"Invoices saved here: {output_dir.resolve()}")

if __name__ == "__main__":
    generate_invoices()
