"""
Invoice generation and PDF rendering.

This module formats each student's lessons for display and renders
them as PDFs with Typst, using `templates/invoice.typ`.
"""

import calendar
import json
from datetime import datetime, timedelta
from importlib import resources
from pathlib import Path
from typing import Any

import typst
from rich.progress import track
from rich.console import Console

from invoice_generator.formatting import (
    format_british_date,
    format_24h_time,
    format_hours_minutes,
    format_currency
)
from invoice_generator.constants import (
    INVOICE_TEMPLATE,
    TEMPLATE_DIR,
    TEMPLATE_PACKAGE,
)
from invoice_generator.event_processing import Lesson
from invoice_generator.models import BankDetails, ContactDetails, StudentInfo
from invoice_generator.logging_config import get_logger

logger = get_logger(__name__)
console = Console()

def covers_whole_month(start_date: datetime, end_date: datetime) -> bool:
    """Whether a period is exactly one calendar month, e.g. from 1st June
    to 30th June, inclusive."""
    _, last_day = calendar.monthrange(start_date.year, start_date.month)
    month_end = start_date.replace(day=last_day)
    return start_date.day == 1 and end_date.date() == month_end.date()


def get_invoice_period(
    start_date: datetime,
    end_date: datetime
) -> str:
    """Returns a string displayed in the invoice title. If the invoice
    covers a full month (e.g. from 1st June to 30th June, inclusive)
    then this returns the month and year (e.g. "June 2024"). If not,
    this returns the invoice period in dd/mm/yyyy format (e.g.
    06/04/2024 to 05/04/2025). The latter is useful for short bursts of
    tutoring, longer stints (e.g. summer holiday revision where only
    one invoice is issued), or for tax purposes.
    """
    if covers_whole_month(start_date, end_date):
        return start_date.strftime("%B %Y")
    else:
        formatted_start_date = start_date.strftime("%d/%m/%Y")
        formatted_end_date = end_date.strftime("%d/%m/%Y")
        return f"{formatted_start_date} to {formatted_end_date}"


def format_invoice(
    student: str,
    lessons: list[Lesson],
    rate: float,
) -> dict[str, Any]:
    """Formats one student's invoice for the template.

    Args:
        student: The student's name
        lessons: The student's lessons over the invoice period
        rate: Hourly rate in GBP

    Returns:
        The `invoices` entry described at the top of `invoice.typ`
    """
    total_time = sum((lesson.duration for lesson in lessons), timedelta())
    return {
        "student": student,
        "sessions": [
            {
                "date": format_british_date(lesson.start),
                "time": (
                    f"{format_24h_time(lesson.start)} until "
                    f"{format_24h_time(lesson.end)} "
                    f"({format_hours_minutes(lesson.duration)})"
                ),
            }
            for lesson in lessons
        ],
        "total_time": format_hours_minutes(total_time),
        "rate": f"{format_currency(rate)}/hour",
        "amount_owed": format_currency(total_time / timedelta(hours=1) * rate),
    }


def write_invoices(
    lessons: dict[str, list[Lesson]],
    student_data: dict[str, StudentInfo],
    start_date: datetime,
    end_date: datetime,
    bank_details: BankDetails,
    contact_details: ContactDetails,
    output_dir: Path,
) -> Path:
    """Generates and writes invoice as PDFs for specified students over the invoice period.

    Private clients get a PDF each. Students from an agency share the
    agency's PDF, a page each.

    Args:
        lessons: Each student to invoice, mapped to their lessons
        student_data: Dictionary mapping student names to StudentInfo models
        start_date: Start of invoice period
        end_date: End of invoice period
        bank_details: BankDetails model with payment information
        contact_details: ContactDetails model with contact information
        output_dir: Directory to write PDF invoices to, created if missing

    Returns:
        Absolute path to the output directory
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Shared by every invoice
    details = {
        "period": get_invoice_period(start_date, end_date),
        "bank": {
            "name": bank_details.name,
            "sort_code": bank_details.formatted_sort_code,
            "account_number": bank_details.formatted_account_number,
            "bank": bank_details.bank,
        },
        "contact": {
            "mobile": contact_details.formatted_mobile,
            "email": contact_details.email,
        },
    }

    # Group invoices by the PDF they belong in: the student's name for
    # private clients, the agency's otherwise
    pdfs: dict[str, list[dict[str, Any]]] = {}
    for student, student_lessons in sorted(lessons.items()):
        info = student_data[student]
        recipient = student if info.client_type == "private" else info.client_type
        pdfs.setdefault(recipient, []).append(
            format_invoice(student, student_lessons, info.rate)
        )

    template = resources.files(TEMPLATE_PACKAGE) / TEMPLATE_DIR / INVOICE_TEMPLATE
    with resources.as_file(template) as template_path:
        for recipient, invoices in track(
            pdfs.items(),
            description="[cyan]Generating invoices",
            console=console,
            transient=True
        ):
            filename = f"{recipient.lower()}-invoice.pdf".replace(" ", "-")
            data = {**details, "invoices": invoices}
            typst.compile(
                template_path,
                output=output_dir / filename,
                sys_inputs={"data": json.dumps(data)},
            )
            logger.info(f"Generated {filename}")

    # Print success message after transient progress bar disappears
    console.print("[green]✓[/green] [cyan]Invoices generated[/cyan]")

    return output_dir.resolve()
