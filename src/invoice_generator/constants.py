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

# Templates ship inside the package; these name the resource, not a path
TEMPLATE_PACKAGE = "invoice_generator"
TEMPLATE_DIR = "templates"
INVOICE_TEMPLATE = "invoice.typ"

OUTPUT_DIR = "invoices"

# One log per run, named after when it started (e.g.
# `logs/2026-10-18_13-24-01.log`), so names sort in time order. Relative,
# like `OUTPUT_DIR`.
LOG_DIR = "logs"
LOG_FILENAME_FORMAT = "%Y-%m-%d_%H-%M-%S.log"

# Google APIs. Read-only access is all the generator ever needs.
GOOGLE_CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
GOOGLE_DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
