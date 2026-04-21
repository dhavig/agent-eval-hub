from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .base import DeviceAdapter, DeviceResult


class MockAndroidAdapter(DeviceAdapter):
    """Fixture-driven Android device. CI-friendly: no emulator required.

    The fixture is a JSON file shaped like:
        {
          "initial_state": {"current_app": null, "installed": ["com.example.weather"]},
          "actions": {
            "launch_app":    {"output": "launched", "state": {"current_app": "<args.package>"}},
            "get_screen":    {"output": "Weather: 15C Paris"},
            "get_intents":   {"output": "android.intent.action.VIEW com.example.weather"}
          }
        }

    A `state` entry may reference args with `<args.key>` templating so a single
    action definition handles any package name. Keeps fixtures small.
    """

    platform = "android"

    def __init__(self, fixture: str | Path):
        self.fixture_path = Path(fixture)
        raw = json.loads(self.fixture_path.read_text())
        self._initial_state: dict[str, Any] = raw.get("initial_state", {})
        self._actions: dict[str, Any] = raw.get("actions", {})
        self._state: dict[str, Any] = dict(self._initial_state)

    def execute(self, action: str, args: dict[str, Any]) -> DeviceResult:
        spec = self._actions.get(action)
        if spec is None:
            return DeviceResult(
                output=f"[mock_android] no fixture for action={action!r}",
                success=False,
                state=dict(self._state),
            )

        output = _render(spec.get("output", ""), args)
        for k, v in spec.get("state", {}).items():
            self._state[k] = _render(v, args) if isinstance(v, str) else v
        return DeviceResult(
            output=output,
            success=bool(spec.get("success", True)),
            state=dict(self._state),
        )

    def snapshot(self) -> dict[str, Any]:
        return dict(self._state)

    def reset(self) -> None:
        self._state = dict(self._initial_state)


def _render(template: str, args: dict[str, Any]) -> str:
    """Replace <args.key> tokens in a fixture string with the call's arguments."""
    out = template
    for key, value in args.items():
        out = out.replace(f"<args.{key}>", str(value))
    return out
