"""device_state grader — asserts on the device snapshot, not just the tool call.
This is the difference between 'agent called launch_app' (tool_called) and
'the app is actually running' (device_state)."""
from __future__ import annotations

from graders.deterministic import device_state
from runner.agent_loop import RunTrace


def _trace(snapshot: dict | None) -> RunTrace:
    return RunTrace(
        task_id="t",
        provider="p",
        model="m",
        final_text="",
        device_snapshot=snapshot,
    )


def test_passes_when_snapshot_value_matches():
    r = device_state(_trace({"current_app": "com.example.weather"}), "current_app", "com.example.weather")
    assert r.passed


def test_fails_when_snapshot_value_differs():
    r = device_state(_trace({"current_app": "com.other"}), "current_app", "com.example.weather")
    assert not r.passed
    assert "com.other" in r.detail


def test_fails_when_key_absent():
    r = device_state(_trace({"foo": 1}), "current_app", "com.example.weather")
    assert not r.passed
    assert "no device_snapshot key" in r.detail


def test_fails_when_snapshot_is_none():
    r = device_state(_trace(None), "current_app", "com.example.weather")
    assert not r.passed
