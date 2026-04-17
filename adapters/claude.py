from __future__ import annotations

import os
from typing import Any

from anthropic import Anthropic

from .base import Adapter, AgentResponse, Tool, ToolCall


class ClaudeAdapter(Adapter):
    provider = "claude"

    def __init__(self, model: str = "claude-sonnet-4-6"):
        super().__init__(model)
        self.client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    def complete(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[Tool] | None = None,
        temperature: float = 0.0,
    ) -> AgentResponse:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": 1024,
            "system": system,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.input_schema,
                }
                for t in tools
            ]

        resp = self.client.messages.create(**kwargs)

        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in resp.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(name=block.name, arguments=block.input))

        return AgentResponse(
            text="".join(text_parts),
            tool_calls=tool_calls,
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
            raw=resp,
        )
