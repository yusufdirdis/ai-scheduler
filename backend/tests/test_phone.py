import pytest

from services.phone import normalize_phone_number


def test_already_e164_passthrough():
    assert normalize_phone_number("+15559876543") == "+15559876543"


def test_normalizes_common_us_formats_to_same_e164():
    variants = ["(555) 987-6543", "555-987-6543", "555.987.6543", "5559876543", "1-555-987-6543"]
    for v in variants:
        assert normalize_phone_number(v) == "+15559876543"


def test_accepts_555_test_range_numbers():
    # is_valid_number() would reject these (not carrier-assigned); is_possible_number()
    # correctly accepts them, which matters for demo/test data and matches what
    # the inbound webhook does when matching Twilio's From field.
    assert normalize_phone_number("+15559876543") == "+15559876543"


def test_rejects_garbage_input():
    with pytest.raises(ValueError):
        normalize_phone_number("not a phone number")


def test_rejects_too_short_number():
    with pytest.raises(ValueError):
        normalize_phone_number("123")
