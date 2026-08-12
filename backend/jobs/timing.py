"""Pure scheduling-window logic — no DB, easily unit-tested against injected times.
Kept separate from jobs/tasks.py so the timezone/day-of-week math can be verified
without needing a database."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


def is_request_due(
    business_timezone: str,
    request_day_of_week: int,
    request_time_hhmm: str,
    now_utc: datetime,
) -> bool:
    """True if `now_utc`, converted to the business's local timezone, falls in the
    same clock hour as the business's configured weekly availability-request
    day/time. The scheduler ticks hourly, so hour-level granularity is what
    actually matters here — exact-minute matching would let a tick landing a
    few seconds late miss the window entirely.
    """
    local_now = now_utc.astimezone(ZoneInfo(business_timezone))
    if local_now.weekday() != request_day_of_week:
        return False

    try:
        request_hour = int(request_time_hhmm.split(":")[0])
    except (ValueError, IndexError):
        return False

    return local_now.hour == request_hour
