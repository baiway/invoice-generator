"""
Data loading and validation utilities.

This module provides type-safe loading of JSON configuration files
with Pydantic validation and comprehensive error handling.
"""

import json
import logging
from pathlib import Path
from typing import TypeVar, Type

from pydantic import BaseModel, ValidationError

from src.constants import (
    STUDENTS_FILE,
    BANK_DETAILS_FILE,
    CONTACT_DETAILS_FILE,
)
from src.models import StudentInfo, BankDetails, ContactDetails, StudentsData

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


def load_json_with_model(
    model: Type[T],
    file_path: str,
    description: str = "data"
) -> T:
    """
    Load and validate JSON file using a Pydantic model.

    Args:
        model: Pydantic model class to validate against
        file_path: Path to JSON data file
        description: Human-readable description for error messages

    Returns:
        Validated model instance

    Raises:
        FileNotFoundError: If data file doesn't exist
        json.JSONDecodeError: If JSON is malformed
        ValidationError: If data doesn't match model schema
    """
    try:
        with open(file_path) as f:
            data = json.load(f)
    except FileNotFoundError as e:
        logger.error(f"{description} file not found at '{file_path}'. "
            f"Please create this file according to README.md instructions.")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {file_path}: {e}")
        raise

    # Validate data against model
    try:
        validated = model.model_validate(data)
        logger.info(f"Successfully validated {description}: {file_path}")
        return validated
    except ValidationError as e:
        logger.error(f"Validation failed for {file_path}: {e}")
        # Format validation errors for user
        errors = []
        for error in e.errors():
            location = " -> ".join(str(loc) for loc in error['loc'])
            errors.append(f"  - {location}: {error['msg']}")
        error_msg = f"`{file_path}` has invalid format:\n" + "\n".join(errors)
        raise ValidationError.from_exception_data(
            title=f"Invalid {description}",
            line_errors=[],
        ) from e


def load_student_data() -> dict[str, StudentInfo]:
    """
    Load and validate student data from students.json.

    Returns:
        Dictionary mapping student names to StudentInfo objects

    Raises:
        FileNotFoundError: If students.json doesn't exist
        ValidationError: If students.json has invalid format
    """
    students_model = load_json_with_model(
        StudentsData,
        STUDENTS_FILE,
        "students.json"
    )
    return students_model.root


def load_bank_details() -> BankDetails:
    """
    Load and validate bank details from bank_details.json.

    Returns:
        BankDetails instance

    Raises:
        FileNotFoundError: If bank_details.json doesn't exist
        ValidationError: If bank_details.json has invalid format
    """
    return load_json_with_model(
        BankDetails,
        BANK_DETAILS_FILE,
        "bank_details.json"
    )


def load_contact_details() -> ContactDetails:
    """
    Load and validate contact details from contact_details.json.

    Returns:
        ContactDetails instance

    Raises:
        FileNotFoundError: If contact_details.json doesn't exist
        ValidationError: If contact_details.json has invalid format
    """
    return load_json_with_model(
        ContactDetails,
        CONTACT_DETAILS_FILE,
        "contact_details.json"
    )
