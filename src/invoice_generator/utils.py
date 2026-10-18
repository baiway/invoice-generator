from datetime import datetime, timedelta

def get_last_full_month() -> tuple[datetime, datetime]:
    """Returns the first and last days of the last full month, at
    midnight. For example, if this function were called on 11th
    November 2024, it would return 2024-10-01 and 2024-10-31.
    """
    today = datetime.today()
    first_day_this_month = today.replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    last_day_last_month = first_day_this_month - timedelta(days=1)
    first_day_last_month = last_day_last_month.replace(day=1)
    return first_day_last_month, last_day_last_month
