from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from jobs.timing import is_request_due


def _utc_for_local(tz: str, year, month, day, hour, minute=0) -> datetime:
    local_dt = datetime(year, month, day, hour, minute, tzinfo=ZoneInfo(tz))
    return local_dt.astimezone(timezone.utc)


def test_matches_at_the_configured_local_hour():
    tz = "America/New_York"
    local_dt = datetime(2026, 8, 5, 9, 0, tzinfo=ZoneInfo(tz))  # a Wednesday
    now_utc = local_dt.astimezone(timezone.utc)
    assert is_request_due(tz, local_dt.weekday(), "09:00", now_utc) is True


def test_does_not_match_wrong_hour():
    tz = "America/New_York"
    local_dt = datetime(2026, 8, 5, 9, 0, tzinfo=ZoneInfo(tz))
    now_utc = local_dt.astimezone(timezone.utc) + timedelta(hours=2)
    assert is_request_due(tz, local_dt.weekday(), "09:00", now_utc) is False


def test_does_not_match_wrong_day():
    tz = "America/New_York"
    local_dt = datetime(2026, 8, 5, 9, 0, tzinfo=ZoneInfo(tz))  # Wednesday
    now_utc = local_dt.astimezone(timezone.utc)
    wrong_day = (local_dt.weekday() + 1) % 7
    assert is_request_due(tz, wrong_day, "09:00", now_utc) is False


def test_timezone_conversion_crosses_utc_day_boundary():
    # 9pm in Los Angeles is after midnight UTC (next calendar day) — the business's
    # LOCAL day/hour must be what's matched, not the UTC one.
    tz = "America/Los_Angeles"
    local_dt = datetime(2026, 8, 5, 21, 0, tzinfo=ZoneInfo(tz))  # Wednesday 9pm local
    now_utc = local_dt.astimezone(timezone.utc)
    assert now_utc.date() != local_dt.date(), "test setup should actually cross a UTC day boundary"
    assert is_request_due(tz, local_dt.weekday(), "21:00", now_utc) is True


def test_minute_offset_within_same_hour_still_matches():
    # The scheduler ticks hourly, not on the exact minute — a tick a few minutes
    # into the hour should still count as "the 9am window."
    tz = "America/New_York"
    local_dt = datetime(2026, 8, 5, 9, 17, tzinfo=ZoneInfo(tz))
    now_utc = local_dt.astimezone(timezone.utc)
    assert is_request_due(tz, local_dt.weekday(), "09:00", now_utc) is True


def test_malformed_time_string_returns_false_not_crash():
    tz = "America/New_York"
    now_utc = datetime(2026, 8, 5, 13, 0, tzinfo=timezone.utc)
    assert is_request_due(tz, 2, "not-a-time", now_utc) is False
