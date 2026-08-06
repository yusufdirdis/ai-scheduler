import json

from services.scheduling.ranker import CandidateInfo, RankingJob, rank_slot


class FakeAIClient:
    def __init__(self, response: str | None = None, raise_error: Exception | None = None):
        self.response = response
        self.raise_error = raise_error
        self.calls = 0

    def chat_json(self, system_prompt: str, user_text: str) -> str:
        self.calls += 1
        if self.raise_error:
            raise self.raise_error
        return self.response


def make_job(candidates):
    return RankingJob(slot_id=1, role_name="Cook", date="2026-08-03", start_time="09:00", end_time="17:00", candidates=tuple(candidates))


def test_single_candidate_skips_llm_call_entirely():
    baseline = CandidateInfo(employee_id=1, full_name="Alex")
    job = make_job([baseline])
    ai = FakeAIClient(response="should never be read")
    outcome = rank_slot(ai, job)
    assert outcome.employee_id == 1
    assert ai.calls == 0


def test_llm_picks_a_valid_alternate_candidate():
    baseline = CandidateInfo(employee_id=1, full_name="Alex", reliability_score=0.5)
    alt = CandidateInfo(employee_id=2, full_name="Jordan", reliability_score=0.95)
    job = make_job([baseline, alt])
    ai = FakeAIClient(response=json.dumps({"employee_id": 2, "rationale": "More reliable."}))
    outcome = rank_slot(ai, job)
    assert outcome.employee_id == 2
    assert outcome.rationale == "More reliable."


def test_llm_returning_ineligible_employee_id_falls_back_to_baseline():
    baseline = CandidateInfo(employee_id=1, full_name="Alex")
    alt = CandidateInfo(employee_id=2, full_name="Jordan")
    job = make_job([baseline, alt])
    ai = FakeAIClient(response=json.dumps({"employee_id": 999, "rationale": "Hallucinated pick."}))
    outcome = rank_slot(ai, job)
    assert outcome.employee_id == 1, "an out-of-candidate-list pick must never be trusted"


def test_llm_returning_malformed_json_falls_back_to_baseline():
    baseline = CandidateInfo(employee_id=1, full_name="Alex")
    alt = CandidateInfo(employee_id=2, full_name="Jordan")
    job = make_job([baseline, alt])
    ai = FakeAIClient(response="not json at all")
    outcome = rank_slot(ai, job)
    assert outcome.employee_id == 1


def test_llm_raising_falls_back_to_baseline_without_crashing():
    baseline = CandidateInfo(employee_id=1, full_name="Alex")
    alt = CandidateInfo(employee_id=2, full_name="Jordan")
    job = make_job([baseline, alt])
    ai = FakeAIClient(raise_error=RuntimeError("no API key"))
    outcome = rank_slot(ai, job)
    assert outcome.employee_id == 1
