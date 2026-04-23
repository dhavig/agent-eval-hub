"""Postgres backend — skeleton for production deployments.

Status: **skeleton**. Implements the `Store` ABC surface but needs a running
Postgres + psycopg installed. Enables the README's promised escape from the
7-day `actions/cache` eviction limit without claiming it's production-ready.

Wire up:
    pip install agent-eval-hub[postgres]
    export AGENT_EVAL_DB_URL=postgresql://user:pass@host/db
    agent-eval --db postgres --suite ...
"""
from __future__ import annotations

import json
import uuid
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any

from agent_eval_hub.storage.base import Store

SCHEMA_STATEMENTS = [
    """CREATE TABLE IF NOT EXISTS runs (
        run_id         TEXT PRIMARY KEY,
        ts             TIMESTAMPTZ NOT NULL,
        suite          TEXT NOT NULL,
        suite_version  INTEGER,
        provider       TEXT NOT NULL,
        model          TEXT NOT NULL,
        git_sha        TEXT,
        pass_rate      DOUBLE PRECISION NOT NULL,
        input_tokens   BIGINT NOT NULL,
        output_tokens  BIGINT NOT NULL,
        total_cost_usd DOUBLE PRECISION
    )""",
    """CREATE TABLE IF NOT EXISTS task_results (
        run_id        TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
        task_id       TEXT NOT NULL,
        passed        BOOLEAN NOT NULL,
        steps         INTEGER,
        latency_s     DOUBLE PRECISION,
        input_tokens  BIGINT,
        output_tokens BIGINT,
        cost_usd      DOUBLE PRECISION,
        error         TEXT,
        grades_json   TEXT,
        PRIMARY KEY (run_id, task_id)
    )""",
    """CREATE TABLE IF NOT EXISTS divergences (
        ts         TIMESTAMPTZ NOT NULL,
        suite      TEXT NOT NULL,
        task_id    TEXT NOT NULL,
        surface_a  TEXT NOT NULL,
        surface_b  TEXT NOT NULL,
        similarity DOUBLE PRECISION NOT NULL,
        answer_a   TEXT,
        answer_b   TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS runs_suite_provider_ts ON runs(suite, provider, ts DESC)",
]


class PostgresStore(Store):
    """Requires `psycopg[binary]`. Import is deferred so users without Postgres
    aren't forced to install it."""

    def __init__(self, dsn: str):
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError(
                "psycopg not installed. `pip install agent-eval-hub[postgres]`"
            ) from exc
        self.conn = psycopg.connect(dsn, autocommit=True)
        with self.conn.cursor() as cur:
            for stmt in SCHEMA_STATEMENTS:
                cur.execute(stmt)

    # --- write ---

    def record_run(self, report, git_sha=None, suite_version=None) -> str:
        if not report.scores:
            raise ValueError("Cannot record empty report")
        run_id = str(uuid.uuid4())
        ts = datetime.now(timezone.utc)
        first = report.scores[0]
        with self.conn.cursor() as cur:
            cur.execute(
                """INSERT INTO runs VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    run_id, ts, report.suite, suite_version,
                    first.provider, first.model, git_sha,
                    report.pass_rate, report.total_input_tokens,
                    report.total_output_tokens, report.total_cost_usd,
                ),
            )
            for s in report.scores:
                tr = s.trace
                cur.execute(
                    """INSERT INTO task_results VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        run_id, s.task_id, s.passed,
                        tr.steps if tr else None,
                        tr.latency_s if tr else None,
                        tr.input_tokens if tr else None,
                        tr.output_tokens if tr else None,
                        s.cost_usd,
                        tr.error if tr else None,
                        json.dumps([asdict(g) if is_dataclass(g) else {"name": "?"} for g in s.grades]),
                    ),
                )
        return run_id

    def record_divergences(self, suite: str, divergences: list[dict[str, Any]]) -> int:
        ts = datetime.now(timezone.utc)
        with self.conn.cursor() as cur:
            for d in divergences:
                cur.execute(
                    "INSERT INTO divergences VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    (ts, suite, d["task_id"], d["surface_a"], d["surface_b"],
                     float(d["similarity"]), d.get("answer_a", ""), d.get("answer_b", "")),
                )
        return len(divergences)

    # --- read ---

    def _rows(self, cur) -> list[dict[str, Any]]:
        cols = [c.name for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def load_run_history(self, suite=None, provider=None):
        q = ("SELECT run_id, ts, suite, suite_version, provider, model, git_sha, "
             "pass_rate, input_tokens, output_tokens, total_cost_usd FROM runs WHERE TRUE")
        args: list[Any] = []
        if suite:
            q += " AND suite = %s"; args.append(suite)
        if provider:
            q += " AND provider = %s"; args.append(provider)
        q += " ORDER BY ts ASC"
        with self.conn.cursor() as cur:
            cur.execute(q, args)
            return self._rows(cur)

    def load_divergences(self, suite=None, limit=100):
        q = "SELECT ts, suite, task_id, surface_a, surface_b, similarity, answer_a, answer_b FROM divergences WHERE TRUE"
        args: list[Any] = []
        if suite:
            q += " AND suite = %s"; args.append(suite)
        q += " ORDER BY ts DESC LIMIT %s"; args.append(limit)
        with self.conn.cursor() as cur:
            cur.execute(q, args)
            return self._rows(cur)

    def find_regressions(self, suite: str, provider: str):
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT run_id FROM runs WHERE suite=%s AND provider=%s ORDER BY ts DESC LIMIT 2",
                (suite, provider),
            )
            runs = cur.fetchall()
            if len(runs) < 2:
                return []
            latest, prev = runs[0][0], runs[1][0]
            cur.execute(
                """SELECT curr.task_id, prev.passed, curr.passed
                   FROM task_results curr JOIN task_results prev ON prev.task_id=curr.task_id
                   WHERE curr.run_id=%s AND prev.run_id=%s
                     AND prev.passed=TRUE AND curr.passed=FALSE""",
                (latest, prev),
            )
            return [{"task_id": r[0], "prev_passed": r[1], "curr_passed": r[2]} for r in cur.fetchall()]

    def find_token_regressions(self, suite: str, provider: str, min_ratio: float = 1.3):
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT run_id FROM runs WHERE suite=%s AND provider=%s ORDER BY ts DESC LIMIT 2",
                (suite, provider),
            )
            runs = cur.fetchall()
            if len(runs) < 2:
                return []
            latest, prev = runs[0][0], runs[1][0]
            cur.execute(
                """SELECT curr.task_id, prev.output_tokens, curr.output_tokens,
                          curr.output_tokens::float / NULLIF(prev.output_tokens, 0) AS ratio
                   FROM task_results curr JOIN task_results prev ON prev.task_id=curr.task_id
                   WHERE curr.run_id=%s AND prev.run_id=%s
                     AND prev.passed=TRUE AND curr.passed=TRUE
                     AND prev.output_tokens > 0
                     AND curr.output_tokens::float / prev.output_tokens >= %s""",
                (latest, prev, min_ratio),
            )
            return [{"task_id": r[0], "prev_tokens": r[1], "curr_tokens": r[2], "ratio": r[3]} for r in cur.fetchall()]

    def close(self):
        self.conn.close()
