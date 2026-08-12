"""Shared phone number normalization — used both when a manager enters an
employee's number and when matching an inbound Twilio webhook's `From` field,
so the two paths can never silently diverge and fail to match.

Uses is_possible_number (structurally phone-shaped) rather than is_valid_number
(actually assigned per carrier data) — the latter rejects legitimate edge cases
like VOIP numbers and, notably, the 555-XXXX test range, and Twilio itself is
the real authority on whether a number can send/receive SMS, not this check.
"""
import phonenumbers


def normalize_phone_number(raw: str) -> str:
    """Normalize to E.164 (e.g. '+15551234567'). Raises ValueError if unparseable."""
    try:
        parsed = phonenumbers.parse(raw, "US")
    except phonenumbers.NumberParseException as e:
        raise ValueError(f"Invalid phone number: {raw!r}") from e
    if not phonenumbers.is_possible_number(parsed):
        raise ValueError(f"Invalid phone number: {raw!r}")
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
