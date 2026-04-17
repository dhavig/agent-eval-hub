from __future__ import annotations

import pytest

from adapters.base import Adapter, AgentResponse
from runner.agent_loop import RunTrace
from runner.run_suite import build_graders


class StubJudge(Adapter):
    provider = "stub"

    def __init__(self, payload: str):
        super().__init__(model="stub-judge")
        self._payload = payload

    def complete(self, system, messages, tools=None, temperature=0.0):  # noqa: ARG002
        return AgentResponse(text=self._payload, input_tokens=0, output_tokens=0)


def _trace(text: str = "") -> RunTrace:
    return RunTrace(task_id="t", provider="p", model="m", final_text=text)


def test_llm_judge_passes_when_payload_scores_high():
    judge = StubJudge('{"score": 5, "passed": true, "reason": "good"}')
    graders = build_graders(judge)
    result = graders["llm_judge"](_trace("answer"), {"rubric": "any"}, "prompt")
    assert result.passed
    assert result.score == 5


def test_llm_judge_fails_on_low_score():
    judge = StubJudge('{"score": 1, "passed": false, "reason": "bad"}')
    graders = build_graders(judge)
    result = graders["llm_judge"](_trace("answer"), {"rubric": "any"}, "prompt")
    assert not result.passed
    assert result.score == 1


def test_llm_judge_tolerates_prose_wrapped_json():
    judge = StubJudge('Here is the evaluation:\n```json\n{"score": 4, "passed": true, "reason": "ok"}\n```\nThanks!')
    graders = build_graders(judge)
    result = graders["llm_judge"](_trace("answer"), {"rubric": "any"}, "prompt")
    assert result.passed


def test_llm_judge_raises_without_judge_adapter():
    graders = build_graders(judge=None)
    with pytest.raises(RuntimeError, match="no judge provided"):
        graders["llm_judge"](_trace("answer"), {"rubric": "any"}, "prompt")


def test_deterministic_graders_still_work_without_judge():
    graders = build_graders(judge=None)
    result = graders["contains_all"](_trace("hello world"), {"phrases": ["hello"]}, "prompt")
    assert result.passed
