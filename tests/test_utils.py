"""
Tests for src/invoice_generator/utils.py date utilities.
"""

from datetime import datetime
from unittest.mock import patch

from invoice_generator.utils import get_last_full_month


class TestGetLastFullMonth:
    """Tests for get_last_full_month function."""

    @patch("invoice_generator.utils.datetime")
    def test_early_in_month(self, mock_datetime):
        """Test when called early in the month (e.g., Jan 5)."""
        mock_datetime.today.return_value = datetime(2024, 1, 5)
        start, end = get_last_full_month()
        assert start == datetime(2023, 12, 1)
        assert end == datetime(2023, 12, 31)

    @patch("invoice_generator.utils.datetime")
    def test_end_of_month(self, mock_datetime):
        """Test when called at end of month (e.g., Jan 31)."""
        mock_datetime.today.return_value = datetime(2024, 1, 31)
        start, end = get_last_full_month()
        assert start == datetime(2023, 12, 1)
        assert end == datetime(2023, 12, 31)

    @patch("invoice_generator.utils.datetime")
    def test_february_leap_year(self, mock_datetime):
        """Test February in leap year."""
        mock_datetime.today.return_value = datetime(2024, 3, 15)
        start, end = get_last_full_month()
        assert start == datetime(2024, 2, 1)
        assert end == datetime(2024, 2, 29)  # 2024 is leap year

    @patch("invoice_generator.utils.datetime")
    def test_february_non_leap_year(self, mock_datetime):
        """Test February in non-leap year."""
        mock_datetime.today.return_value = datetime(2023, 3, 15)
        start, end = get_last_full_month()
        assert start == datetime(2023, 2, 1)
        assert end == datetime(2023, 2, 28)

    @patch("invoice_generator.utils.datetime")
    def test_time_of_day_is_dropped(self, mock_datetime):
        """Both dates should be at midnight whenever it is called."""
        mock_datetime.today.return_value = datetime(2024, 1, 5, 15, 30, 12, 5)
        start, end = get_last_full_month()
        assert start == datetime(2023, 12, 1)
        assert end == datetime(2023, 12, 31)
