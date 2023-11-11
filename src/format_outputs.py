import numpy as np
from datetime import datetime, timedelta
from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML, CSS

def format_british_date(value):
    """Converts numpy.datetime64 into date string in DD/MM/YYYY format.
    """
    date_str = str(value)
    date_obj = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S")
    return date_obj.strftime("%d/%m/%Y")

def format_24h_time(value):
    """Converts datetime string to 24-hour time format.
    """
    date_str = str(value)
    date_obj = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S")
    return date_obj.strftime("%H:%M")

def format_hours_minutes(value):
    """Formats a numpy.timedelta64 into a human-readable time interval.
    """
    # Assuming value is a NumPy timedelta64 object in seconds
    # First, convert the duration to total seconds as integer
    total_seconds = value.astype("timedelta64[s]").astype(int)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60

    # Determine the correct singular or plural form for hours and minutes
    hour_str = "hour" if hours == 1 else "hours"
    minute_str = "minute" if minutes == 1 else "minutes"

    # Build the formatted length string
    if hours and minutes:
        return f"{hours} {hour_str}, {minutes} {minute_str}"
    elif hours:
        return f"{hours} {hour_str}"
    elif minutes:
        return f"{minutes} {minute_str}"
    else:
        return "0 hours"

def format_currency(value):
    """Formats a floating point number as £xx.xx
    """
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

def write_invoices(lessons, student_data, start_date, end_date):
    """Generates and writes invoice PDFs for each student.
    """
    env = Environment(loader=FileSystemLoader("."),
                      autoescape=select_autoescape(["html", "xml"]))
    env.filters["british_date"] = format_british_date
    env.filters["time_24h"] = format_24h_time
    env.filters["hours_minutes"] = format_hours_minutes
    env.filters["currency"] = format_currency
    template = env.get_template("templates/invoice-template.html")
    css = CSS(filename="styles/styles.css")

    invoice_date = datetime.now().strftime("%d/%m/%Y")
    invoice_period = get_invoice_period(start_date, end_date)
    
    for student, times in lessons.items():
        start_times = np.array([s.rstrip("Z") for s in times["start"]], dtype="datetime64")
        end_times = np.array([e.rstrip("Z") for e in times["end"]], dtype="datetime64")

        session_lengths = end_times - start_times
        
        total_hours = np.sum(session_lengths)
        total_charge = (total_hours.astype(int) / 3600) * student_data[student]["rate"]
        rendered_html = template.render(
            student=student,
            invoice_period=invoice_period,
            invoice_date=invoice_date,
            timings=zip(start_times, end_times, session_lengths),
            total_hours=total_hours,
            rate=student_data[student]["rate"],
            total_charge=total_charge
        )

        html = HTML(string=rendered_html)
        html.write_pdf(f"invoices/{student}-invoice.pdf", stylesheets=[css])

# for student in lessons.keys():
#     grove_list = 
#     if student_data[student] == "grove":
        
# Print a list of students who you haven't seen this month
    # for student in student_data.keys():
    #     if student not in lessons.keys():
    #         print(f"No lessons found with student: {student}")
    # return lessons
