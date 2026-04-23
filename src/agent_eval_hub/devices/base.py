from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


class DeviceUnavailable(RuntimeError):
    """Raised when a device backend's runtime dependency is missing (adb, appium, ...)."""


@dataclass
class DeviceAction:
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class DeviceResult:
    output: str
    success: bool = True
    state: dict[str, Any] = field(default_factory=dict)


class DeviceAdapter(ABC):
    """A device-side executor. The LLM issues tool calls; the device runs them.

    Concrete backends translate a (name, args) pair into whatever the underlying
    surface needs — an adb shell, an Appium WebDriver call, a fixture lookup —
    and return a DeviceResult that the agent loop feeds back as a tool result.
    """

    platform: str = "base"

    @abstractmethod
    def execute(self, action: str, args: dict[str, Any]) -> DeviceResult: ...

    @abstractmethod
    def snapshot(self) -> dict[str, Any]:
        """Return a small, comparable view of device state for grader assertions."""

    def reset(self) -> None:
        """Optional: reset state between tasks. Default is a no-op."""
        return None

    def close(self) -> None:
        """Optional: release resources (adb session, Appium driver)."""
        return None
