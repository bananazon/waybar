import re
import time
from datetime import datetime


def get_human_timestamp() -> str:
    now = int(time.time())
    dt = datetime.fromtimestamp(now)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def to_24hour_time(input: int) -> str | None:
    try:
        # Convert to datetime (local time)
        dt = datetime.fromtimestamp(input)

        # Format as 24-hour time (HH:MM)
        return dt.strftime("%H:%M")
    except Exception:
        return None


def to_unix_time(input: str | None) -> int:
    if input:
        pattern = r"^(0[1-9]|1[0-2]):[0-5][0-9] (AM|PM)$"
        if re.match(pattern, input):
            try:
                # Parse as 12-hour format
                dt = datetime.strptime(input, "%I:%M %p")

                # Replace today's date with the parsed time
                now = datetime.now()
                dt = dt.replace(year=now.year, month=now.month, day=now.day)

                # Convert to Unix timestamp (local time)
                return int(time.mktime(dt.timetuple()))
            except Exception:
                return 0
        else:
            return 0
    return 0


def unix_to_human(timestamp, format: str = "%Y-%m-%d") -> str:
    """
    Take a Unix timestamp and convert it to the specified format.
    """
    return datetime.fromtimestamp(timestamp).strftime(format)


def unix_time_in_ms() -> int:
    """
    Return the Unix timestamp in millesconds.
    """
    return int(time.time() * 1000)


def get_timestamp(timestamp: int = 0, format: str = "%Y-%m-%d %k:%M:%S") -> str:
    """
    Take a Unix timestamp and convert it to the specified format.
    """
    return datetime.fromtimestamp(timestamp).strftime(format)


def duration(seconds: int = 0) -> tuple[int, int, int, int]:
    seconds = int(seconds)
    days = int(seconds / 86400)
    hours = int(((seconds - (days * 86400)) / 3600))
    minutes = int(((seconds - days * 86400 - hours * 3600) / 60))
    secs = int((seconds - (days * 86400) - (hours * 3600) - (minutes * 60)))

    return days, hours, minutes, secs


def get_duration(seconds: int = 0) -> str:
    d, h, m, s = duration(seconds)
    if d > 0:
        return f"{d:02d}d {h:02d}h {m:02d}m {s:02d}s"
    else:
        return f"{h:02d}h {m:02d}m {s:02d}s"
