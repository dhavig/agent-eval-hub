"""Adapter contract tests.

Every registered LLM adapter class must:
  1. Subclass the Adapter ABC
  2. Have a `provider` class attribute matching its registry name
  3. Expose `.complete(system, messages, tools, temperature)`

These are STATIC checks on the class — no SDK import, no network, no env vars.
The lazy-import pattern means attempting to instantiate here would pull in each
provider's SDK, which is the opposite of what a fast unit-level contract test
should require. Integration and live-provider tests handle instantiation
behavior in their own tiers.
"""
from __future__ import annotations

import importlib
import inspect

import pytest

from agent_eval_hub.adapters import KNOWN_PROVIDERS
from agent_eval_hub.adapters.base import Adapter

# (registry_name) -> (module, class) — mirrors get_adapter's dispatch.
_PROVIDER_CLASSES = {
    "claude": ("agent_eval_hub.adapters.claude", "ClaudeAdapter"),
    "openai": ("agent_eval_hub.adapters.openai_adapter", "OpenAIAdapter"),
    "gemini": ("agent_eval_hub.adapters.gemini", "GeminiAdapter"),
    "ollama": ("agent_eval_hub.adapters.ollama", "OllamaAdapter"),
    "device": ("agent_eval_hub.adapters.device_ollama", "DeviceOllamaAdapter"),
}


def test_known_providers_matches_dispatch_table():
    """If someone adds a new KNOWN_PROVIDERS entry without updating get_adapter,
    this catches it. Otherwise the registry and dispatcher drift silently."""
    assert set(KNOWN_PROVIDERS) == set(_PROVIDER_CLASSES), (
        "KNOWN_PROVIDERS and _PROVIDER_CLASSES are out of sync. "
        "Every registered provider needs a class mapping here."
    )


def _load_class(provider: str):
    module_name, class_name = _PROVIDER_CLASSES[provider]
    try:
        mod = importlib.import_module(module_name)
    except BaseException as exc:  # includes PanicException from broken pyo3 builds
        pytest.skip(f"{provider} SDK unavailable in this env: {type(exc).__name__}")
    return getattr(mod, class_name)


@pytest.mark.parametrize("provider", KNOWN_PROVIDERS)
def test_class_subclasses_adapter(provider: str):
    cls = _load_class(provider)
    assert issubclass(cls, Adapter), f"{cls.__name__} must subclass Adapter"


@pytest.mark.parametrize("provider", KNOWN_PROVIDERS)
def test_provider_attribute_matches_registry(provider: str):
    cls = _load_class(provider)
    assert cls.provider == provider, (
        f"{cls.__name__}.provider = {cls.provider!r} but registered under {provider!r}"
    )


@pytest.mark.parametrize("provider", KNOWN_PROVIDERS)
def test_complete_signature(provider: str):
    cls = _load_class(provider)
    sig = inspect.signature(cls.complete)
    for required in ("system", "messages", "tools", "temperature"):
        assert required in sig.parameters, f"{cls.__name__}.complete() missing '{required}'"
