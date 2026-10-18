"""
Command line interface.

This module parses and validates command line arguments, then drives the
fetch -> process -> render pipeline. Installed as the `generate-invoices`
command; see `[project.scripts]` in `pyproject.toml`.
"""

import argparse
from datetime import datetime
from pathlib import Path
from rich.console import Console

from invoice_generator.calendar_api import authenticate, fetch_events
from invoice_generator.event_processing import Lesson, process_events
from invoice_generator.utils import get_last_full_month
from invoice_generator.invoice_generator import write_invoices
from invoice_generator.data_loader import load_student_data, load_bank_details, load_contact_details
from invoice_generator.logging_config import setup_logging, get_logger
from invoice_generator.models import StudentInfo
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


def parse_date(value: str) -> datetime:
    """Parses a YYYY-MM-DD date given on the command line."""
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"invalid date '{value}' (expected YYYY-MM-DD)"
        ) from None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parses and validates command line arguments, filling in the
    default invoice period. Invalid arguments print a usage error and
    exit, as argparse does for its own checks.

    Args:
        argv: Argument list to parse. Defaults to `sys.argv[1:]`.

    Returns:
        The arguments, with `start` and `end` set to the first and last
        moments of the invoice period
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
        type=parse_date,
        metavar="YYYY-MM-DD",
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
        type=parse_date,
        metavar="YYYY-MM-DD",
        help=(
            "End of the invoice period in YYYY-MM-DD format (e.g. "
            "2024-09-30). Cannot be specified without `--from`. If "
            "neither are specified, defaults to the end of "
            "the last full month. For example, if the script is run on "
            "2024-09-03, the end of the invoice period will default to "
            "2024-08-31."
        )
    )

    args = parser.parse_args(argv)

    if args.start is None:
        if args.end is not None:
            parser.error("argument --to: not allowed without --from")
        args.start, args.end = get_last_full_month()
    elif args.end is None:
        args.end = datetime.today()

    if args.start.date() > args.end.date():
        parser.error(
            f"argument --from: {args.start:%Y-%m-%d} is after the end of the "
            f"invoice period ({args.end:%Y-%m-%d})"
        )

    # The invoice period includes the whole of its last day
    args.end = args.end.replace(hour=23, minute=59, second=59, microsecond=0)
    return args


def validate_students(
    names: list[str],
    student_data: dict[str, StudentInfo],
) -> None:
    """Validates student names supplied via the CLI using the `--only`
    flag, raising a ValueError naming any that are not in
    `students.json`. An empty list (i.e. `--only` not used) means all
    students, so needs no validation.

    Args:
        names: Names passed to `--only`.
        student_data: Dictionary mapping student names to StudentInfo models
    """
    unrecognised_names = [name for name in names if name not in student_data]
    if unrecognised_names:
        raise ValueError(
            "The following names passed using the `--only` option are not in "
            f"`students.json`: {', '.join(unrecognised_names)}"
        )


def print_inactive_students(
    lessons: dict[str, list[Lesson]],
    student_data: dict[str, StudentInfo],
) -> None:
    """Prints the students in `students.json` not seen in the invoice
    period, as a prompt to get in touch with them.

    Args:
        lessons: Each student seen, mapped to their lessons
        student_data: Dictionary mapping student names to StudentInfo models
    """
    inactive = [student for student in student_data if student not in lessons]
    if not inactive:
        return

    console.print("\n[yellow]Not seen in this period:[/yellow]")
    for student in inactive:
        console.print(f"  {student}")
        logger.info(f"{student} not seen in this period")


def main(argv: list[str] | None = None) -> None:
    # Set up logging first - detailed logs written to file
    log_file = setup_logging()

    # Parse and validate command line arguments
    args = parse_args(argv)
    data_dir = Path(args.data_dir)

    # Load and validate JSON data files
    logger.info("Loading configuration files...")
    student_data = load_student_data(data_dir / STUDENTS_FILENAME)
    bank_details = load_bank_details(data_dir / BANK_DETAILS_FILENAME)
    contact_details = load_contact_details(data_dir / CONTACT_DETAILS_FILENAME)
    validate_students(args.only, student_data)
    console.print("[green]✓[/green] [cyan]Configuration files loaded[/cyan]")

    # Authenticate Google Calendar
    logger.info("Authenticating with Google Calendar...")
    service = authenticate(
        data_dir / CREDENTIALS_FILENAME, data_dir / TOKEN_FILENAME
    )
    console.print("[green]✓[/green] [cyan]Authenticated with Google[/cyan]")

    # Fetch all Google Calendar events over the invoice period
    logger.info("Fetching and processing Google Calendar events")
    events = fetch_events(service, args.start, args.end)

    # Match events to the students listed in `students.json`, giving each
    # student's lessons: {"Alice": [Lesson(start, end), ...], ...}
    lessons = process_events(events, student_data, args.only)
    console.print("[green]✓[/green] [cyan]Events fetched and processed[/cyan]")

    # Inactive students are only of interest when invoicing everyone
    if not args.only:
        print_inactive_students(lessons, student_data)

    # Write invoices
    logger.info("Writing invoices...")
    invoices = write_invoices(lessons, student_data, args.start, args.end,
                              bank_details, contact_details,
                              Path(args.output_dir))
    logger.info(f"Invoices saved to: {invoices}")
    console.print(f"\n[cyan]Invoices saved to:[/cyan] {invoices}")
    console.print(f"[cyan]Detailed logs:[/cyan] {log_file}\n")
