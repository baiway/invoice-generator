from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


def format_british_date(dt: datetime) -> str:
    """Converts datetime object into a string in DD/MM/YYYY format."""
    return dt.strftime("%d/%m/%Y")


def format_24h_time(dt: datetime) -> str:
    """Converts datetime object into a 24-hour time string (e.g. "15:00")
    in UK timezone."""
    tz = ZoneInfo("Europe/London")
    local_time = dt.astimezone(tz)

    return local_time.strftime("%H:%M")


def format_hours_minutes(dt: timedelta) -> str:
    """Formats a datetime.timedelta object into a human-readable time
    interval."""
    total_seconds = int(dt.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60

    hour_str = "hour" if hours == 1 else "hours"
    minute_str = "minute" if minutes == 1 else "mins"

    if hours and minutes:
        return f"{hours} {hour_str} {minutes} {minute_str}"
    elif hours:
        return f"{hours} {hour_str}"
    elif minutes:
        return f"{minutes} {minute_str}"
    else:
        return "0 hours"


def format_currency(amount: float) -> str:
    """Formats a floating point number as £xx.xx"""
    return f"£{amount:,.2f}"
