"""
Loading of the JSON configuration files.

Each file is validated against its Pydantic model, so a missing file
raises `FileNotFoundError` and a malformed or invalid one raises
`pydantic.ValidationError` naming every offending field.
"""

from pathlib import Path

from pydantic import ConfigDict, TypeAdapter

from invoice_generator.models import BankDetails, ContactDetails, StudentInfo

# `students.json` is a bare mapping of names to details, so it has no model
# class of its own; the title names the file in validation errors
STUDENTS = TypeAdapter(
    dict[str, StudentInfo], config=ConfigDict(title="students.json")
)


def load_student_data(path: Path) -> dict[str, StudentInfo]:
    """Load `students.json`, mapping each student's name to their details."""
    return STUDENTS.validate_json(path.read_bytes())


def load_bank_details(path: Path) -> BankDetails:
    """Load `bank_details.json`."""
    return BankDetails.model_validate_json(path.read_bytes())


def load_contact_details(path: Path) -> ContactDetails:
    """Load `contact_details.json`."""
    return ContactDetails.model_validate_json(path.read_bytes())
