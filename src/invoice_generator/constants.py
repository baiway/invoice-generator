"""
Configuration constants for the invoice generator.

This module centralizes magic strings and configuration values used throughout
the application, making them easier to maintain and test.
"""

# File paths. `DATA_DIR` and `OUTPUT_DIR` are deliberately relative: they
# resolve against the directory the command is run from, so invoices land
# beside the data they were generated from. The CLI's `--data-dir` and
# `--output-dir` flags override them.
DATA_DIR = "data"

STUDENTS_FILENAME = "students.json"
BANK_DETAILS_FILENAME = "bank_details.json"
CONTACT_DETAILS_FILENAME = "contact_details.json"
CREDENTIALS_FILENAME = "credentials.json"
TOKEN_FILENAME = "token.json"

STUDENTS_FILE = f"{DATA_DIR}/{STUDENTS_FILENAME}"
BANK_DETAILS_FILE = f"{DATA_DIR}/{BANK_DETAILS_FILENAME}"
CONTACT_DETAILS_FILE = f"{DATA_DIR}/{CONTACT_DETAILS_FILENAME}"
CREDENTIALS_FILE = f"{DATA_DIR}/{CREDENTIALS_FILENAME}"
TOKEN_FILE = f"{DATA_DIR}/{TOKEN_FILENAME}"

# Templates ship inside the package; these name the resource, not a path
TEMPLATE_PACKAGE = "invoice_generator"
TEMPLATE_DIR = "templates"
INVOICE_TEMPLATE = "invoice-template.html"
STYLES_CSS = "styles.css"

OUTPUT_DIR = "invoices"
LOG_FILE = "invoice-generator.log"

# Google Calendar API
GOOGLE_CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

# Date formats
DATE_FORMAT_INPUT = "%Y-%m-%d"
DATE_FORMAT_BRITISH = "%d/%m/%Y"
DATE_FORMAT_MONTH_YEAR = "%B %Y"
TIME_FORMAT_24H = "%H:%M"
