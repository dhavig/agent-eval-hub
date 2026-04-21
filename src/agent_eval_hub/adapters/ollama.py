from __future__ import annotations

import json
import os
from typing import Any

import httpx

from .base import Adapter, AgentResponse, Tool, ToolCall


class OllamaAdapter(Adapter):
    """Adapter for a locally-running Ollama server (default http://localhost:11434).

    Uses the /api/chat endpoint. Tool use is supported for models that implement it
    (e.g. llama3.1, qwen2.5). For smaller models without tool-use training, tool_calls
    will simply be empty and the agent loop will terminate after one step.
    """

    provider = "ollama"

    def __init__(self, model: str = "llama3.1", base_url: str | None = None, timeout: float = 120.0):
        super().__init__(model)
        self.base_url = base_url or os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        self.timeout = timeout

    def complete(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[Tool] | None = None,
        temperature: float = 0.0,
    ) -> AgentResponse:
        body: dict[str, Any] = {
            "model": self.model,
            "stream": False,
            "options": {"temperature": temperature},
            "messages": [{"role": "system", "content": system}, *messages],
        }
        if tools:
            body["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.input_schema,
                    },
                }
                for t in tools
            ]

        with httpx.Client(timeout=self.timeout) as client:
            r = client.post(f"{self.base_url}/api/chat", json=body)
            r.raise_for_status()
            data = r.json()

        msg = data.get("message", {})
        tool_calls: list[ToolCall] = []
        for call in msg.get("tool_calls", []) or []:
            fn = call.get("function", {})
            args = fn.get("arguments", {})
            # Ollama sometimes returns arguments as a JSON string, sometimes as a dict.
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            tool_calls.append(ToolCall(name=fn.get("name", ""), arguments=args))

        return AgentResponse(
            text=msg.get("content", "") or "",
            tool_calls=tool_calls,
            input_tokens=data.get("prompt_eval_count", 0) or 0,
            output_tokens=data.get("eval_count", 0) or 0,
            raw=data,
        )
