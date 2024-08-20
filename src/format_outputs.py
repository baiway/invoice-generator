import logging
import numpy as np
from datetime import datetime, timedelta
import pytz
from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML, CSS

# Suppress strange warnings from fontTools
logging.basicConfig(level=logging.ERROR)


def format_british_date(value):
    """Converts numpy.datetime64 into date string in DD/MM/YYYY format."""
    date_str = str(value)
    date_obj = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S")
    return date_obj.strftime("%d/%m/%Y")


def format_24h_time(t):
    """Converts datetime string to 24-hour time format."""

    if isinstance(t, np.datetime64):
        t = t.astype("datetime64[ms]").astype(datetime).replace(tzinfo=pytz.utc)

    tz = pytz.timezone("Europe/London")
    local_time = t.astimezone(tz)

    return local_time.strftime("%H:%M")


def format_hours_minutes(value):
    """Formats a numpy.timedelta64 into a human-readable time interval."""
    total_seconds = value.astype("timedelta64[s]").astype(int)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60

    hour_str = "hour" if hours == 1 else "hours"
    minute_str = "minute" if minutes == 1 else "minutes"

    if hours and minutes:
        return f"{hours} {hour_str}, {minutes} {minute_str}"
    elif hours:
        return f"{hours} {hour_str}"
    elif minutes:
        return f"{minutes} {minute_str}"
    else:
        return "0 hours"


def format_currency(value):
    """Formats a floating point number as £xx.xx"""
    return "£{:,.2f}".format(value)


def get_invoice_period(start_date, end_date):
    """Determines whether the invoice period is displayed as the last month
    (e.g. 'June') or a date interval (e.g. 01/01/2023 to 05/05/2023)
    """
    next_month = start_date.replace(day=28) + timedelta(days=4)
    last_day_of_month = next_month - timedelta(days=next_month.day)

    if (start_date.day == 1) and (end_date == last_day_of_month):
        return start_date.strftime("%B")  # covers whole month
    else:
        formatted_start_date = start_date.strftime("%d/%m/%Y")
        formatted_end_date = end_date.strftime("%d/%m/%Y")
        return f"{formatted_start_date} to {formatted_end_date}"


def write_invoices(output_dir, lessons, start_date, end_date):
    """Generates and writes invoice PDFs for each student."""
    # Initialise Jinja2 and WeasyPrint and add custom filters
    env = Environment(
        loader=FileSystemLoader("."), autoescape=select_autoescape(["html", "xml"])
    )
    env.filters["british_date"] = format_british_date
    env.filters["time_24h"] = format_24h_time
    env.filters["hours_minutes"] = format_hours_minutes
    env.filters["currency"] = format_currency
    template = env.get_template("templates/invoice-template.html")
    css = CSS("styles/styles.css")

    invoice_date = datetime.now().strftime("%d/%m/%Y")
    invoice_period = get_invoice_period(start_date, end_date)

    agency_html = {}
    for student, lesson_info in lessons.items():
        start_times = np.array(
            [s.rstrip("Z") for s in lesson_info["start"]], dtype="datetime64"
        )
        end_times = np.array([e.rstrip("Z") for e in lesson_info["end"]], dtype="datetime64")

        session_lengths = end_times - start_times

        total_hours = np.sum(session_lengths)
        total_charge = (total_hours.astype(int) / 3600) * lesson_info["rate"]
        rendered_html = template.render(
            student=student,
            invoice_period=invoice_period,
            invoice_date=invoice_date,
            timings=zip(start_times, end_times, session_lengths),
            total_hours=total_hours,
            rate=lesson_info["rate"],
            total_charge=total_charge,
        )

        client_type = lesson_info["client_type"]

        if client_type == "private":
            html = HTML(string=rendered_html)
            filename = f"{student.lower()}-invoice.pdf".replace(" ", "-")
            html.write_pdf(output_dir / filename, stylesheets=[css])
        else:
            if client_type not in agency_html:
                agency_html[client_type] = []
            agency_html[client_type].append(rendered_html)

    for agency, pages in agency_html.items():
        combined_html = "<html><body>"
        for page in pages:
            combined_html += f"{page}<hr>"
        combined_html += "</body></html>"

        html = HTML(string=combined_html)
        filename = f"{agency.lower()}-invoice.pdf".replace(" ", "-")
        html.write_pdf(output_dir / filename, stylesheets=[css])

def print_inactive_students(lessons, student_data):
    for student in student_data:
        if student not in lessons:
            print(f"  {student} not seen in this period.")
# TODO
# - Print a list of students who you haven't seen this month
