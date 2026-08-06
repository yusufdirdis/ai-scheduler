"""LLM soft-preference layer. Operates ONLY on a pre-vetted candidate list per slot
(baseline assignee + locally-feasible alternates) — it is structurally impossible for
this step to pick an ineligible employee, and its output is re-validated globally
afterward (validator.py) before anything is persisted."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from services.ai_client import AIClient

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You assign one employee to a work shift from a short list of already-eligible candidates.
Weigh: skill ratings relevant to this shift, reliability history, and manager notes.
The first candidate listed is the current baseline pick — only choose someone else if they are a clearly
better fit; ties go to the baseline.
Respond with ONLY a single valid JSON object, no other text: {"employee_id": <int>, "rationale": "<one sentence>"}
The employee_id MUST be one of the candidate ids given to you."""


@dataclass(frozen=True)
class CandidateInfo:
    employee_id: int
    full_name: str
    skill_ratings: dict[str, int] = field(default_factory=dict)  # skill name -> 1-5
    reliability_score: float | None = None
    manager_notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class RankingJob:
    slot_id: int
    role_name: str
    date: str
    start_time: str
    end_time: str
    candidates: tuple[CandidateInfo, ...]  # candidates[0] is always the solver baseline


@dataclass
class RankingOutcome:
    employee_id: int
    rationale: str


def _candidate_to_dict(c: CandidateInfo) -> dict:
    return {
        "employee_id": c.employee_id,
        "name": c.full_name,
        "skill_ratings": c.skill_ratings,
        "reliability_score": c.reliability_score,
        "manager_notes": list(c.manager_notes),
    }


def rank_slot(ai_client: AIClient, job: RankingJob) -> RankingOutcome:
    baseline = job.candidates[0]
    if len(job.candidates) <= 1:
        return RankingOutcome(employee_id=baseline.employee_id, rationale="Only eligible candidate.")

    user_payload = {
        "shift": {"role": job.role_name, "date": job.date, "start_time": job.start_time, "end_time": job.end_time},
        "candidates": [_candidate_to_dict(c) for c in job.candidates],
    }

    try:
        raw = ai_client.chat_json(SYSTEM_PROMPT, json.dumps(user_payload))
        parsed = json.loads(raw)
        chosen_id = int(parsed["employee_id"])
        rationale = str(parsed.get("rationale", "")).strip() or "No rationale given."
    except Exception as e:
        logger.warning("Ranker LLM call failed for slot %s, keeping baseline: %s", job.slot_id, e)
        return RankingOutcome(employee_id=baseline.employee_id, rationale=f"AI ranking unavailable ({e}); kept solver baseline.")

    valid_ids = {c.employee_id for c in job.candidates}
    if chosen_id not in valid_ids:
        logger.warning("Ranker returned invalid employee_id %s for slot %s, keeping baseline", chosen_id, job.slot_id)
        return RankingOutcome(
            employee_id=baseline.employee_id, rationale="AI returned an invalid candidate; kept solver baseline."
        )

    return RankingOutcome(employee_id=chosen_id, rationale=rationale)


def rank_schedule(ai_client: AIClient, jobs: list[RankingJob]) -> dict[int, RankingOutcome]:
    return {job.slot_id: rank_slot(ai_client, job) for job in jobs}
