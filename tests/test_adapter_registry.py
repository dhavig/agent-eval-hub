from __future__ import annotations

import builtins
import importlib
import sys

import pytest

from agent_eval_hub.adapters import KNOWN_PROVIDERS, get_adapter


def test_known_providers_lists_all_four():
    assert set(KNOWN_PROVIDERS) == {"claude", "openai", "gemini", "ollama"}


def test_unknown_provider_raises():
    with pytest.raises(ValueError, match="Unknown provider"):
        get_adapter("cohere", "cmd-r")


def test_missing_gemini_sdk_does_not_break_other_providers(monkeypatch: pytest.MonkeyPatch):
    """Simulate a machine without google-genai installed. Claude/OpenAI should still resolve,
    and only get_adapter('gemini') should fail."""
    # Blow away any cached gemini module so the import runs fresh with our blocker in place.
    for mod in [m for m in list(sys.modules) if m.startswith("google") or m == "agent_eval_hub.adapters.gemini"]:
        monkeypatch.delitem(sys.modules, mod, raising=False)

    real_import = builtins.__import__

    def blocked_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "google" or name.startswith("google."):
            raise ImportError(f"simulated missing SDK: {name}")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", blocked_import)

    # Re-import the adapters package to pick up the fresh state.
    importlib.reload(sys.modules["agent_eval_hub.adapters"])
    from agent_eval_hub.adapters import get_adapter as fresh_get_adapter

    with pytest.raises(ImportError):
        fresh_get_adapter("gemini", "gemini-2.5-pro")
    # But the registry itself is still usable for other providers.
    # (We can't actually construct claude/openai here without their keys, but the import
    #  succeeding is what we're asserting — no top-level Gemini import took down the module.)
