"""Device-specific graders. Separated from `deterministic` because device
assertions read from `RunTrace.device_snapshot`, not `final_text` or
`tool_calls` — different surface, different mental model.
"""
from __future__ import annotations

from agent_eval_hub.graders.deterministic import GradeResult
from agent_eval_hub.runner.agent_loop import RunTrace


def device_state(trace: RunTrace, key: str, equals: object = None) -> GradeResult:
    """Assert that after the run, the device snapshot has `key == equals`.

    Checks the physical side-effect on the device (e.g. current_app is what we
    expected), not just that the LLM issued the right tool call."""
    snap = trace.device_snapshot or {}
    if key not in snap:
        return GradeResult(
            name="device_state",
            passed=False,
            detail=f"no device_snapshot key {key!r} (snapshot keys: {list(snap)})",
        )
    actual = snap[key]
    return GradeResult(
        name="device_state",
        passed=actual == equals,
        detail=f"{key}={actual!r} (expected {equals!r})",
    )
