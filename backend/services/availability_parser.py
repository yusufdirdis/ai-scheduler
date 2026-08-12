"""Turns an employee's free-text SMS reply into structured availability windows.
LLM-assisted since replies are natural language ("I can work Tue-Thu evenings,
off Friday"); falls back to zero slots + low confidence on any failure, which
surfaces as AvailabilitySubmission.status='parse_failed' for manager follow-up
rather than silently guessing or crashing the inbound webhook."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date, time, timedelta

from services.ai_client import AIClient

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You parse an employee's free-text SMS reply about their work availability for a
specific week into structured time windows.

Given the week's date range and the employee's message, extract the days and time ranges they say
they ARE available to work. Respond with ONLY a single valid JSON object, no other text:
{"slots": [{"date": "YYYY-MM-DD", "start_time": "HH:MM", "end_time": "HH:MM"}, ...], "confidence": <0.0-1.0>}

Rules:
- Only include days the employee says they ARE available; never include days they're unavailable.
- If a message says "all day" or gives a day with no specific hours, use 00:00 to 23:59 for that day.
- Dates must fall within the given week's date range — resolve day names (e.g. "Tuesday") to the
  matching date in that range.
- If the message is too ambiguous or doesn't describe availability at all, return an empty slots
  list and a confidence below 0.5.
- confidence should reflect how sure you are the extracted slots match what the employee meant.
"""


@dataclass
class ParsedSlot:
    date: date
    start_time: time
    end_time: time


@dataclass
class ParsedAvailability:
    slots: list[ParsedSlot] = field(default_factory=list)
    confidence: float = 0.0


def parse_availability_reply(ai_client: AIClient, week_start_date: date, raw_text: str) -> ParsedAvailability:
    week_end_date = week_start_date + timedelta(days=6)
    user_payload = {
        "week_start_date": week_start_date.isoformat(),
        "week_end_date": week_end_date.isoformat(),
        "message": raw_text,
    }

    try:
        raw = ai_client.chat_json(SYSTEM_PROMPT, json.dumps(user_payload))
        parsed = json.loads(raw)
    except Exception as e:
        logger.warning("Availability parse failed (AI call/JSON error), returning empty: %s", e)
        return ParsedAvailability(slots=[], confidence=0.0)

    slots: list[ParsedSlot] = []
    for raw_slot in parsed.get("slots", []):
        try:
            slot_date = date.fromisoformat(raw_slot["date"])
            start_time = time.fromisoformat(raw_slot["start_time"])
            end_time = time.fromisoformat(raw_slot["end_time"])
        except (KeyError, ValueError):
            continue
        if not (week_start_date <= slot_date <= week_end_date):
            continue  # drop hallucinated out-of-week dates rather than trust them
        if end_time <= start_time:
            continue
        slots.append(ParsedSlot(date=slot_date, start_time=start_time, end_time=end_time))

    try:
        confidence = float(parsed.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))

    return ParsedAvailability(slots=slots, confidence=confidence)
