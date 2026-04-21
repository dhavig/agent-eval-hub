"""Pricing + cost-per-successful-task — the flagship QE metric."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_eval_hub import pricing


def test_known_model_has_pricing():
    p_in, p_out = pricing.price_per_1m("claude-sonnet-4-6")
    assert p_in > 0 and p_out > 0


def test_unknown_model_is_zero_not_error():
    """Zero > crash: harness must keep working on a model we haven't priced."""
    assert pricing.price_per_1m("future-model-xyz") == (0.0, 0.0)


def test_estimate_cost_scales_with_tokens():
    # 1M in + 1M out at ($3, $15) = $18
    assert pricing.estimate_cost("claude-sonnet-4-6", 1_000_000, 1_000_000) == pytest.approx(18.0)


def test_cost_per_successful_task_returns_none_when_nothing_passed():
    assert pricing.cost_per_successful_task(1.0, 0) is None


def test_cost_per_successful_task_divides_cleanly():
    assert pricing.cost_per_successful_task(6.0, 3) == 2.0


def test_env_override_loads_custom_prices(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    custom = tmp_path / "prices.json"
    custom.write_text(json.dumps({"my-model": [100.0, 200.0]}))
    monkeypatch.setenv("AGENT_EVAL_PRICING_JSON", str(custom))
    pricing._load_prices.cache_clear()
    try:
        assert pricing.price_per_1m("my-model") == (100.0, 200.0)
    finally:
        pricing._load_prices.cache_clear()
