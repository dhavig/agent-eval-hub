from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable

from adapters.base import Adapter, Tool, ToolCall


@dataclass
class RunTrace:
    task_id: str
    provider: str
    model: str
    final_text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    steps: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    latency_s: float = 0.0
    error: str | None = None


ToolHandler = Callable[[ToolCall], str]


def run_agent(
    adapter: Adapter,
    task_id: str,
    system: str,
    user_prompt: str,
    tools: list[Tool] | None = None,
    tool_handlers: dict[str, ToolHandler] | None = None,
    max_steps: int = 5,
) -> RunTrace:
    """Drive an agent through a task. Stops when the model returns no tool calls."""
    trace = RunTrace(task_id=task_id, provider=adapter.provider, model=adapter.model, final_text="")
    tool_handlers = tool_handlers or {}
    messages: list[dict[str, Any]] = [{"role": "user", "content": user_prompt}]
    start = time.time()

    try:
        for step in range(max_steps):
            trace.steps = step + 1
            resp = adapter.complete(system=system, messages=messages, tools=tools)
            trace.input_tokens += resp.input_tokens
            trace.output_tokens += resp.output_tokens
            trace.tool_calls.extend(resp.tool_calls)

            if not resp.tool_calls:
                trace.final_text = resp.text
                break

            # Feed tool results back as a plain user message (simplified for v1).
            results: list[str] = []
            for call in resp.tool_calls:
                handler = tool_handlers.get(call.name)
                result = handler(call) if handler else f"[no handler for {call.name}]"
                results.append(f"{call.name}({call.arguments}) -> {result}")

            messages.append({"role": "assistant", "content": resp.text or "(tool use)"})
            messages.append({"role": "user", "content": "Tool results:\n" + "\n".join(results)})
    except Exception as exc:  # surface provider errors into the trace, don't crash the suite
        trace.error = f"{type(exc).__name__}: {exc}"

    trace.latency_s = time.time() - start
    return trace
