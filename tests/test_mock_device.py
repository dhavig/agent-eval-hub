"""MockAndroidAdapter — fixture-driven device for CI-friendly UI tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_eval_hub.devices import get_device
from agent_eval_hub.devices.mock_android import MockAndroidAdapter


@pytest.fixture
def fixture_path(tmp_path: Path) -> Path:
    p = tmp_path / "fx.json"
    p.write_text(json.dumps({
        "initial_state": {"current_app": None, "installed": ["com.example.weather"]},
        "actions": {
            "launch_app": {"output": "launched <args.package>", "state": {"current_app": "<args.package>"}},
            "get_screen_text": {"output": "hello world"},
            "fail_me": {"output": "nope", "success": False},
        },
    }))
    return p


def test_loads_initial_state(fixture_path: Path):
    d = MockAndroidAdapter(fixture=fixture_path)
    snap = d.snapshot()
    assert snap["current_app"] is None
    assert "com.example.weather" in snap["installed"]


def test_action_updates_state_with_templated_args(fixture_path: Path):
    d = MockAndroidAdapter(fixture=fixture_path)
    result = d.execute("launch_app", {"package": "com.example.weather"})
    assert result.success
    assert result.output == "launched com.example.weather"
    assert d.snapshot()["current_app"] == "com.example.weather"


def test_unknown_action_returns_failed_result_without_crashing(fixture_path: Path):
    d = MockAndroidAdapter(fixture=fixture_path)
    result = d.execute("nonexistent", {})
    assert not result.success
    assert "no fixture" in result.output


def test_fixture_can_mark_action_as_failed(fixture_path: Path):
    d = MockAndroidAdapter(fixture=fixture_path)
    result = d.execute("fail_me", {})
    assert not result.success


def test_reset_restores_initial_state(fixture_path: Path):
    d = MockAndroidAdapter(fixture=fixture_path)
    d.execute("launch_app", {"package": "com.example.weather"})
    assert d.snapshot()["current_app"] == "com.example.weather"
    d.reset()
    assert d.snapshot()["current_app"] is None


def test_factory_returns_mock_adapter(fixture_path: Path):
    d = get_device("mock_android", fixture=fixture_path)
    assert isinstance(d, MockAndroidAdapter)


def test_factory_rejects_unknown_backend():
    with pytest.raises(ValueError, match="Unknown device backend"):
        get_device("not_a_real_device")
