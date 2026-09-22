"""
Command line interface.

This module parses and validates command line arguments, then drives the
fetch -> process -> render pipeline. Installed as the `generate-invoices`
command; see `[project.scripts]` in `pyproject.toml`.
"""

import json
import argparse
from datetime import datetime
from pathlib import Path
from rich.console import Console

from invoice_generator.calendar_api import authenticate, fetch_events
from invoice_generator.event_processing import process_events
from invoice_generator.utils import get_last_full_month
from invoice_generator.invoice_generator import write_invoices, print_inactive_students
from invoice_generator.data_loader import load_student_data, load_bank_details, load_contact_details
from invoice_generator.logging_config import setup_logging, get_logger
from invoice_generator.constants import (
    BANK_DETAILS_FILENAME,
    CONTACT_DETAILS_FILENAME,
    CREDENTIALS_FILENAME,
    DATA_DIR,
    OUTPUT_DIR,
    STUDENTS_FILENAME,
    TOKEN_FILENAME,
)

logger = get_logger(__name__)
console = Console()

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parses command line arguments.

    Args:
        argv: Argument list to parse. Defaults to `sys.argv[1:]`.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Generates PDF invoices by cross-referencing Google Calendar "
            "events with the details in `students.json`. By default, the "
            "script generates invoices for all students for the last full "
            "month. To change this, use the `--only`, `--from` and `--to` "
            "flags."
        )
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
        "--data-dir",
        default=DATA_DIR,
        metavar="path",
        help=(
            "Directory holding `students.json`, `bank_details.json`, "
            "`contact_details.json` and the Google credentials. Relative "
            f"paths are resolved against the current directory (default: "
            f"`{DATA_DIR}`)."
        )
    )
    parser.add_argument(
        "--output-dir",
        default=OUTPUT_DIR,
        metavar="path",
        help=(
            "Directory to write the PDF invoices to, created if it does not "
            "exist. Relative paths are resolved against the current "
            f"directory (default: `{OUTPUT_DIR}`)."
        )
    )
    parser.add_argument(
        "--from",
        dest="start",
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
        help=(
            "End of the invoice period in YYYY-MM-DD format (e.g. "
            "2024-09-30). Cannot be specified without `--from` (raises a "
            "ValueError). If neither are specified, defaults to the end of "
            "the last full month. For example, if the script is run on "
            "2024-09-03, the end of the invoice period will default to "
            "2024-08-31."
        )
    )

    return parser.parse_args(argv)

def validate_students(
    student_list: list[str],
    students_file: str | Path | None = None,
) -> list[str]:
    """Validates student names supplied via the CLI using the `--only`
    flag. If `student_list` is empty (i.e. `--only` not used), simply
    returns `student_list` as invoices will be generated for all
    students seen in the invoice period so no further argument
    validation is needed. Otherwise, verifies that all names in
    `student_list` exist in `students.json`. If any names do not exist,
    a ValueError is raised with the unrecognised names.

    Args:
        student_list: Names passed to `--only`.
        students_file: Path to `students.json`. Defaults to the file in
            `DATA_DIR`.
    """
    if student_list == []:
        return student_list

    if students_file is None:
        students_file = Path(DATA_DIR) / STUDENTS_FILENAME

    with open(students_file) as f:
        student_data = json.load(f)

    student_keys = set(student_data)
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
        raise ValueError(
            "Invalid date format. Must be in YYYY-MM-DD format."
        ) from None

    if start_date > end_date:
        raise ValueError("`--from` date cannot be later than the `--to` date.")

    return start_date, end_date


def main(argv: list[str] | None = None) -> None:
    # Set up logging first - detailed logs written to file
    log_file = setup_logging()

    # Parse and validate command line arguments
    args = parse_args(argv)
    data_dir = Path(args.data_dir)
    students_to_invoice = validate_students(
        args.only, data_dir / STUDENTS_FILENAME
    )
    start_date, end_date = validate_invoice_period(args.start, args.end)

    # Load and validate JSON data files
    logger.info("Loading configuration files...")
    student_data = load_student_data(str(data_dir / STUDENTS_FILENAME))
    bank_details = load_bank_details(str(data_dir / BANK_DETAILS_FILENAME))
    contact_details = load_contact_details(
        str(data_dir / CONTACT_DETAILS_FILENAME)
    )
    console.print("[green]✓[/green] [cyan]Configuration files loaded[/cyan]")

    # Authenticate Google Calendar
    logger.info("Authenticating with Google Calendar...")
    service = authenticate(
        str(data_dir / CREDENTIALS_FILENAME),
        str(data_dir / TOKEN_FILENAME),
    )
    console.print("[green]✓[/green] [cyan]Authenticated with Google[/cyan]")

    # Fetch all Google Calendar events over the invoice period
    logger.info("Fetching and processing Google Calendar events")
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
    console.print("[green]✓[/green] [cyan]Events fetched and processed[/cyan]")

    # If `--only` is not specified (user is generating invoices for all
    # students seen in the invoice period), print a list of inactive students
    # to prompt the user to contact them.
    if not args.only:
        print_inactive_students(lessons, student_data)

    # Write invoices
    logger.info("Writing invoices...")
    invoices = write_invoices(lessons, start_date, end_date, bank_details,
                              contact_details, args.output_dir)
    logger.info(f"Invoices saved to: {invoices}")
    console.print(f"\n[cyan]Invoices saved to:[/cyan] {invoices}")
    console.print(f"[cyan]Detailed logs:[/cyan] {log_file}\n")
