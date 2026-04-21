"""Seed a DuckDB file with synthetic run history so the dashboard has something to show.

Usage:
    python -m agent_eval_hub.dashboard.seed_demo --db demo.duckdb
    streamlit run src/agent_eval_hub/dashboard/app.py -- --db demo.duckdb
"""
from __future__ import annotations

import argparse
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from agent_eval_hub.adapters.base import ToolCall
from agent_eval_hub.graders.deterministic import GradeResult
from agent_eval_hub.runner.agent_loop import RunTrace
from agent_eval_hub.runner.scorer import SuiteReport, TaskScore
from agent_eval_hub.storage.duckdb_store import connect, record_run

SUITES = {
    "tool_use": ["weather_paris", "order_lookup", "refusal_no_tool"],
    "red_team": [
        "indirect_injection_via_web_fetch",
        "system_prompt_leak",
        "exfiltration_via_email",
        "goal_hijack_via_tool_result",
        "harmful_request_refusal",
    ],
}

PROVIDERS = [
    ("claude", "claude-sonnet-4-6"),
    ("openai", "gpt-4o-mini"),
    ("gemini", "gemini-2.5-pro"),
    ("ollama", "llama3.1"),
]


def _stable_passed(suite: str, provider: str, task_id: str) -> bool:
    """Deterministic per-cell pass/fail so only the seeded drift shows as a regression."""
    rng = random.Random(f"{suite}-{provider}-{task_id}")
    threshold = 0.95 if provider in ("claude", "openai") else 0.80
    return rng.random() < threshold


def fake_report(suite: str, provider: str, model: str, week: int, is_latest: bool) -> SuiteReport:
    """Build a fake SuiteReport. Injects a regression only on the LATEST week for
    (openai, red_team, indirect_injection_via_web_fetch) so find_regressions fires."""
    rng = random.Random(f"{suite}-{provider}-{week}")
    scores: list[TaskScore] = []
    for task_id in SUITES[suite]:
        # Silent-drift simulation: previously passing, now failing, only on the newest run.
        if (
            is_latest
            and provider == "openai"
            and suite == "red_team"
            and task_id == "indirect_injection_via_web_fetch"
        ):
            passed = False
        else:
            passed = _stable_passed(suite, provider, task_id)
        scores.append(
            TaskScore(
                task_id=task_id,
                provider=provider,
                model=model,
                passed=passed,
                grades=[GradeResult(name="demo", passed=passed, detail="seeded")],
                trace=RunTrace(
                    task_id=task_id,
                    provider=provider,
                    model=model,
                    final_text="seeded output",
                    tool_calls=[ToolCall(name="demo", arguments={})],
                    steps=rng.randint(1, 3),
                    input_tokens=rng.randint(200, 800),
                    output_tokens=rng.randint(50, 300),
                    latency_s=rng.uniform(0.5, 3.0),
                ),
            )
        )
    return SuiteReport(suite=suite, scores=scores)


def seed(db_path: Path, weeks: int = 8) -> None:
    con = connect(db_path)
    con.execute("DELETE FROM task_results")
    con.execute("DELETE FROM runs")
    base = datetime.now(timezone.utc) - timedelta(weeks=weeks)
    for week in range(weeks):
        for suite in SUITES:
            for provider, model in PROVIDERS:
                report = fake_report(suite, provider, model, week=week, is_latest=(week == weeks - 1))
                ts = base + timedelta(weeks=week)
                # Override timestamp by inserting directly after record_run to keep
                # it realistic; simplest: use record_run which uses now() then rewrite.
                run_id = record_run(con, report, git_sha=f"week-{week:02d}-sha")
                con.execute("UPDATE runs SET ts = ? WHERE run_id = ?", [ts, run_id])
    con.close()
    print(f"seeded {weeks} weeks x {len(SUITES)} suites x {len(PROVIDERS)} providers into {db_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path("demo.duckdb"))
    parser.add_argument("--weeks", type=int, default=8)
    args = parser.parse_args()
    seed(args.db, args.weeks)


if __name__ == "__main__":
    main()
