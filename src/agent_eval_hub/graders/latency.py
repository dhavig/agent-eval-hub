"""Latency graders — essential for device surfaces where hard deadlines matter."""
from __future__ import annotations

from agent_eval_hub.graders.deterministic import GradeResult
from agent_eval_hub.runner.agent_loop import RunTrace


def latency_under(trace: RunTrace, seconds: float) -> GradeResult:
    """Pass when the task completed in under `seconds` wall time.

    Reliability on-device ≠ reliability in cloud — phones have hard latency
    budgets. Usable from YAML as:
        - type: latency_under
          seconds: 2.0
    """
    observed = trace.latency_s
    return GradeResult(
        name="latency_under",
        passed=observed < seconds,
        detail=f"observed={observed:.2f}s, budget={seconds:.2f}s",
    )


def token_budget(trace: RunTrace, max_output_tokens: int) -> GradeResult:
    """Pass when output tokens stay under budget.

    Silent cost regressions live here: answers get longer without getting
    better. Usable from YAML as:
        - type: token_budget
          max_output_tokens: 400
    """
    observed = trace.output_tokens
    return GradeResult(
        name="token_budget",
        passed=observed <= max_output_tokens,
        detail=f"output_tokens={observed}, budget={max_output_tokens}",
    )
