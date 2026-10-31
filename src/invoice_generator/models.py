"""
Pydantic models for data validation.

This module defines Pydantic models for all JSON configuration files,
providing runtime validation and type safety. Models store raw data
and provide formatting methods for display purposes.
"""

import re
from typing import Self

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

# A Google Drive folder's link, as copied from Drive's "Share" dialog or
# address bar, e.g. "https://drive.google.com/drive/folders/1AbC?usp=sharing"
# or ".../drive/u/0/folders/1AbC". The group is the folder's ID.
DRIVE_FOLDER_URL = re.compile(
    r"^https://drive\.google\.com/drive/(?:u/\d+/)?folders/([\w-]+)"
)


class StudentInfo(BaseModel):
    """Student information model."""

    client_type: str = Field(..., min_length=1, description="Client type (e.g., private, agency name)")
    rate: float = Field(..., gt=0, description="Hourly rate in GBP")
    emails: list[EmailStr] = Field(
        default_factory=list,
        description="Email addresses for calendar matching (can be empty for students matched by event title)"
    )
    reports: bool = Field(
        default=False,
        description="Whether to write lesson reports for this student (with `--reports`)"
    )
    folders: list[str] = Field(
        default_factory=list,
        description="Links to the Google Drive folders holding the student's lessons, one per subject"
    )

    @field_validator("folders")
    @classmethod
    def check_folder_links(cls, v: list[str]) -> list[str]:
        """Check each folder is a link to a Google Drive folder."""
        for url in v:
            if not DRIVE_FOLDER_URL.match(url):
                raise ValueError(f"'{url}' is not a link to a Google Drive folder")
        return v

    @model_validator(mode="after")
    def check_report_folders(self) -> Self:
        """Students with reports need somewhere to find their lessons."""
        if self.reports and not self.folders:
            raise ValueError("`reports` is true, so `folders` must list at least one folder")
        return self

    @property
    def folder_ids(self) -> list[str]:
        """The IDs of the Google Drive folders in `folders`."""
        return [
            match.group(1)
            for url in self.folders
            if (match := DRIVE_FOLDER_URL.match(url))
        ]


class BankDetails(BaseModel):
    """Bank details model.

    Stores raw data and provides formatted properties for display.
    Account number and sort code accept input with or without formatting,
    stores as raw digits.
    """

    name: str = Field(..., min_length=1, description="Account holder name")
    sort_code: str = Field(..., description="Bank sort code (6 digits, dashes optional)")
    account_number: str = Field(..., description="Bank account number (8 digits, spaces optional)")
    bank: str = Field(..., min_length=1, description="Bank name")

    @field_validator("sort_code")
    @classmethod
    def normalise_sort_code(cls, v: str) -> str:
        """Strip dashes and validate sort code is 6 digits."""
        # Remove all dashes and whitespace
        normalised = v.replace("-", "").replace(" ", "")

        # Validate it's exactly 6 digits
        if not normalised.isdigit() or len(normalised) != 6:
            raise ValueError("Sort code must be exactly 6 digits")

        return normalised

    @field_validator("account_number")
    @classmethod
    def normalise_account_number(cls, v: str) -> str:
        """Strip whitespace and validate account number is 8 digits."""
        # Remove all whitespace
        normalised = "".join(v.split())

        # Validate it's exactly 8 digits
        if not normalised.isdigit() or len(normalised) != 8:
            raise ValueError("Account number must be exactly 8 digits")

        return normalised

    @property
    def formatted_sort_code(self) -> str:
        """Format sort code as 'XX-XX-XX' for display."""
        return f"{self.sort_code[:2]}-{self.sort_code[2:4]}-{self.sort_code[4:]}"

    @property
    def formatted_account_number(self) -> str:
        """Format account number as 'XXXX XXXX' for display."""
        return f"{self.account_number[:4]} {self.account_number[4:]}"


class ContactDetails(BaseModel):
    """Contact details model.

    Stores raw data with country code and phone number separately,
    provides formatted international number for display.
    """

    country_code: str = Field(
        ...,
        pattern=r"^\+\d+$",
        description="Country calling code (e.g., +44, +1)"
    )
    phone_number: str = Field(
        ...,
        min_length=10,
        description="Phone number without country code"
    )
    email: EmailStr = Field(..., description="Email address")

    @field_validator("phone_number")
    @classmethod
    def normalise_phone_number(cls, v: str) -> str:
        """Normalise phone number to digits only."""
        # Remove all non-digit characters
        normalised = "".join(c for c in v if c.isdigit())

        if len(normalised) < 10:
            raise ValueError(f"Phone number must have at least 10 digits, got {len(normalised)}")

        return normalised

    @property
    def formatted_mobile(self) -> str:
        """Format as international phone number.

        Examples:
            country_code="+44", phone_number="1234567890" -> "+44 1234 567890"
            country_code="+1", phone_number="2025551234" -> "+1 2025 551234"
        """
        # Format: +CC XXXX XXXXXX
        # Note: phone_number is guaranteed to have >= 10 digits by the validator
        return f"{self.country_code} {self.phone_number[:4]} {self.phone_number[4:]}"

