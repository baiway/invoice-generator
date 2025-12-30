"""
Tests for src/utils.py date utilities.
"""

from datetime import datetime
from unittest.mock import patch

from src.utils import get_last_full_month


class TestGetLastFullMonth:
    """Tests for get_last_full_month function."""

    @patch("src.utils.datetime")
    def test_early_in_month(self, mock_datetime):
        """Test when called early in the month (e.g., Jan 5)."""
        mock_datetime.today.return_value = datetime(2024, 1, 5)
        start, end = get_last_full_month()
        assert start == "2023-12-01"
        assert end == "2023-12-31"

    @patch("src.utils.datetime")
    def test_end_of_month(self, mock_datetime):
        """Test when called at end of month (e.g., Jan 31)."""
        mock_datetime.today.return_value = datetime(2024, 1, 31)
        start, end = get_last_full_month()
        assert start == "2023-12-01"
        assert end == "2023-12-31"

    @patch("src.utils.datetime")
    def test_february_leap_year(self, mock_datetime):
        """Test February in leap year."""
        mock_datetime.today.return_value = datetime(2024, 3, 15)
        start, end = get_last_full_month()
        assert start == "2024-02-01"
        assert end == "2024-02-29"  # 2024 is leap year

    @patch("src.utils.datetime")
    def test_february_non_leap_year(self, mock_datetime):
        """Test February in non-leap year."""
        mock_datetime.today.return_value = datetime(2023, 3, 15)
        start, end = get_last_full_month()
        assert start == "2023-02-01"
        assert end == "2023-02-28"
