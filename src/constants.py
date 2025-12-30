"""
Configuration constants for the invoice generator.

This module centralizes magic strings and configuration values used throughout
the application, making them easier to maintain and test.
"""

# File paths
DATA_DIR = "data"
STUDENTS_FILE = f"{DATA_DIR}/students.json"
BANK_DETAILS_FILE = f"{DATA_DIR}/bank_details.json"
CONTACT_DETAILS_FILE = f"{DATA_DIR}/contact_details.json"
CREDENTIALS_FILE = f"{DATA_DIR}/credentials.json"
TOKEN_FILE = f"{DATA_DIR}/token.json"

TEMPLATE_DIR = "template"
INVOICE_TEMPLATE = f"{TEMPLATE_DIR}/invoice-template.html"
STYLES_CSS = f"{TEMPLATE_DIR}/styles.css"

OUTPUT_DIR = "invoices"
LOG_FILE = "invoice-generator.log"

# Google Calendar API
GOOGLE_CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

# Date formats
DATE_FORMAT_INPUT = "%Y-%m-%d"
DATE_FORMAT_BRITISH = "%d/%m/%Y"
DATE_FORMAT_MONTH_YEAR = "%B %Y"
TIME_FORMAT_24H = "%H:%M"
