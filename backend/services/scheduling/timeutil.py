from datetime import date as date_type
from datetime import time as time_type

from .types import SlotSpec


def to_minutes(d: date_type, t: time_type, week_start: date_type) -> int:
    """Minutes since the start of week_start (00:00), for use as CP-SAT interval coordinates."""
    return (d - week_start).days * 24 * 60 + t.hour * 60 + t.minute


def duration_minutes(slot: SlotSpec) -> int:
    start = slot.start_time.hour * 60 + slot.start_time.minute
    end = slot.end_time.hour * 60 + slot.end_time.minute
    return end - start


def window_covers_slot(window_date: date_type, window_start: time_type, window_end: time_type, slot: SlotSpec) -> bool:
    if window_date != slot.date:
        return False
    return window_start <= slot.start_time and window_end >= slot.end_time
