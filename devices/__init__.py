"""Device adapters — extend AgentEvalHub from cloud-only to cross-device.

Mirrors the `adapters/` pattern: one file per backend behind a shared ABC,
with lazy imports so a missing optional dependency (adb, Appium) only breaks
its own backend, not the harness.
"""
from .base import DeviceAction, DeviceAdapter, DeviceResult, DeviceUnavailable

__all__ = [
    "DeviceAction",
    "DeviceAdapter",
    "DeviceResult",
    "DeviceUnavailable",
    "get_device",
    "KNOWN_DEVICES",
]

KNOWN_DEVICES = ("mock_android", "adb_android", "appium_android")


def get_device(name: str, **kwargs) -> DeviceAdapter:
    """Lazy-load a device adapter. Missing SDKs only break their own backend."""
    if name == "mock_android":
        from .mock_android import MockAndroidAdapter
        return MockAndroidAdapter(**kwargs)
    if name == "adb_android":
        from .real_android import AdbAndroidAdapter
        return AdbAndroidAdapter(**kwargs)
    if name == "appium_android":
        from .appium_android import AppiumAndroidAdapter
        return AppiumAndroidAdapter(**kwargs)
    raise ValueError(f"Unknown device backend: {name}. Known: {', '.join(KNOWN_DEVICES)}")
