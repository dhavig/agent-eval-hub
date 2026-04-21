"""Latency + token budget graders."""
from __future__ import annotations

from agent_eval_hub.graders.latency import latency_under, token_budget
from agent_eval_hub.runner.agent_loop import RunTrace


def _trace(latency: float = 0.0, output_tokens: int = 0) -> RunTrace:
    return RunTrace(
        task_id="t", provider="p", model="m", final_text="",
        latency_s=latency, output_tokens=output_tokens,
    )


def test_latency_under_passes_under_budget():
    assert latency_under(_trace(latency=1.5), seconds=2.0).passed


def test_latency_under_fails_at_or_over_budget():
    assert not latency_under(_trace(latency=2.0), seconds=2.0).passed
    assert not latency_under(_trace(latency=5.0), seconds=2.0).passed


def test_token_budget_passes_at_or_under():
    assert token_budget(_trace(output_tokens=300), max_output_tokens=400).passed
    assert token_budget(_trace(output_tokens=400), max_output_tokens=400).passed


def test_token_budget_fails_over():
    r = token_budget(_trace(output_tokens=401), max_output_tokens=400)
    assert not r.passed
    assert "401" in r.detail
