"""AdbAndroidAdapter — verifies it fails loudly and early when adb is absent,
so CI doesn't silently skip device tests. Real adb behavior is covered by the
local emulator workflow documented in the README."""
from __future__ import annotations

import pytest

from devices.base import DeviceUnavailable


def test_missing_adb_raises_device_unavailable(monkeypatch: pytest.MonkeyPatch):
    import shutil
    monkeypatch.setattr(shutil, "which", lambda _: None)

    from devices.real_android import AdbAndroidAdapter
    with pytest.raises(DeviceUnavailable, match="adb not found"):
        AdbAndroidAdapter()


def test_parse_top_activity_extracts_package():
    from devices.real_android import _parse_top_activity
    sample = """
    Display #0:
      mResumedActivity: ActivityRecord{abc u0 com.example.weather/.MainActivity t99}
    """
    assert _parse_top_activity(sample) == "com.example.weather"


def test_parse_top_activity_returns_none_when_no_match():
    from devices.real_android import _parse_top_activity
    assert _parse_top_activity("nothing useful here") is None
