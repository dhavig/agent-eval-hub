from __future__ import annotations

import json
import uuid
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb

from runner.scorer import SuiteReport

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id        VARCHAR PRIMARY KEY,
    ts            TIMESTAMP NOT NULL,
    suite         VARCHAR   NOT NULL,
    provider      VARCHAR   NOT NULL,
    model         VARCHAR   NOT NULL,
    git_sha       VARCHAR,
    pass_rate     DOUBLE    NOT NULL,
    input_tokens  BIGINT    NOT NULL,
    output_tokens BIGINT    NOT NULL
);

CREATE TABLE IF NOT EXISTS task_results (
    run_id        VARCHAR NOT NULL,
    task_id       VARCHAR NOT NULL,
    passed        BOOLEAN NOT NULL,
    steps         INTEGER,
    latency_s     DOUBLE,
    input_tokens  BIGINT,
    output_tokens BIGINT,
    error         VARCHAR,
    grades_json   VARCHAR,
    PRIMARY KEY (run_id, task_id)
);

CREATE TABLE IF NOT EXISTS divergences (
    ts          TIMESTAMP NOT NULL,
    suite       VARCHAR   NOT NULL,
    task_id     VARCHAR   NOT NULL,
    surface_a   VARCHAR   NOT NULL,
    surface_b   VARCHAR   NOT NULL,
    similarity  DOUBLE    NOT NULL,
    answer_a    VARCHAR,
    answer_b    VARCHAR
);
"""


def connect(db_path: str | Path) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(str(db_path))
    con.execute(SCHEMA)
    return con


def _grade_to_dict(g: Any) -> dict[str, Any]:
    return asdict(g) if is_dataclass(g) else {"name": "unknown", "passed": False}


def record_run(
    con: duckdb.DuckDBPyConnection,
    report: SuiteReport,
    git_sha: str | None = None,
) -> str:
    if not report.scores:
        raise ValueError("Cannot record empty report")

    run_id = str(uuid.uuid4())
    ts = datetime.now(timezone.utc)
    first = report.scores[0]

    con.execute(
        "INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            run_id,
            ts,
            report.suite,
            first.provider,
            first.model,
            git_sha,
            report.pass_rate,
            report.total_input_tokens,
            report.total_output_tokens,
        ],
    )

    for s in report.scores:
        trace = s.trace
        con.execute(
            "INSERT INTO task_results VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                run_id,
                s.task_id,
                s.passed,
                trace.steps if trace else None,
                trace.latency_s if trace else None,
                trace.input_tokens if trace else None,
                trace.output_tokens if trace else None,
                trace.error if trace else None,
                json.dumps([_grade_to_dict(g) for g in s.grades]),
            ],
        )
    return run_id


def load_run_history(
    con: duckdb.DuckDBPyConnection,
    suite: str | None = None,
    provider: str | None = None,
) -> list[dict[str, Any]]:
    query = "SELECT run_id, ts, suite, provider, model, git_sha, pass_rate, input_tokens, output_tokens FROM runs WHERE 1=1"
    args: list[Any] = []
    if suite:
        query += " AND suite = ?"
        args.append(suite)
    if provider:
        query += " AND provider = ?"
        args.append(provider)
    query += " ORDER BY ts ASC"
    return [dict(zip([c[0] for c in con.description], row)) for row in con.execute(query, args).fetchall()]


def record_divergences(
    con: duckdb.DuckDBPyConnection,
    suite: str,
    divergences: list[dict[str, Any]],
) -> int:
    ts = datetime.now(timezone.utc)
    for d in divergences:
        con.execute(
            "INSERT INTO divergences VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ts,
                suite,
                d["task_id"],
                d["surface_a"],
                d["surface_b"],
                float(d["similarity"]),
                d.get("answer_a", ""),
                d.get("answer_b", ""),
            ],
        )
    return len(divergences)


def load_divergences(
    con: duckdb.DuckDBPyConnection,
    suite: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    query = "SELECT ts, suite, task_id, surface_a, surface_b, similarity, answer_a, answer_b FROM divergences WHERE 1=1"
    args: list[Any] = []
    if suite:
        query += " AND suite = ?"
        args.append(suite)
    query += " ORDER BY ts DESC LIMIT ?"
    args.append(limit)
    return [dict(zip([c[0] for c in con.description], row)) for row in con.execute(query, args).fetchall()]


def find_regressions(
    con: duckdb.DuckDBPyConnection,
    suite: str,
    provider: str,
) -> list[dict[str, Any]]:
    """Return tasks that passed in the previous run of this suite+provider but fail in the latest."""
    runs = con.execute(
        "SELECT run_id FROM runs WHERE suite = ? AND provider = ? ORDER BY ts DESC LIMIT 2",
        [suite, provider],
    ).fetchall()
    if len(runs) < 2:
        return []
    latest_id, prev_id = runs[0][0], runs[1][0]

    rows = con.execute(
        """
        SELECT curr.task_id, prev.passed AS prev_passed, curr.passed AS curr_passed
        FROM task_results curr
        JOIN task_results prev
          ON prev.task_id = curr.task_id
        WHERE curr.run_id = ? AND prev.run_id = ?
          AND prev.passed = TRUE AND curr.passed = FALSE
        """,
        [latest_id, prev_id],
    ).fetchall()
    return [{"task_id": r[0], "prev_passed": r[1], "curr_passed": r[2]} for r in rows]
