import json
import argparse
from datetime import datetime
from pathlib import Path
from src.api import authenticate, fetch_events, process_events
from src.utils import get_last_full_month
from src.outputs import write_invoices, print_inactive_students

def parse_args() -> argparse.Namespace:
    """Parses command line arguments"""

    parser = argparse.ArgumentParser(
        description=(
            "Generates PDF invoices by cross-referencing Google Calendar "
            "events with the details in `students.json`. By default, the "
            "script generates invoices for all students for the last full "
            "month. To change this, use the `--only`, `--from` and `--to` "
            "flags."
        ),
        formatter_class=argparse.MetavarTypeHelpFormatter
    )
    parser.add_argument(
        "--only",
        nargs="+",
        default=[],
        metavar="student",
        help=(
            "Case-sensitive list of student names for which invoices will be "
            "generated. Must match the names in `students.json`. If not "
            "specified, invoices will be generated for all students seen over "
            "the invoice period."
        )
    )
    parser.add_argument(
        "--from",
        dest="start",
        type=str,
        help=(
            "Start of the invoice period in YYYY-MM-DD format. If not "
            "specified, defaults to the start of the last full month. "
            "For example, if the script is run on 2024-09-03, the "
            "start of the invoice period will default to 2024-08-01. If "
            "specified without `--to`, the end of the invoice period will "
            "default to today's date."
        )
    )
    parser.add_argument(
        "--to",
        dest="end",
        type=str,
        help=(
            "End of the invoice period in YYYY-MM-DD format (e.g. "
            "2024-09-30). Cannot be specified without `--from` (raises a "
            "ValueError). If neither are specified, defaults to the end of "
            "the last full month. For example, if the script is run on "
            "2024-09-03, the end of the invoice period will default to "
            "2024-08-31."
        )
    )

    return parser.parse_args()

def validate_students(student_list: list[str]) -> list[str]:
    """Validates student names supplied via the CLI using the `--only`
    flag. If `student_list` is empty (i.e. `--only` not used), simply
    returns `student_list` as invoices will be generated for all
    students seen in the invoice period so no further argument
    validation is needed. Otherwise, verifies that all names in
    `student_list` exist in `students.json`. If any names do not exist,
    a ValueError is raised with the unrecognised names.
    """
    if student_list == []:
        return student_list

    with open("data/students.json", "r") as f:
        student_data = json.load(f)

    student_keys = {name for name in student_data.keys()}
    unrecognised_names = set(student_list) - student_keys

    if unrecognised_names:
        raise ValueError(
            "The following names passed using the `--only` option are not in "
            f"`students.json`: {', '.join(unrecognised_names)}"
        )
    else:
        return student_list


def validate_invoice_period(start: str, end: str) -> tuple[datetime, datetime]:
    """Validates the invoice period supplied via the CLI and return the
    specified dates as datetime objects. If `--to` is specified without
    `--from`, raises a ValueError. If only `--from` is provided, `--to`
    defaults to today's date. If both are empty, the function uses the
    last full month as the date range.
    """
    if end and not start:
        raise ValueError("`--to` cannot be specified without `--from.`")

    if start and not end:
        end = datetime.today().strftime("%Y-%m-%d")

    if not start and not end:
        start, end = get_last_full_month()

    try:
        start_date = datetime.strptime(start, "%Y-%m-%d")
        end_date = datetime.strptime(end, "%Y-%m-%d")
        end_date = end_date.replace(hour=23, minute=59, second=59)
    except ValueError:
        raise ValueError("Invalid date format. Must be in YYYY-MM-DD format.")

    if start_date > end_date:
        raise ValueError("`--from` date cannot be later than the `--to` date.")

    return start_date, end_date


def main():
    # Parse and validate command line arguments
    args = parse_args()
    students_to_invoice = validate_students(args.only)
    start_date, end_date = validate_invoice_period(args.start, args.end)

    # Load `students.json`, `bank_details.json` and `contact_details.json`
    with open("data/students.json", "r") as f:
        student_data = json.load(f)
    with open("data/bank_details.json", "r") as f:
        bank_details = json.load(f)
    with open("data/contact_details.json", "r") as f:
        contact_details = json.load(f)

    # Authenticate Google Calendar
    service = authenticate()

    # Fetch all Google Calendar events over the invoice period
    events = fetch_events(service, start_date, end_date)

    # Matches Google Calendar events to students listed in `students.json`,
    # producing a `pandas.DataFrame` with the following structure:
    #
    # student |    start (datetime)    |     end (datetime)     | rate | client_type
    # ------------------------------------------------------------------------------
    #  Alice  | 2024-09-08 11:00:00+00 | 2024-09-08 12:00:00+00 |  50  |   private
    #  Bob    | 2024-09-08 14:00:00+00 | 2024-09-08 15:00:00+00 |  40  |   agency
    lessons = process_events(events, student_data, students_to_invoice,
                             contact_details)

    # If `--only` is not specified (user is generating invoices for all
    # students seen in the invoice period), print a list of inactive students
    # to prompt the user to contact them.
    if not args.only:
        print_inactive_students(lessons, student_data)

    # Write invoices
    output_dir = Path("./invoices")
    if not output_dir.exists():
        output_dir.mkdir()
    write_invoices(output_dir, lessons, start_date, end_date, bank_details, contact_details)
    print(f"Invoices saved here: {output_dir.resolve()}")

if __name__ == "__main__":
    main()
