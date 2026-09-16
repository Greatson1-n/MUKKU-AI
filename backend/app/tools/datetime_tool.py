from datetime import datetime

def get_current_datetime() -> str:
    """Returns the current local date, time, and day of the week."""
    now = datetime.now()
    return now.strftime("Current Date: %A, %B %d, %Y | Local Time: %I:%M:%S %p")
