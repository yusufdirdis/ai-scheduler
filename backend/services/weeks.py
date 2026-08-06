from datetime import date, timedelta


def week_start_on_or_before(reference: date, week_start_day: int) -> date:
    """Most recent date <= reference whose weekday matches week_start_day.

    `date.weekday()` and our `week_start_day` column both use 0=Monday..6=Sunday,
    so no conversion is needed.
    """
    delta = (reference.weekday() - week_start_day) % 7
    return reference - timedelta(days=delta)


def is_valid_week_start(candidate: date, week_start_day: int) -> bool:
    return candidate.weekday() == week_start_day
