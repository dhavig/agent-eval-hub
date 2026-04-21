from __future__ import annotations

import json
import uuid
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb

from agent_eval_hub.runner.scorer import SuiteReport
from agent_eval_hub.storage.base import Store

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id         VARCHAR PRIMARY KEY,
    ts             TIMESTAMP NOT NULL,
    suite          VARCHAR   NOT NULL,
    suite_version  INTEGER,
    provider       VARCHAR   NOT NULL,
    model          VARCHAR   NOT NULL,
    git_sha        VARCHAR,
    pass_rate      DOUBLE    NOT NULL,
    input_tokens   BIGINT    NOT NULL,
    output_tokens  BIGINT    NOT NULL,
    total_cost_usd DOUBLE
);

CREATE TABLE IF NOT EXISTS task_results (
    run_id        VARCHAR NOT NULL,
    task_id       VARCHAR NOT NULL,
    passed        BOOLEAN NOT NULL,
    steps         INTEGER,
    latency_s     DOUBLE,
    input_tokens  BIGINT,
    output_tokens BIGINT,
    cost_usd      DOUBLE,
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

CREATE TABLE IF NOT EXISTS human_review_queue (
    ts         TIMESTAMP NOT NULL,
    suite      VARCHAR,
    task_id    VARCHAR,
    task_prompt VARCHAR,
    agent_answer VARCHAR,
    rubric     VARCHAR,
    reason     VARCHAR,
    resolved   BOOLEAN DEFAULT FALSE,
    human_passed BOOLEAN,
    human_note VARCHAR
);
"""


def _ensure_column(con: duckdb.DuckDBPyConnection, table: str, col: str, decl: str) -> None:
    """Add a column if missing — so new DuckDB schemas pick up older DB files
    from previous versions without a migration tool."""
    existing = {row[1] for row in con.execute(f"PRAGMA table_info('{table}')").fetchall()}
    if col not in existing:
        con.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")


def connect(db_path: str | Path) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(str(db_path))
    con.execute(SCHEMA)
    # Soft migrations for DBs created before 0.3.0:
    _ensure_column(con, "runs", "suite_version", "INTEGER")
    _ensure_column(con, "runs", "total_cost_usd", "DOUBLE")
    _ensure_column(con, "task_results", "cost_usd", "DOUBLE")
    return con


def _grade_to_dict(g: Any) -> dict[str, Any]:
    return asdict(g) if is_dataclass(g) else {"name": "unknown", "passed": False}


def record_run(
    con: duckdb.DuckDBPyConnection,
    report: SuiteReport,
    git_sha: str | None = None,
    suite_version: int | None = None,
) -> str:
    if not report.scores:
        raise ValueError("Cannot record empty report")

    run_id = str(uuid.uuid4())
    ts = datetime.now(timezone.utc)
    first = report.scores[0]

    con.execute(
        """INSERT INTO runs
           (run_id, ts, suite, suite_version, provider, model, git_sha,
            pass_rate, input_tokens, output_tokens, total_cost_usd)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            run_id,
            ts,
            report.suite,
            suite_version,
            first.provider,
            first.model,
            git_sha,
            report.pass_rate,
            report.total_input_tokens,
            report.total_output_tokens,
            report.total_cost_usd,
        ],
    )

    for s in report.scores:
        trace = s.trace
        con.execute(
            """INSERT INTO task_results
               (run_id, task_id, passed, steps, latency_s, input_tokens,
                output_tokens, cost_usd, error, grades_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                run_id,
                s.task_id,
                s.passed,
                trace.steps if trace else None,
                trace.latency_s if trace else None,
                trace.input_tokens if trace else None,
                trace.output_tokens if trace else None,
                s.cost_usd,
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
    query = (
        "SELECT run_id, ts, suite, suite_version, provider, model, git_sha, "
        "pass_rate, input_tokens, output_tokens, total_cost_usd "
        "FROM runs WHERE 1=1"
    )
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
    """Tasks that passed last run but fail in the latest."""
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


def find_token_regressions(
    con: duckdb.DuckDBPyConnection,
    suite: str,
    provider: str,
    min_ratio: float = 1.3,
) -> list[dict[str, Any]]:
    """Semantic drift: tasks that STILL PASS but use >= min_ratio more tokens
    than the previous run. Silent cost regression — the pass/fail signal hides it."""
    runs = con.execute(
        "SELECT run_id FROM runs WHERE suite = ? AND provider = ? ORDER BY ts DESC LIMIT 2",
        [suite, provider],
    ).fetchall()
    if len(runs) < 2:
        return []
    latest_id, prev_id = runs[0][0], runs[1][0]

    rows = con.execute(
        """
        SELECT curr.task_id,
               prev.output_tokens AS prev_tokens,
               curr.output_tokens AS curr_tokens,
               CAST(curr.output_tokens AS DOUBLE) / NULLIF(prev.output_tokens, 0) AS ratio
        FROM task_results curr
        JOIN task_results prev ON prev.task_id = curr.task_id
        WHERE curr.run_id = ? AND prev.run_id = ?
          AND prev.passed = TRUE AND curr.passed = TRUE
          AND prev.output_tokens > 0
          AND CAST(curr.output_tokens AS DOUBLE) / prev.output_tokens >= ?
        """,
        [latest_id, prev_id, min_ratio],
    ).fetchall()
    return [{"task_id": r[0], "prev_tokens": r[1], "curr_tokens": r[2], "ratio": r[3]} for r in rows]


def enqueue_human_review(
    con: duckdb.DuckDBPyConnection,
    suite: str,
    task_id: str,
    task_prompt: str,
    agent_answer: str,
    rubric: str,
    reason: str,
) -> None:
    con.execute(
        """INSERT INTO human_review_queue
           (ts, suite, task_id, task_prompt, agent_answer, rubric, reason, resolved)
           VALUES (?, ?, ?, ?, ?, ?, ?, FALSE)""",
        [datetime.now(timezone.utc), suite, task_id, task_prompt, agent_answer, rubric, reason],
    )


def load_human_review_queue(
    con: duckdb.DuckDBPyConnection,
    pending_only: bool = True,
    limit: int = 50,
) -> list[dict[str, Any]]:
    query = "SELECT ts, suite, task_id, task_prompt, agent_answer, rubric, reason, resolved, human_passed, human_note FROM human_review_queue"
    if pending_only:
        query += " WHERE resolved = FALSE"
    query += " ORDER BY ts ASC LIMIT ?"
    return [dict(zip([c[0] for c in con.description], row)) for row in con.execute(query, [limit]).fetchall()]


class DuckDBStore(Store):
    """`Store` facade over the module-level functions. Lets callers depend on
    the abstract `Store` type; the Postgres backend implements the same surface."""

    def __init__(self, path: str | Path):
        self.con = connect(path)

    def record_run(self, report, git_sha=None, suite_version=None):
        return record_run(self.con, report, git_sha=git_sha, suite_version=suite_version)

    def record_divergences(self, suite, divergences):
        return record_divergences(self.con, suite, divergences)

    def load_run_history(self, suite=None, provider=None):
        return load_run_history(self.con, suite=suite, provider=provider)

    def load_divergences(self, suite=None, limit=100):
        return load_divergences(self.con, suite=suite, limit=limit)

    def find_regressions(self, suite, provider):
        return find_regressions(self.con, suite, provider)

    def find_token_regressions(self, suite, provider, min_ratio=1.3):
        return find_token_regressions(self.con, suite, provider, min_ratio=min_ratio)

    def close(self):
        self.con.close()
