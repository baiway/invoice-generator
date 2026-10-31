"""
Command line interface.

This module parses and validates command line arguments, then drives the
fetch -> process -> render pipeline. Installed as the `generate-invoices`
command; see `[project.scripts]` in `pyproject.toml`.
"""

import argparse
from datetime import date, datetime
from typing import Any
from pathlib import Path
from rich.console import Console
from rich.text import Text

from invoice_generator.calendar_api import calendar_service, fetch_events
from invoice_generator.drive_api import drive_service
from invoice_generator.event_processing import (
    Lesson,
    SkipReason,
    SkippedEvent,
    process_events,
)
from invoice_generator.formatting import format_british_date, format_24h_time
from invoice_generator.utils import get_last_full_month
from invoice_generator.invoice_generator import write_invoices
from invoice_generator.data_loader import load_student_data, load_bank_details, load_contact_details
from invoice_generator.google_auth import authenticate
from invoice_generator.logging_config import setup_logging, get_logger
from invoice_generator.models import StudentInfo
from invoice_generator.reports import ReportsOutcome, write_reports
from invoice_generator.summariser import ModelUnavailable, check_model
from invoice_generator.constants import (
    BANK_DETAILS_FILENAME,
    CONTACT_DETAILS_FILENAME,
    CREDENTIALS_FILENAME,
    DATA_DIR,
    GOOGLE_CALENDAR_SCOPES,
    GOOGLE_DRIVE_SCOPES,
    OUTPUT_DIR,
    REPORTS_DIR,
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

    parser.add_argument(
        "--reports",
        action="store_true",
        help=(
            "Also draft lesson reports, after the invoices, for students "
            "with `reports` set in `students.json`. Each lesson in their "
            "Google Drive folders is summarised by Apple's on-device model, "
            "so lesson files never leave your Mac (needs macOS 27). Edit "
            "the reports, then run `render-reports` to make PDFs."
        )
    )
    parser.add_argument(
        "--reports-dir",
        default=REPORTS_DIR,
        metavar="path",
        help=(
            "Directory to write lesson reports to, created if it does not "
            "exist. Reports already there are never overwritten. Relative "
            "paths are resolved against the current directory (default: "
            f"`{REPORTS_DIR}`)."
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


def event_time(event: dict[str, Any]) -> str:
    """When a calendar event took place, e.g. "13/10/2026 15:00–16:00",
    or just the date for an all-day event.
    """
    start, end = event["start"], event["end"]
    if "dateTime" not in start:
        return date.fromisoformat(start["date"]).strftime("%d/%m/%Y")
    start_time = datetime.fromisoformat(start["dateTime"])
    end_time = datetime.fromisoformat(end["dateTime"])
    return (
        f"{format_british_date(start_time)} "
        f"{format_24h_time(start_time)}–{format_24h_time(end_time)}"
    )


def print_skipped_events(skipped: list[SkippedEvent]) -> None:
    """Prints the events that may be lessons but couldn't be invoiced,
    grouped by reason.

    Args:
        skipped: Events skipped by `process_events`
    """
    for reason in SkipReason:
        events = [s for s in skipped if s.reason is reason]
        if not events:
            continue
        console.print(f"\n[yellow]Skipped events {reason.value}:[/yellow]")
        for s in events:
            # Built as `Text` rather than a string, so neither markup nor
            # rich's automatic highlighting applies: the date and time are
            # one colour, and the title and detail are left as they are
            when = event_time(s.event)
            line = Text("  ")
            line.append(when, style="bold cyan")
            # Pad to the width of a timed event so the titles line up
            line.append(" " * (24 - len(when)) + s.event.get("summary", ""))
            if s.detail:
                line.append(f" ({s.detail})")
            # Long lines are left for the terminal to wrap
            console.print(line, soft_wrap=True)


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
        console.print(f"  {student}", markup=False, soft_wrap=True)
        logger.info(f"{student} not seen in this period")


def print_reports_outcome(outcome: ReportsOutcome, reports_dir: Path) -> None:
    """Prints where the reports were saved, what to check in them, and
    any left as they were.

    Args:
        outcome: What `write_reports` did
        reports_dir: Directory the reports are in
    """
    if outcome.written:
        console.print(f"\n[cyan]Reports saved to:[/cyan] {reports_dir.resolve()}",
                      soft_wrap=True)
        for path in outcome.written:
            console.print(f"  {path.name}", markup=False, soft_wrap=True)
    else:
        console.print("\n[cyan]No reports to write[/cyan]")

    if outcome.warnings:
        console.print("\n[yellow]Check these in the reports:[/yellow]")
        for student, warning in outcome.warnings:
            console.print(f"  {student}: {warning}", markup=False, soft_wrap=True)

    if outcome.kept:
        console.print("\n[yellow]Reports already there, so left as they are "
                      "(delete them to write them again):[/yellow]")
        for path in outcome.kept:
            console.print(f"  {path.name}", markup=False, soft_wrap=True)


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

    # Check Apple's model can be used before anything else, so that a
    # problem with it (e.g. `fm`'s terms not agreed to) is found straight away
    if args.reports:
        try:
            check_model()
        except ModelUnavailable as e:
            console.print(f"[red]Can't write reports:[/red] {e}", soft_wrap=True)
            raise SystemExit(1) from None

    # Sign in to Google
    logger.info("Authenticating with Google...")
    scopes = GOOGLE_CALENDAR_SCOPES + (GOOGLE_DRIVE_SCOPES if args.reports else [])
    creds = authenticate(
        data_dir / CREDENTIALS_FILENAME, data_dir / TOKEN_FILENAME, scopes
    )
    console.print("[green]✓[/green] [cyan]Authenticated with Google[/cyan]")

    # Fetch all Google Calendar events over the invoice period
    logger.info("Fetching and processing Google Calendar events")
    events = fetch_events(calendar_service(creds), args.start, args.end)

    # Match events to the students listed in `students.json`, giving each
    # student's lessons: {"Alice": [Lesson(start, end), ...], ...}
    lessons, skipped = process_events(events, student_data, args.only)
    console.print("[green]✓[/green] [cyan]Events fetched and processed[/cyan]")

    # Write invoices
    logger.info("Writing invoices...")
    invoices = write_invoices(lessons, student_data, args.start, args.end,
                              bank_details, contact_details,
                              Path(args.output_dir))
    logger.info(f"Invoices saved to: {invoices}")
    # Soft wrap keeps the paths whole, so they can be copied
    console.print(f"\n[cyan]Invoices saved to:[/cyan] {invoices}", soft_wrap=True)
    console.print(f"[cyan]Detailed logs:[/cyan] {log_file}", soft_wrap=True)

    # Things to follow up, after the main output
    print_skipped_events(skipped)
    # Inactive students are only of interest when invoicing everyone
    if not args.only:
        print_inactive_students(lessons, student_data)

    # Reports last, as they take a while: the invoices can be sent meanwhile
    if args.reports:
        console.print("\n[cyan]Writing lesson reports...[/cyan]")
        reports_dir = Path(args.reports_dir)
        try:
            outcome = write_reports(lessons, student_data, args.start, args.end,
                                    drive_service(creds), reports_dir)
        except ModelUnavailable as e:
            console.print(f"[red]Stopped writing reports:[/red] {e}", soft_wrap=True)
            raise SystemExit(1) from None
        print_reports_outcome(outcome, reports_dir)
    console.print()
