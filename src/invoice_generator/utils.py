from typing import Tuple
from datetime import datetime, timedelta

def get_last_full_month() -> Tuple[str, str]:
    """Returns the start date and end date of the last full month
    in YYYY-MM-DD format. For example, if this function were called
    on 11th November 2024, it would return ("2024-10-01", "2024-10-31").
    """
    today = datetime.today()
    first_day_this_month= today.replace(day=1)
    last_day_last_month = first_day_this_month - timedelta(days=1)
    first_day_last_month = last_day_last_month.replace(day=1)
    return (
        first_day_last_month.strftime("%Y-%m-%d"),
        last_day_last_month.strftime("%Y-%m-%d")
    )
