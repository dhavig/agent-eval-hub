from __future__ import annotations

import json
import os
from typing import Any

from openai import OpenAI

from .base import Adapter, AgentResponse, Tool, ToolCall


class OpenAIAdapter(Adapter):
    provider = "openai"

    def __init__(self, model: str = "gpt-4o-mini"):
        super().__init__(model)
        self.client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    def complete(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[Tool] | None = None,
        temperature: float = 0.0,
    ) -> AgentResponse:
        oai_messages = [{"role": "system", "content": system}, *messages]

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": oai_messages,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = [
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

        resp = self.client.chat.completions.create(**kwargs)
        choice = resp.choices[0].message

        tool_calls: list[ToolCall] = []
        for call in choice.tool_calls or []:
            tool_calls.append(
                ToolCall(
                    name=call.function.name,
                    arguments=json.loads(call.function.arguments or "{}"),
                )
            )

        return AgentResponse(
            text=choice.content or "",
            tool_calls=tool_calls,
            input_tokens=resp.usage.prompt_tokens,
            output_tokens=resp.usage.completion_tokens,
            raw=resp,
        )
