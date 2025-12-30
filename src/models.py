"""
Pydantic models for data validation.

This module defines Pydantic models for all JSON configuration files,
providing runtime validation and type safety.
"""

from pydantic import BaseModel, EmailStr, Field, field_validator, RootModel


class StudentInfo(BaseModel):
    """Student information model."""

    client_type: str = Field(..., min_length=1, description="Client type (e.g., private, agency name)")
    rate: float = Field(..., gt=0, description="Hourly rate in GBP")
    emails: list[EmailStr] = Field(..., min_length=1, description="Email addresses for calendar matching")

    model_config = {
        "frozen": False  # Allow modification if needed
    }


class BankDetails(BaseModel):
    """Bank details model."""

    name: str = Field(..., min_length=1, description="Account holder name")
    sort_code: str = Field(..., pattern=r"^\d{2}-\d{2}-\d{2}$", description="Bank sort code (format: XX-XX-XX)")
    account_number: str = Field(..., pattern=r"^\d{4} \d{4}$", description="Bank account number")
    bank: str = Field(..., min_length=1, description="Bank name")
    link: str = Field(..., description="Payment link URL (must contain 'amt' placeholder)")
    QR_code: str = Field(..., description="QR code image URL (must contain 'amt' placeholder)")

    @field_validator("link", "QR_code")
    @classmethod
    def validate_contains_placeholder(cls, v: str) -> str:
        """Validate that payment links contain the 'amt' placeholder."""
        if "amt" not in v:
            raise ValueError("Must contain 'amt' placeholder for dynamic amount replacement")
        return v


class ContactDetails(BaseModel):
    """Contact details model."""

    mobile: str = Field(..., pattern=r"^[\d ]+$", min_length=10, description="Mobile phone number")
    email: EmailStr = Field(..., description="Email address")


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
