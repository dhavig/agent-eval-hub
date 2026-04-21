from __future__ import annotations

import shutil
import subprocess
from typing import Any

from .base import DeviceAdapter, DeviceResult, DeviceUnavailable


class AdbAndroidAdapter(DeviceAdapter):
    """Real Android backend via `adb`. Requires `adb` on PATH and a reachable
    device (physical or emulator). Falls back with a clear error if unavailable —
    so CI without an emulator can route to MockAndroidAdapter instead of crashing.

    Supported actions (intentionally small; extend as your suite grows):
      - launch_app(package): monkey -p <pkg> -c LAUNCHER 1
      - stop_app(package):   am force-stop <pkg>
      - get_current_app():   dumpsys activity activities | topResumedActivity
      - shell(command):      raw `adb shell <command>` escape hatch
      - list_packages():     pm list packages -3
    """

    platform = "android"

    def __init__(self, serial: str | None = None, adb_path: str | None = None):
        self.adb_path = adb_path or shutil.which("adb")
        if not self.adb_path:
            raise DeviceUnavailable(
                "adb not found on PATH. Install Android platform-tools or use mock_android."
            )
        self.serial = serial
        self._state: dict[str, Any] = {"current_app": None}
        self._ensure_device_connected()

    def _adb(self, *args: str) -> str:
        cmd = [self.adb_path]
        if self.serial:
            cmd += ["-s", self.serial]
        cmd += list(args)
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if proc.returncode != 0:
            raise DeviceUnavailable(f"adb {args} failed: {proc.stderr.strip()}")
        return proc.stdout

    def _ensure_device_connected(self) -> None:
        out = self._adb("devices")
        lines = [line for line in out.splitlines()[1:] if line.strip() and "\tdevice" in line]
        if not lines:
            raise DeviceUnavailable("adb found no connected devices. Start an emulator first.")

    def execute(self, action: str, args: dict[str, Any]) -> DeviceResult:
        try:
            if action == "launch_app":
                pkg = args["package"]
                self._adb("shell", "monkey", "-p", pkg, "-c", "android.intent.category.LAUNCHER", "1")
                self._state["current_app"] = pkg
                return DeviceResult(output=f"launched {pkg}", state=dict(self._state))

            if action == "stop_app":
                pkg = args["package"]
                self._adb("shell", "am", "force-stop", pkg)
                if self._state.get("current_app") == pkg:
                    self._state["current_app"] = None
                return DeviceResult(output=f"stopped {pkg}", state=dict(self._state))

            if action == "get_current_app":
                raw = self._adb("shell", "dumpsys", "activity", "activities")
                pkg = _parse_top_activity(raw)
                self._state["current_app"] = pkg
                return DeviceResult(output=pkg or "none", state=dict(self._state))

            if action == "list_packages":
                raw = self._adb("shell", "pm", "list", "packages", "-3")
                pkgs = [line.removeprefix("package:").strip() for line in raw.splitlines() if line.strip()]
                return DeviceResult(output="\n".join(pkgs), state=dict(self._state))

            if action == "shell":
                cmd = args["command"]
                raw = self._adb("shell", cmd)
                return DeviceResult(output=raw.strip(), state=dict(self._state))

            return DeviceResult(output=f"[adb_android] unknown action {action!r}", success=False, state=dict(self._state))
        except DeviceUnavailable as exc:
            return DeviceResult(output=f"adb error: {exc}", success=False, state=dict(self._state))

    def snapshot(self) -> dict[str, Any]:
        return dict(self._state)


def _parse_top_activity(dumpsys_output: str) -> str | None:
    """Find topResumedActivity=...ActivityRecord{... u0 <pkg>/... line."""
    for line in dumpsys_output.splitlines():
        line = line.strip()
        if line.startswith("topResumedActivity") or line.startswith("mResumedActivity"):
            # ...u0 com.example.weather/.MainActivity t123}
            for tok in line.split():
                if "/" in tok and "." in tok:
                    return tok.split("/")[0]
    return None
