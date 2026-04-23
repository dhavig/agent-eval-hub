from __future__ import annotations

from pathlib import Path

from agent_eval_hub.adapters.base import ToolCall
from agent_eval_hub.graders.deterministic import GradeResult
from agent_eval_hub.runner.agent_loop import RunTrace
from agent_eval_hub.runner.scorer import SuiteReport, TaskScore
from agent_eval_hub.storage.duckdb import connect, find_regressions, load_run_history, record_run


def _report(suite: str, provider: str, model: str, task_outcomes: dict[str, bool]) -> SuiteReport:
    scores = []
    for task_id, passed in task_outcomes.items():
        trace = RunTrace(
            task_id=task_id,
            provider=provider,
            model=model,
            final_text="ok",
            tool_calls=[ToolCall(name="noop", arguments={})],
            steps=1,
            input_tokens=10,
            output_tokens=5,
            latency_s=0.1,
        )
        scores.append(
            TaskScore(
                task_id=task_id,
                provider=provider,
                model=model,
                passed=passed,
                grades=[GradeResult(name="dummy", passed=passed, detail="test")],
                trace=trace,
            )
        )
    return SuiteReport(suite=suite, scores=scores)


def test_record_run_and_load_history(tmp_path: Path):
    con = connect(tmp_path / "runs.duckdb")
    report = _report("tool_use", "claude", "claude-sonnet-4-6", {"t1": True, "t2": True})
    run_id = record_run(con, report, git_sha="abc123")
    assert run_id

    history = load_run_history(con)
    assert len(history) == 1
    assert history[0]["suite"] == "tool_use"
    assert history[0]["git_sha"] == "abc123"
    assert history[0]["pass_rate"] == 1.0


def test_find_regressions_detects_pass_to_fail(tmp_path: Path):
    con = connect(tmp_path / "runs.duckdb")
    # First run: both pass.
    record_run(con, _report("red_team", "claude", "claude-sonnet-4-6", {"a": True, "b": True}))
    # Second run: task 'b' regresses.
    record_run(con, _report("red_team", "claude", "claude-sonnet-4-6", {"a": True, "b": False}))

    regs = find_regressions(con, "red_team", "claude")
    assert len(regs) == 1
    assert regs[0]["task_id"] == "b"


def test_no_regressions_when_only_one_run(tmp_path: Path):
    con = connect(tmp_path / "runs.duckdb")
    record_run(con, _report("red_team", "claude", "claude-sonnet-4-6", {"a": False}))
    assert find_regressions(con, "red_team", "claude") == []


def test_regressions_ignore_new_failures(tmp_path: Path):
    """A task that was failing AND keeps failing is not a regression."""
    con = connect(tmp_path / "runs.duckdb")
    record_run(con, _report("red_team", "claude", "claude-sonnet-4-6", {"a": False, "b": True}))
    record_run(con, _report("red_team", "claude", "claude-sonnet-4-6", {"a": False, "b": False}))
    regs = find_regressions(con, "red_team", "claude")
    assert [r["task_id"] for r in regs] == ["b"]
