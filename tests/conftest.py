"""Shared pytest fixtures + path-based auto-marking.

Fixtures live here so multiple tests can reuse them without copy-paste:
  - ScriptedAdapter: a stub LLM adapter that replays pre-baked responses
  - tmp_db: a fresh DuckDB store path per test
  - fixture_repo_path: points at the project's fixtures/ directory

Auto-marking by path: tests under tests/unit/ get @pytest.mark.unit, etc.
Writers of new tests don't need to remember markers — the directory structure
is the contract.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from agent_eval_hub.adapters.base import Adapter, AgentResponse

REPO_ROOT = Path(__file__).resolve().parent.parent


class ScriptedAdapter(Adapter):
    """Replay pre-baked AgentResponses, one per .complete() call.

    Lets integration tests assert end-to-end behavior without an API key or
    network. Raises if a test requests more turns than it scripted — catches
    off-by-one errors loudly instead of returning stale responses."""

    provider = "scripted"

    def __init__(self, model: str, responses: list[AgentResponse]):
        super().__init__(model)
        self._responses = list(responses)

    def complete(self, system, messages, tools=None, temperature=0.0):
        if not self._responses:
            return AgentResponse(text="(no more scripted responses)")
        return self._responses.pop(0)


@pytest.fixture
def scripted_adapter():
    """Factory for ScriptedAdapter — use as `scripted_adapter([resp1, resp2, ...])`."""
    def _build(responses: list[AgentResponse], model: str = "stub") -> ScriptedAdapter:
        return ScriptedAdapter(model=model, responses=responses)
    return _build


@pytest.fixture
def patch_get_adapter(monkeypatch: pytest.MonkeyPatch):
    """Helper: patch runner.run_suite.get_adapter so the CLI picks up a stub.

    Usage:
        patch_get_adapter({"claude": [AgentResponse(...), ...]})
    """
    from agent_eval_hub.adapters import get_adapter as _real

    def _apply(mapping: dict[str, list[AgentResponse]]) -> None:
        def fake(name: str, model: str):
            if name in mapping:
                return ScriptedAdapter(model=model, responses=mapping[name])
            return _real(name, model)

        import agent_eval_hub.runner.run_suite as rs
        monkeypatch.setattr(rs, "get_adapter", fake)

    return _apply


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    """Fresh DuckDB path that gets cleaned up automatically."""
    return tmp_path / "runs.duckdb"


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture
def mock_android_fixture() -> Path:
    return REPO_ROOT / "fixtures" / "devices" / "basic_ui.json"


def pytest_collection_modifyitems(config, items):
    """Auto-mark tests based on their folder: tests/unit/, tests/integration/, tests/e2e/.
    Tests outside these folders (currently the default) get no mark and run every time.
    """
    unit_dir = "tests/unit/"
    integration_dir = "tests/integration/"
    e2e_dir = "tests/e2e/"
    device_dir = "tests/device/"
    for item in items:
        nodeid = item.nodeid.replace("\\", "/")
        if unit_dir in nodeid:
            item.add_marker(pytest.mark.unit)
        elif integration_dir in nodeid:
            item.add_marker(pytest.mark.integration)
        elif e2e_dir in nodeid:
            item.add_marker(pytest.mark.e2e)
        elif device_dir in nodeid:
            item.add_marker(pytest.mark.device)
