import json
from datetime import date

from services.availability_parser import parse_availability_reply

MONDAY = date(2026, 8, 3)  # week: 2026-08-03 .. 2026-08-09


class FakeAIClient:
    def __init__(self, response: str | None = None, raise_error: Exception | None = None):
        self.response = response
        self.raise_error = raise_error

    def chat_json(self, system_prompt: str, user_text: str) -> str:
        if self.raise_error:
            raise self.raise_error
        return self.response


def test_parses_clear_availability_message():
    ai = FakeAIClient(
        response=json.dumps(
            {
                "slots": [
                    {"date": "2026-08-04", "start_time": "17:00", "end_time": "22:00"},
                    {"date": "2026-08-05", "start_time": "17:00", "end_time": "22:00"},
                ],
                "confidence": 0.95,
            }
        )
    )
    result = parse_availability_reply(ai, MONDAY, "I can work Tue and Wed evenings 5-10pm")
    assert len(result.slots) == 2
    assert result.confidence == 0.95
    assert result.slots[0].date == date(2026, 8, 4)


def test_drops_hallucinated_out_of_week_date():
    ai = FakeAIClient(
        response=json.dumps(
            {
                "slots": [
                    {"date": "2026-08-04", "start_time": "09:00", "end_time": "17:00"},
                    {"date": "2026-08-20", "start_time": "09:00", "end_time": "17:00"},  # outside the week
                ],
                "confidence": 0.9,
            }
        )
    )
    result = parse_availability_reply(ai, MONDAY, "Tuesday works, also the 20th")
    assert len(result.slots) == 1
    assert result.slots[0].date == date(2026, 8, 4)


def test_drops_slot_with_end_before_start():
    ai = FakeAIClient(
        response=json.dumps(
            {"slots": [{"date": "2026-08-04", "start_time": "17:00", "end_time": "09:00"}], "confidence": 0.8}
        )
    )
    result = parse_availability_reply(ai, MONDAY, "garbled reply")
    assert result.slots == []


def test_ambiguous_message_returns_empty_with_low_confidence():
    ai = FakeAIClient(response=json.dumps({"slots": [], "confidence": 0.2}))
    result = parse_availability_reply(ai, MONDAY, "idk maybe??")
    assert result.slots == []
    assert result.confidence == 0.2


def test_malformed_json_response_falls_back_to_empty():
    ai = FakeAIClient(response="not valid json")
    result = parse_availability_reply(ai, MONDAY, "Tue-Thu evenings")
    assert result.slots == []
    assert result.confidence == 0.0


def test_ai_client_raising_falls_back_to_empty_without_crashing():
    ai = FakeAIClient(raise_error=RuntimeError("no API key"))
    result = parse_availability_reply(ai, MONDAY, "Tue-Thu evenings")
    assert result.slots == []
    assert result.confidence == 0.0


def test_confidence_clamped_to_valid_range():
    ai = FakeAIClient(response=json.dumps({"slots": [], "confidence": 5.0}))
    result = parse_availability_reply(ai, MONDAY, "whatever works")
    assert result.confidence == 1.0


def test_all_day_availability():
    ai = FakeAIClient(
        response=json.dumps(
            {"slots": [{"date": "2026-08-06", "start_time": "00:00", "end_time": "23:59"}], "confidence": 0.9}
        )
    )
    result = parse_availability_reply(ai, MONDAY, "free all day Thursday")
    assert len(result.slots) == 1
    assert result.slots[0].start_time.hour == 0
    assert result.slots[0].end_time.hour == 23
