"""
Invoice generation and PDF rendering.

This module handles generating HTML invoices from lesson data and
rendering them as PDFs using WeasyPrint.
"""

import calendar
from datetime import datetime, timedelta
from importlib import resources
from pathlib import Path
from jinja2 import Environment, PackageLoader, select_autoescape
from bs4 import BeautifulSoup
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
    STYLES_CSS,
    TEMPLATE_DIR,
    TEMPLATE_PACKAGE,
)
from invoice_generator.event_processing import Lesson
from invoice_generator.models import BankDetails, ContactDetails, StudentInfo
from invoice_generator.logging_config import get_logger
from invoice_generator.weasyprint_libs import configure_library_path

# Must run before WeasyPrint is imported: it `dlopen()`s its system
# libraries at import time and needs DYLD_FALLBACK_LIBRARY_PATH set to
# find them on macOS.
configure_library_path()

from weasyprint import HTML, CSS  # noqa: E402 (see above)

logger = get_logger(__name__)
console = Console()

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
    # Get the last day of the month for `start_date`
    _, last_day = calendar.monthrange(start_date.year, start_date.month)

    if (start_date.day == 1) and (end_date.day == last_day):
        return start_date.strftime("%B %Y")  # covers whole month
    else:
        formatted_start_date = start_date.strftime("%d/%m/%Y")
        formatted_end_date = end_date.strftime("%d/%m/%Y")
        return f"{formatted_start_date} to {formatted_end_date}"


def extract_page_content(rendered_html: str) -> str:
    """Extract the content inside the <div class="container">."""
    soup = BeautifulSoup(rendered_html, "html.parser")
    content = soup.find("div", class_="container")
    return str(content)


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

    # Initialise Jinja2 (templating) and WeasyPrint (generating PDFs)
    # and add custom filters
    env = Environment(
        loader=PackageLoader(TEMPLATE_PACKAGE, TEMPLATE_DIR),
        autoescape=select_autoescape(["html", "xml"])
    )
    env.filters["british_date"] = format_british_date
    env.filters["time_24h"] = format_24h_time
    env.filters["hours_minutes"] = format_hours_minutes
    env.filters["currency"] = format_currency
    template = env.get_template(INVOICE_TEMPLATE)

    # `as_file` gives WeasyPrint a real path to resolve any relative URLs
    # in the stylesheet against; the CSS is fully parsed on construction.
    styles = resources.files(TEMPLATE_PACKAGE) / TEMPLATE_DIR / STYLES_CSS
    with resources.as_file(styles) as css_path:
        css = CSS(str(css_path))

    invoice_period = get_invoice_period(start_date, end_date)

    # Container to produce separate invoices for each agency; keys will be
    # the agency names
    agency_html: dict[str, list[str]] = {}

    # Generate invoices for each student with progress bar
    for student, student_lessons in track(
        sorted(lessons.items()),
        description="[cyan]Generating invoices",
        console=console,
        transient=True
    ):
        info = student_data[student]
        client_type = info.client_type
        total_time = sum((lesson.duration for lesson in student_lessons), timedelta())
        total_charge = total_time / timedelta(hours=1) * info.rate

        # Substitute lesson information into template HTML
        rendered_html = template.render(
            student=student,
            invoice_period=invoice_period,
            lessons=student_lessons,
            total_time=total_time,
            rate=info.rate,
            total_charge=total_charge,
            name=bank_details.name,
            sort_code=bank_details.formatted_sort_code,
            account_number=bank_details.formatted_account_number,
            bank=bank_details.bank,
            mobile=contact_details.formatted_mobile,
            email=contact_details.email,
        )

        # Generate separate PDFs for private clients and collect agency
        # lessons to form a combined PDF later.
        if client_type == "private":
            html = HTML(string=rendered_html)
            filename = f"{student.lower()}-invoice.pdf".replace(" ", "-")
            html.write_pdf(output_dir / filename, stylesheets=[css])
            logger.info(f"Generated invoice for {student}")
        else:
            # Extract the content inside the <div class="container">
            page_content = extract_page_content(rendered_html)
            if client_type not in agency_html:
                agency_html[client_type] = []
            agency_html[client_type].append(page_content + "\n\t")

    # Print success message after transient progress bar disappears
    console.print("[green]✓[/green] [cyan]Invoices generated[/cyan]")

    # Define outer HTML for agency invoices (this was removed by the above)
    # `extract_page_content` call to avoid duplicating the <html>, <head>, etc.
    # tags in the template if you see multiple students from the same agency
    outer_html = (
        "<!DOCTYPE html>\n"
        "<html>\n"
        "<head lang='en'>\n"
        "  <meta charset='UTF-8'>\n"
        "</head>\n"
        "<body>\n"
        "  {content}\n"
        "<div class='clearfix'></div>"
        "</body>\n"
        "</html>\n"
    )

    # Write agency invoices; if you see multiple students from the same agency,
    # the sessions for each student will be printed on a separate page
    for agency, pages in agency_html.items():
        html = HTML(string=outer_html.format(content="".join(pages)))
        filename = f"{agency.lower()}-invoice.pdf".replace(" ", "-")
        html.write_pdf(output_dir / filename, stylesheets=[css])
        logger.info(f"Generated combined invoice for {agency}")

    return output_dir.resolve()

def print_inactive_students(
    lessons: dict[str, list[Lesson]],
    student_data: dict[str, StudentInfo]
) -> None:
    """Logs a list of students not seen in the provided invoice period.

    This prompts the user to contact inactive students.

    Args:
        lessons: Each student seen, mapped to their lessons
        student_data: Dictionary mapping student names to StudentInfo models
    """
    for student in student_data:
        if student not in lessons:
            logger.info(f"{student} not seen in this period")
