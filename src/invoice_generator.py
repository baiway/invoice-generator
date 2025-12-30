"""
Invoice generation and PDF rendering.

This module handles generating HTML invoices from lesson data and
rendering them as PDFs using WeasyPrint.
"""

import pandas as pd
import calendar
from datetime import datetime
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML, CSS
from bs4 import BeautifulSoup
from typing import Any

from src.formatting import (
    format_british_date,
    format_24h_time,
    format_hours_minutes,
    format_currency
)
from src.constants import CLIENT_TYPE_PRIVATE, AMOUNT_PLACEHOLDER
from src.models import BankDetails, ContactDetails, StudentInfo
from src.logging_config import get_logger

logger = get_logger(__name__)

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
    output_dir: Path,
    lessons: pd.DataFrame,
    start_date: datetime,
    end_date: datetime,
    bank_details: BankDetails,
    contact_details: ContactDetails
):
    """Generates and writes invoice as PDFs for specified students over the invoice period.

    Args:
        output_dir: Directory to write PDF invoices to
        lessons: DataFrame containing lesson information
        start_date: Start of invoice period
        end_date: End of invoice period
        bank_details: BankDetails model with payment information
        contact_details: ContactDetails model with contact information
    """
    # Initialise Jinja2 (templating) and WeasyPrint (generating PDFs)
    # and add custom filters
    env = Environment(
        loader=FileSystemLoader("."),
        autoescape=select_autoescape(["html", "xml"])
    )
    env.filters["british_date"] = format_british_date
    env.filters["time_24h"] = format_24h_time
    env.filters["hours_minutes"] = format_hours_minutes
    env.filters["currency"] = format_currency
    template = env.get_template("template/invoice-template.html")
    css = CSS("template/styles.css")

    invoice_period = get_invoice_period(start_date, end_date)

    # Container to produce separate invoices for each agency; keys will be
    # the agency names
    agency_html = {}

    grouped_lessons = lessons.groupby("student")

    for student, lesson_info in grouped_lessons:
        # Get start and end times for each session
        start_times = lesson_info["start"]
        end_times = lesson_info["end"]

        # Calculate amount owed
        session_lengths = end_times - start_times
        total_hours = session_lengths.sum()
        rate = lesson_info["rate"].iloc[0]
        client_type = lesson_info["client_type"].iloc[0]
        total_charge = (total_hours / pd.Timedelta(hours=1)) * rate

        # Only include bank details for private clients, not agencies
        deets = True # always include payment information

        # Generate QR code and payment link dynamically based on amount owed
        QR_code = bank_details.QR_code.replace(AMOUNT_PLACEHOLDER, str(int(total_charge * 100)))
        link = bank_details.link.replace(AMOUNT_PLACEHOLDER, str(total_charge))

        # Substitute lesson information into template HTML
        rendered_html = template.render(
            student=student,
            invoice_period=invoice_period,
            timings=zip(start_times, end_times, session_lengths),
            total_hours=total_hours,
            rate=rate,
            total_charge=total_charge,
            deets=deets,
            link=link if deets else "",
            QR_code=QR_code if deets else "",
            name=bank_details.name if deets else "",
            sort_code=bank_details.formatted_sort_code if deets else "",
            account_number=bank_details.formatted_account_number if deets else "",
            bank=bank_details.bank if deets else "",
            mobile=contact_details.formatted_mobile if deets else "",
            email=contact_details.email if deets else ""
        )

        # Generate separate PDFs for private clients and collect agency
        # lessons to form a combined PDF later.
        if client_type == CLIENT_TYPE_PRIVATE:
            html = HTML(string=rendered_html)
            filename = f"{str(student).lower()}-invoice.pdf".replace(" ", "-")
            html.write_pdf(output_dir / filename, stylesheets=[css])
            logger.info(f"Generated invoice for {student}")
        else:
            # Extract the content inside the <div class="container">
            page_content = extract_page_content(rendered_html)
            if client_type not in agency_html:
                agency_html[client_type] = []
            agency_html[client_type].append(page_content + "\n\t")

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
        invoices = ""
        for page in pages:
             invoices += page
        html = HTML(string=outer_html.format(content=invoices))
        filename = f"{agency.lower()}-invoice.pdf".replace(" ", "-")
        html.write_pdf(output_dir / filename, stylesheets=[css])
        logger.info(f"Generated combined invoice for {agency}")

def print_inactive_students(
    lessons: pd.DataFrame,
    student_data: dict[str, StudentInfo]
) -> None:
    """Prints a list of students not seen in the provided invoice period.

    This prompts the user to contact inactive students.

    Args:
        lessons: DataFrame containing lesson information
        student_data: Dictionary mapping student names to StudentInfo models
    """
    students_seen = lessons["student"].unique()

    for student in student_data:
        if student not in students_seen:
            print(f"  {student} not seen in this period.")
