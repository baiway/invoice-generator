import json
import os
from src.calendar_api import authenticate_google_calendar, fetch_calendar_events, process_events
from src.utils import get_user_choice, get_last_full_month, get_date_input
from src.format_outputs import write_invoices

def main():
    try:
        with open("data/students.json", "r") as f:
            student_data = json.load(f)
    except FileNotFoundError:
        print("Error: 'students.json' file not found in 'data' directory.")
        return
    except json.JSONDecodeError:
        print("Error: 'students.json' file is not a valid JSON.")
        return

    try:
        service = authenticate_google_calendar()
    except Exception as e:
        print(f"Error while authenticating Google Calendar: {e}")
        return

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
    try:
        events = fetch_calendar_events(service, start_date, end_date)
        lessons = process_events(events, student_data)
    except Exception as e:
        print(f"Error while fetching or processing events: {e}")
        return

    output_folder = "invoices"
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    try:
        write_invoices(lessons, student_data, start_date, end_date)
    except Exception as e:
        print(f"Error while writing invoices: {e}")
    
    print("Done! Invoices saved in `invoices` folder.")

if __name__ == "__main__":
    main()
