"""
Pydantic models for data validation.

This module defines Pydantic models for all JSON configuration files,
providing runtime validation and type safety. Models store raw data
and provide formatting methods for display purposes.
"""

from pydantic import BaseModel, EmailStr, Field, field_validator, RootModel


class StudentInfo(BaseModel):
    """Student information model."""

    client_type: str = Field(..., min_length=1, description="Client type (e.g., private, agency name)")
    rate: float = Field(..., gt=0, description="Hourly rate in GBP")
    emails: list[EmailStr] = Field(
        default_factory=list,
        description="Email addresses for calendar matching (can be empty for students matched by event title)"
    )

    model_config = {
        "frozen": False  # Allow modification if needed
    }

    @property
    def formatted_rate(self) -> str:
        """Format rate to 2 decimal places for display."""
        return f"{self.rate:.2f}"


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
    link: str = Field(..., description="Payment link URL (must contain 'amt' placeholder)")
    QR_code: str = Field(..., description="QR code image URL (must contain 'amt' placeholder)")

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

    @field_validator("link", "QR_code")
    @classmethod
    def validate_contains_placeholder(cls, v: str) -> str:
        """Validate that payment links contain the 'amt' placeholder."""
        if "amt" not in v:
            raise ValueError("Must contain 'amt' placeholder for dynamic amount replacement")
        return v

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
        if len(self.phone_number) >= 10:
            return f"{self.country_code} {self.phone_number[:4]} {self.phone_number[4:]}"
        return f"{self.country_code} {self.phone_number}"


class StudentsData(RootModel[dict[str, StudentInfo]]):
    """Root model for students.json file."""

    root: dict[str, StudentInfo]

    def __iter__(self):  # type: ignore
        """Allow iteration over students."""
        return iter(self.root)

    def __getitem__(self, item: str) -> StudentInfo:
        """Allow dictionary-style access."""
        return self.root[item]

    def items(self):  # type: ignore
        """Allow .items() access like a dictionary."""
        return self.root.items()

    def keys(self):  # type: ignore
        """Allow .keys() access like a dictionary."""
        return self.root.keys()

    def values(self):  # type: ignore
        """Allow .values() access like a dictionary."""
        return self.root.values()
