"""Smoke test for run_cross_surface.main — proves the full pipeline works:
load suite, run against two providers, compute jaccard divergences, exit 0/1."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

from adapters import get_adapter as _real_get_adapter
from adapters.base import Adapter, AgentResponse


class _Static(Adapter):
    provider = "static"

    def __init__(self, model: str, text: str):
        super().__init__(model)
        self._text = text

    def complete(self, system, messages, tools=None, temperature=0.0):  # noqa: ARG002
        return AgentResponse(text=self._text)


@pytest.fixture
def trivial_suite(tmp_path: Path) -> Path:
    path = tmp_path / "trivial.yaml"
    yaml.safe_dump({
        "name": "trivial",
        "tools": [],
        "tasks": [
            {"id": "q1", "system": "s", "user": "what is the weather?", "graders": []},
        ],
    }, path.open("w"))
    return path


def test_cross_surface_returns_zero_when_answers_agree(monkeypatch: pytest.MonkeyPatch, trivial_suite: Path):
    def fake(name: str, model: str):
        if name in ("A", "B"):
            return _Static(model=model, text="the weather is sunny and 20 degrees")
        return _real_get_adapter(name, model)

    import runner.run_suite as rs
    import runner.run_cross_surface as rcs
    monkeypatch.setattr(rs, "get_adapter", fake)
    monkeypatch.setattr(sys, "argv", [
        "run_cross_surface",
        "--suite", str(trivial_suite),
        "--surface-a", "A:m1",
        "--surface-b", "B:m2",
        "--threshold", "0.5",
    ])
    assert rcs.main() == 0


def test_cross_surface_returns_one_when_answers_diverge(monkeypatch: pytest.MonkeyPatch, trivial_suite: Path):
    # Surface A says sunny, Surface B says rainy — share only "the weather is".
    responses = {"A": "the weather is sunny and clear", "B": "the weather is rainy and cold"}

    def fake(name: str, model: str):
        if name in responses:
            return _Static(model=model, text=responses[name])
        return _real_get_adapter(name, model)

    import runner.run_suite as rs
    import runner.run_cross_surface as rcs
    monkeypatch.setattr(rs, "get_adapter", fake)
    monkeypatch.setattr(sys, "argv", [
        "run_cross_surface",
        "--suite", str(trivial_suite),
        "--surface-a", "A:m1",
        "--surface-b", "B:m2",
        "--threshold", "0.9",  # force divergence
    ])
    assert rcs.main() == 1


def test_divergences_recorded_to_db(monkeypatch: pytest.MonkeyPatch, trivial_suite: Path, tmp_path: Path):
    def fake(name: str, model: str):
        if name == "A":
            return _Static(model=model, text="completely one")
        if name == "B":
            return _Static(model=model, text="utterly different")
        return _real_get_adapter(name, model)

    import runner.run_suite as rs
    import runner.run_cross_surface as rcs
    monkeypatch.setattr(rs, "get_adapter", fake)

    db = tmp_path / "div.duckdb"
    monkeypatch.setattr(sys, "argv", [
        "run_cross_surface",
        "--suite", str(trivial_suite),
        "--surface-a", "A:m1",
        "--surface-b", "B:m2",
        "--threshold", "0.9",
        "--db", str(db),
    ])
    assert rcs.main() == 1

    from storage.duckdb_store import connect, load_divergences
    con = connect(db)
    rows = load_divergences(con)
    con.close()
    assert len(rows) == 1
    assert rows[0]["task_id"] == "q1"
    assert rows[0]["similarity"] < 0.9
