from __future__ import annotations

import os
from typing import Any

from google import genai
from google.genai import types

from .base import Adapter, AgentResponse, Tool, ToolCall


def _role(role: str) -> str:
    """Gemini uses 'model' where OpenAI/Claude use 'assistant'."""
    return "model" if role == "assistant" else role


class GeminiAdapter(Adapter):
    provider = "gemini"

    def __init__(self, model: str = "gemini-2.5-pro"):
        super().__init__(model)
        self.client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    def _build_contents(self, messages: list[dict[str, Any]]) -> list[types.Content]:
        return [
            types.Content(role=_role(m["role"]), parts=[types.Part.from_text(text=m["content"])])
            for m in messages
        ]

    def _build_tools(self, tools: list[Tool] | None) -> list[types.Tool] | None:
        if not tools:
            return None
        declarations = [
            types.FunctionDeclaration(
                name=t.name,
                description=t.description,
                parameters=t.input_schema,
            )
            for t in tools
        ]
        return [types.Tool(function_declarations=declarations)]

    def complete(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[Tool] | None = None,
        temperature: float = 0.0,
    ) -> AgentResponse:
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            tools=self._build_tools(tools),
        )

        resp = self.client.models.generate_content(
            model=self.model,
            contents=self._build_contents(messages),
            config=config,
        )

        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        candidate = resp.candidates[0] if resp.candidates else None
        for part in (candidate.content.parts if candidate and candidate.content else []):
            if getattr(part, "function_call", None):
                fc = part.function_call
                tool_calls.append(ToolCall(name=fc.name, arguments=dict(fc.args or {})))
            elif getattr(part, "text", None):
                text_parts.append(part.text)

        usage = resp.usage_metadata
        return AgentResponse(
            text="".join(text_parts),
            tool_calls=tool_calls,
            input_tokens=getattr(usage, "prompt_token_count", 0) or 0,
            output_tokens=getattr(usage, "candidates_token_count", 0) or 0,
            raw=resp,
        )
