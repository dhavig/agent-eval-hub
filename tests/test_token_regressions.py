"""Silent cost drift: same task, same pass/fail, more tokens."""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest

from agent_eval_hub.adapters.base import ToolCall
from agent_eval_hub.graders.deterministic import GradeResult
from agent_eval_hub.runner.agent_loop import RunTrace
from agent_eval_hub.runner.scorer import SuiteReport, TaskScore
from agent_eval_hub.storage.duckdb import connect, find_token_regressions, record_run


def _make_report(output_tokens: int, passed: bool = True) -> SuiteReport:
    return SuiteReport(
        suite="s",
        scores=[
            TaskScore(
                task_id="t1",
                provider="claude",
                model="claude-sonnet-4-6",
                passed=passed,
                grades=[GradeResult(name="g", passed=passed)],
                trace=RunTrace(
                    task_id="t1",
                    provider="claude",
                    model="claude-sonnet-4-6",
                    final_text="ok",
                    tool_calls=[ToolCall(name="x", arguments={})],
                    input_tokens=100,
                    output_tokens=output_tokens,
                ),
            ),
        ],
    )


def test_token_regression_fires_when_tokens_grow(tmp_path: Path):
    db = tmp_path / "r.duckdb"
    con = connect(db)
    record_run(con, _make_report(output_tokens=100))
    import time; time.sleep(0.01)
    record_run(con, _make_report(output_tokens=200))  # 2x tokens, still passing
    regressions = find_token_regressions(con, suite="s", provider="claude", min_ratio=1.5)
    assert len(regressions) == 1
    assert regressions[0]["task_id"] == "t1"
    assert regressions[0]["ratio"] >= 1.5


def test_token_regression_ignored_when_below_threshold(tmp_path: Path):
    db = tmp_path / "r.duckdb"
    con = connect(db)
    record_run(con, _make_report(output_tokens=100))
    import time; time.sleep(0.01)
    record_run(con, _make_report(output_tokens=110))  # 1.1x — under 1.3x threshold
    regressions = find_token_regressions(con, suite="s", provider="claude")
    assert regressions == []


def test_token_regression_requires_both_passing(tmp_path: Path):
    """If the task failed, that's a regular regression, not a token regression."""
    db = tmp_path / "r.duckdb"
    con = connect(db)
    record_run(con, _make_report(output_tokens=100, passed=True))
    import time; time.sleep(0.01)
    record_run(con, _make_report(output_tokens=500, passed=False))  # failed — out of scope here
    assert find_token_regressions(con, suite="s", provider="claude") == []
