"""AppiumAndroidAdapter — ensure missing appium-python-client raises a clear
DeviceUnavailable rather than an opaque ImportError."""
from __future__ import annotations

import sys

import pytest

from devices.base import DeviceUnavailable


def test_missing_appium_package_raises_device_unavailable(monkeypatch: pytest.MonkeyPatch):
    # Simulate appium not being installed by injecting ImportError for the module.
    monkeypatch.setitem(sys.modules, "appium", None)

    from devices.appium_android import AppiumAndroidAdapter
    with pytest.raises(DeviceUnavailable, match="appium-python-client not installed"):
        AppiumAndroidAdapter()
