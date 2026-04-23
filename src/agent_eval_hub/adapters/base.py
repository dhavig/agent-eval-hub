from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any]


@dataclass
class AgentResponse:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    raw: Any = None


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict[str, Any]


class Adapter(ABC):
    provider: str = "base"

    def __init__(self, model: str):
        self.model = model

    @abstractmethod
    def complete(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[Tool] | None = None,
        temperature: float = 0.0,
    ) -> AgentResponse: ...
