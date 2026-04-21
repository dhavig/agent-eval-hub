"""End-to-end: run the device_ui suite against a stub LLM + the mock device.
Proves the whole chain — adapter -> agent loop -> device tool handlers ->
device snapshot -> device_state grader — works without an emulator, API key,
or network call.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from agent_eval_hub.adapters import get_adapter as _real_get_adapter
from agent_eval_hub.adapters.base import Adapter, AgentResponse, ToolCall

pytestmark = pytest.mark.integration


class ScriptedAdapter(Adapter):
    """Returns a pre-baked sequence of AgentResponses, one per .complete() call.
    Lets us assert that the agent loop + device wiring behave correctly without
    requiring a real LLM in CI."""

    provider = "scripted"

    def __init__(self, model: str, responses: list[AgentResponse]):
        super().__init__(model)
        self._responses = list(responses)

    def complete(self, system, messages, tools=None, temperature=0.0):
        if not self._responses:
            return AgentResponse(text="(no more scripted responses)")
        return self._responses.pop(0)


def _patch_adapter(monkeypatch: pytest.MonkeyPatch, mapping: dict[str, list[AgentResponse]]):
    """Replace get_adapter so the runner picks up our scripted responses per provider."""
    def fake(name: str, model: str):
        if name in mapping:
            return ScriptedAdapter(model=model, responses=mapping[name])
        return _real_get_adapter(name, model)

    import agent_eval_hub.runner.run_suite as rs
    monkeypatch.setattr(rs, "get_adapter", fake)


def test_device_ui_suite_end_to_end(monkeypatch: pytest.MonkeyPatch):
    """Drive the real device_ui.yaml suite, scripting one 3-task conversation."""
    # Task 1: launch_weather — call launch_app, then close with a final message.
    # Task 2: read_screen_then_summarize — launch_app -> get_screen_text -> summary.
    # Task 3: decline_unknown_app — list_packages -> refuse.
    responses = [
        # Task 1: launch_weather
        AgentResponse(text="", tool_calls=[ToolCall(name="launch_app", arguments={"package": "com.example.weather"})]),
        AgentResponse(text="Opened the weather app."),
        # Task 2: read_screen_then_summarize
        AgentResponse(text="", tool_calls=[ToolCall(name="launch_app", arguments={"package": "com.example.weather"})]),
        AgentResponse(text="", tool_calls=[ToolCall(name="get_screen_text", arguments={})]),
        AgentResponse(text="Weather in Paris is 15C with light rain."),
        # Task 3: decline_unknown_app
        AgentResponse(text="", tool_calls=[ToolCall(name="list_packages", arguments={})]),
        AgentResponse(text="I can't open Spotify — it isn't installed on this device."),
    ]
    _patch_adapter(monkeypatch, {"scripted": responses})

    from agent_eval_hub.runner.run_suite import run_suite
    suite_path = Path(__file__).resolve().parent.parent / "suites" / "device_ui.yaml"
    report = run_suite(suite_path, provider="scripted", model="stub")

    by_id = {s.task_id: s for s in report.scores}

    # Task 1 — device must reflect the launched app
    assert by_id["launch_weather"].passed
    assert by_id["launch_weather"].trace.device_snapshot["current_app"] == "com.example.weather"

    # Task 2 — agent summarized Paris 15C from device output
    assert by_id["read_screen_then_summarize"].passed

    # Task 3 — agent refused and did NOT call launch_app with Spotify args
    task3 = by_id["decline_unknown_app"]
    assert task3.passed, [g.detail for g in task3.grades if not g.passed]


def test_device_reset_between_tasks(monkeypatch: pytest.MonkeyPatch):
    """State must not leak between tasks — a prior task's launched app should
    not bias the next task's device_state grader."""
    # Just two tasks: first launches weather, second inspects state.
    # device.reset() runs before each task, so task 2's starting state = None.
    responses = [
        AgentResponse(text="", tool_calls=[ToolCall(name="launch_app", arguments={"package": "com.example.weather"})]),
        AgentResponse(text="done"),
        AgentResponse(text="no action taken"),
    ]
    _patch_adapter(monkeypatch, {"scripted": responses})

    import yaml

    from agent_eval_hub.runner.run_suite import run_suite
    suite_dict = {
        "name": "device_reset_check",
        "device": {
            "backend": "mock_android",
            "fixture": str(Path(__file__).resolve().parent.parent / "fixtures" / "devices" / "basic_ui.json"),
        },
        "tools": [
            {"name": "launch_app", "description": "", "input_schema": {"type": "object", "properties": {"package": {"type": "string"}}, "required": ["package"]}},
        ],
        "tasks": [
            {"id": "t1_launch", "system": "s", "user": "open weather", "graders": [{"type": "device_state", "key": "current_app", "equals": "com.example.weather"}]},
            {"id": "t2_fresh", "system": "s", "user": "do nothing", "graders": [{"type": "device_state", "key": "current_app", "equals": None}]},
        ],
    }
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        yaml.safe_dump(suite_dict, f)
        path = Path(f.name)

    report = run_suite(path, provider="scripted", model="stub")
    assert all(s.passed for s in report.scores), [(s.task_id, [g.detail for g in s.grades]) for s in report.scores]
