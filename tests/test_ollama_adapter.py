"""Ollama adapter tests using httpx.MockTransport — no live server needed."""
from __future__ import annotations

import json

import httpx
import pytest

from agent_eval_hub.adapters.base import Tool
from agent_eval_hub.adapters.ollama import OllamaAdapter


def _make_adapter(handler):
    """Build an OllamaAdapter that routes all requests through the given handler."""
    adapter = OllamaAdapter(model="llama3.1", base_url="http://stub")
    transport = httpx.MockTransport(handler)
    original_client = httpx.Client

    # Monkey-wrap httpx.Client to always use the mock transport when base_url matches.
    class _Client(original_client):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    return adapter, _Client


def test_returns_text_response(monkeypatch: pytest.MonkeyPatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        body = json.loads(request.content)
        assert body["model"] == "llama3.1"
        assert body["messages"][0]["role"] == "system"
        return httpx.Response(
            200,
            json={
                "message": {"role": "assistant", "content": "hello"},
                "prompt_eval_count": 12,
                "eval_count": 3,
            },
        )

    adapter, Client = _make_adapter(handler)
    monkeypatch.setattr(httpx, "Client", Client)

    resp = adapter.complete(system="be nice", messages=[{"role": "user", "content": "hi"}])
    assert resp.text == "hello"
    assert resp.input_tokens == 12
    assert resp.output_tokens == 3
    assert resp.tool_calls == []


def test_parses_tool_calls_with_dict_args(monkeypatch: pytest.MonkeyPatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {"function": {"name": "get_weather", "arguments": {"city": "Paris"}}}
                    ],
                },
                "prompt_eval_count": 5,
                "eval_count": 2,
            },
        )

    adapter, Client = _make_adapter(handler)
    monkeypatch.setattr(httpx, "Client", Client)

    tool = Tool(name="get_weather", description="weather", input_schema={"type": "object"})
    resp = adapter.complete(system="s", messages=[{"role": "user", "content": "weather"}], tools=[tool])
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].name == "get_weather"
    assert resp.tool_calls[0].arguments == {"city": "Paris"}


def test_parses_tool_calls_with_json_string_args(monkeypatch: pytest.MonkeyPatch):
    """Some Ollama models return arguments as a JSON-encoded string."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {
                    "tool_calls": [
                        {"function": {"name": "get_weather", "arguments": '{"city": "Paris"}'}}
                    ],
                },
            },
        )

    adapter, Client = _make_adapter(handler)
    monkeypatch.setattr(httpx, "Client", Client)

    resp = adapter.complete(system="s", messages=[{"role": "user", "content": "w"}])
    assert resp.tool_calls[0].arguments == {"city": "Paris"}


def test_handles_malformed_json_args_gracefully(monkeypatch: pytest.MonkeyPatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {
                    "tool_calls": [
                        {"function": {"name": "x", "arguments": "not json at all"}}
                    ],
                },
            },
        )

    adapter, Client = _make_adapter(handler)
    monkeypatch.setattr(httpx, "Client", Client)

    resp = adapter.complete(system="s", messages=[{"role": "user", "content": "x"}])
    # Rather than crash, we fall back to empty args — the grader will detect the bad call.
    assert resp.tool_calls[0].arguments == {}
