"""
Tests for src/formatting.py display formatting functions.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from src.formatting import (
    format_british_date,
    format_24h_time,
    format_hours_minutes,
    format_currency,
)


class TestFormatBritishDate:
    """Tests for format_british_date function."""

    def test_standard_date(self):
        """Standard date should format as DD/MM/YYYY."""
        dt = datetime(2024, 1, 5, 10, 30)
        assert format_british_date(dt) == "05/01/2024"

    def test_end_of_year(self):
        """End of year date should format correctly."""
        dt = datetime(2023, 12, 31, 23, 59)
        assert format_british_date(dt) == "31/12/2023"


class TestFormat24hTime:
    """Tests for format_24h_time function."""

    def test_utc_to_uk_time(self):
        """UTC time should convert to UK timezone."""
        # UTC 10:00 in winter = UK 10:00 (GMT)
        dt = datetime(2024, 1, 15, 10, 0, tzinfo=ZoneInfo("UTC"))
        assert format_24h_time(dt) == "10:00"

    def test_utc_to_uk_bst(self):
        """UTC time should convert to BST in summer."""
        # UTC 10:00 in summer = UK 11:00 (BST)
        dt = datetime(2024, 7, 15, 10, 0, tzinfo=ZoneInfo("UTC"))
        assert format_24h_time(dt) == "11:00"


class TestFormatHoursMinutes:
    """Tests for format_hours_minutes function."""

    def test_hours_only(self):
        """Whole hours should format without minutes."""
        td = timedelta(hours=2)
        assert format_hours_minutes(td) == "2 hours"

    def test_one_hour(self):
        """One hour should use singular form."""
        td = timedelta(hours=1)
        assert format_hours_minutes(td) == "1 hour"

    def test_hours_and_minutes(self):
        """Mixed hours and minutes should show both."""
        td = timedelta(hours=2, minutes=30)
        assert format_hours_minutes(td) == "2 hours 30 mins"

    def test_one_hour_one_minute(self):
        """Singular forms for both units."""
        td = timedelta(hours=1, minutes=1)
        assert format_hours_minutes(td) == "1 hour 1 minute"

    def test_minutes_only(self):
        """Only minutes should format correctly."""
        td = timedelta(minutes=45)
        assert format_hours_minutes(td) == "45 mins"

    def test_zero_duration(self):
        """Zero duration should format appropriately."""
        td = timedelta(seconds=0)
        assert format_hours_minutes(td) == "0 hours"


class TestFormatCurrency:
    """Tests for format_currency function."""

    def test_integer_amount(self):
        """Integer amounts should show .00."""
        assert format_currency(50) == "£50.00"

    def test_decimal_amount(self):
        """Decimal amounts should round to 2 places."""
        assert format_currency(123.456) == "£123.46"

    def test_large_amount(self):
        """Large amounts should include comma separator."""
        assert format_currency(1234.50) == "£1,234.50"

    def test_zero(self):
        """Zero should format correctly."""
        assert format_currency(0) == "£0.00"
