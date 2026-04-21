from __future__ import annotations

from typing import Any

from .base import DeviceAdapter, DeviceResult, DeviceUnavailable


class AppiumAndroidAdapter(DeviceAdapter):
    """Android UI automation via Appium. Actions map to WebDriver calls.

    Requires `appium-python-client` and a running Appium server. The import is
    deferred so the harness works in CI without Appium installed — only this
    backend breaks when it's missing, matching the lazy-import pattern used
    for LLM provider SDKs.

    Supported actions:
      - launch_app(package, activity): start an app
      - tap(x, y):                     coordinate tap
      - tap_by_text(text):             find element by text and tap
      - get_screen_text():             concatenate all visible text
      - send_keys(text):               type into focused field
    """

    platform = "android"

    def __init__(
        self,
        server_url: str = "http://localhost:4723",
        device_name: str = "Android Emulator",
        platform_version: str | None = None,
        app_package: str | None = None,
        app_activity: str | None = None,
    ):
        try:
            from appium import webdriver
            from appium.options.android import UiAutomator2Options
        except ImportError as exc:
            raise DeviceUnavailable(
                "appium-python-client not installed. `pip install Appium-Python-Client` "
                "or use mock_android for CI."
            ) from exc

        options = UiAutomator2Options()
        options.device_name = device_name
        if platform_version:
            options.platform_version = platform_version
        if app_package:
            options.app_package = app_package
        if app_activity:
            options.app_activity = app_activity

        try:
            self.driver = webdriver.Remote(server_url, options=options)
        except Exception as exc:
            raise DeviceUnavailable(f"Could not connect to Appium at {server_url}: {exc}") from exc

        self._state: dict[str, Any] = {"current_app": app_package, "last_screen": ""}

    def execute(self, action: str, args: dict[str, Any]) -> DeviceResult:
        try:
            if action == "launch_app":
                pkg = args["package"]
                activity = args.get("activity", ".MainActivity")
                self.driver.start_activity(pkg, activity)
                self._state["current_app"] = pkg
                return DeviceResult(output=f"launched {pkg}", state=dict(self._state))

            if action == "tap":
                self.driver.tap([(int(args["x"]), int(args["y"]))])
                return DeviceResult(output=f"tapped ({args['x']}, {args['y']})", state=dict(self._state))

            if action == "tap_by_text":
                from appium.webdriver.common.appiumby import AppiumBy
                el = self.driver.find_element(by=AppiumBy.ANDROID_UIAUTOMATOR, value=f'new UiSelector().text("{args["text"]}")')
                el.click()
                return DeviceResult(output=f"tapped element with text={args['text']!r}", state=dict(self._state))

            if action == "get_screen_text":
                from appium.webdriver.common.appiumby import AppiumBy
                els = self.driver.find_elements(by=AppiumBy.XPATH, value="//*[@text]")
                text = "\n".join(el.get_attribute("text") or "" for el in els).strip()
                self._state["last_screen"] = text
                return DeviceResult(output=text, state=dict(self._state))

            if action == "send_keys":
                self.driver.switch_to.active_element.send_keys(args["text"])
                return DeviceResult(output=f"typed {args['text']!r}", state=dict(self._state))

            return DeviceResult(
                output=f"[appium_android] unknown action {action!r}",
                success=False,
                state=dict(self._state),
            )
        except Exception as exc:  # surface driver errors without crashing the suite
            return DeviceResult(output=f"appium error: {exc}", success=False, state=dict(self._state))

    def snapshot(self) -> dict[str, Any]:
        return dict(self._state)

    def close(self) -> None:
        try:
            self.driver.quit()
        except Exception:
            pass
