import json
import datetime

def get_user_choice():
    """Used to determine whether the user wants to specify a custom date
    range or not. If not, use the last full month.
    """
    print("By default, this application generates invoices for the previous calendar month.")
    prompt = "Would you like to enter a custom date range instead? (y/n) "
    while True:
        user_input = input(prompt).strip().lower()
        if user_input == "y":
            return True
        elif user_input == "n":
            return False
        else:
            print("Invalid input. Please enter 'y' or 'n'.")


def get_last_full_month():
    """Returns datetime objects for the start date and end date of the
    last full month. For example, if this function were called on
    11th November, it would return (1st October, 31st October).
    """
    today = datetime.datetime.now(datetime.timezone.utc)
    first_day_of_current_month = today.replace(day=1, hour=0, minute=0)
    last_day_of_last_month = first_day_of_current_month - datetime.timedelta(days=1)
    first_day_of_last_month = last_day_of_last_month.replace(day=1)
    return first_day_of_last_month, last_day_of_last_month


def get_date_input(point):
    """Used when the user wants to generate invoices between to dates.
	"""
    while True:
        user_input = input(f"Enter the {point} date (YYYY-MM-DD): ")
        try:
            date_obj = datetime.datetime.fromisoformat(user_input)
            return date_obj.replace(tzinfo=datetime.timezone.utc)
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")
