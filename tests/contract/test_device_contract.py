"""Device contract tests — parameterized over KNOWN_DEVICES.

Every registered device backend must:
  1. Subclass DeviceAdapter
  2. Expose `execute`, `snapshot`, `reset`, `close`
  3. For backends that need external deps (adb, Appium), raise DeviceUnavailable
     cleanly when the dep is missing — never an opaque ImportError/FileNotFoundError.
"""
from __future__ import annotations

import shutil
import sys

import pytest

from agent_eval_hub.devices import KNOWN_DEVICES
from agent_eval_hub.devices.base import DeviceAdapter, DeviceUnavailable


@pytest.mark.parametrize("backend", KNOWN_DEVICES)
def test_every_device_has_required_methods(backend: str):
    """Without instantiating (which may need adb/appium), check the class surface."""
    module_name = {
        "mock_android": "agent_eval_hub.devices.mock_android",
        "adb_android": "agent_eval_hub.devices.real_android",
        "appium_android": "agent_eval_hub.devices.appium_android",
    }[backend]
    class_name = {
        "mock_android": "MockAndroidAdapter",
        "adb_android": "AdbAndroidAdapter",
        "appium_android": "AppiumAndroidAdapter",
    }[backend]

    import importlib
    mod = importlib.import_module(module_name)
    cls = getattr(mod, class_name)
    assert issubclass(cls, DeviceAdapter), f"{class_name} must subclass DeviceAdapter"
    for method in ("execute", "snapshot", "reset", "close"):
        assert hasattr(cls, method), f"{class_name} missing {method}()"


def test_adb_missing_raises_device_unavailable(monkeypatch: pytest.MonkeyPatch):
    """adb_android must raise DeviceUnavailable when adb isn't on PATH."""
    monkeypatch.setattr(shutil, "which", lambda _: None)
    from agent_eval_hub.devices.real_android import AdbAndroidAdapter
    with pytest.raises(DeviceUnavailable):
        AdbAndroidAdapter()


def test_appium_missing_raises_device_unavailable(monkeypatch: pytest.MonkeyPatch):
    """appium_android must raise DeviceUnavailable when appium isn't installed."""
    monkeypatch.setitem(sys.modules, "appium", None)
    from agent_eval_hub.devices.appium_android import AppiumAndroidAdapter
    with pytest.raises(DeviceUnavailable):
        AppiumAndroidAdapter()
