# Adding a new device backend

1. Create `src/agent_eval_hub/devices/<name>.py` subclassing `DeviceAdapter`:
   ```python
   from .base import DeviceAdapter, DeviceResult, DeviceUnavailable

   class MyDevice(DeviceAdapter):
       platform = "android"  # or "windows", "ios", etc.

       def __init__(self, **kwargs):
           # If a required dep is missing, raise DeviceUnavailable loudly.
           ...

       def execute(self, action: str, args: dict) -> DeviceResult: ...
       def snapshot(self) -> dict: ...
       def reset(self) -> None: ...
       def close(self) -> None: ...
   ```

2. Register it in `src/agent_eval_hub/devices/__init__.py`:
   ```python
   KNOWN_DEVICES = (..., "my_device")

   def get_device(name: str, **kwargs) -> DeviceAdapter:
       ...
       if name == "my_device":
           from .my_device import MyDevice
           return MyDevice(**kwargs)
   ```

3. Any suite can now use it:
   ```yaml
   device:
     backend: my_device
     # backend-specific kwargs are passed through
   ```

4. Update the class mapping in `tests/contract/test_device_contract.py` so the contract tests parameterize over it.

## Design rules

- **`DeviceUnavailable`, not `ImportError`.** Missing deps (adb, Appium) must raise `DeviceUnavailable` with an actionable message. The harness treats this as "CI can't run this backend" rather than crashing.
- **Fixture-first for new backends.** Add a mock alongside the real one. CI runs the mock; local runs hit the real device. Same YAML suite.
- **`reset()` between tasks.** State must not leak from one task to the next or `device_state` graders lie.
