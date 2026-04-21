"""Per-model pricing — powers the `$/successful-task` metric.

Prices are in USD per 1M tokens (input, output). Numbers are rounded published
list prices — not contract prices. Override via env:
    AGENT_EVAL_PRICING_JSON=/path/to/prices.json

Returning (0, 0) for unknown models is deliberate: the harness keeps working,
cost columns show 0. `cost_per_successful_task` will gracefully degrade when
prices are missing — a silent 0 is preferable to crashing a CI run over a
pricing catalog lookup.
"""
from __future__ import annotations

import json
import os
from functools import cache

DEFAULT_PRICES: dict[str, tuple[float, float]] = {
    # Anthropic
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-opus-4-7": (15.00, 75.00),
    "claude-haiku-4-5-20251001": (1.00, 5.00),
    # OpenAI
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    # Gemini
    "gemini-2.5-pro": (1.25, 5.00),
    "gemini-2.5-flash": (0.075, 0.30),
    # Ollama (local) — zero marginal cost
    "llama3.1": (0.0, 0.0),
    "qwen2.5": (0.0, 0.0),
}


@cache
def _load_prices() -> dict[str, tuple[float, float]]:
    path = os.environ.get("AGENT_EVAL_PRICING_JSON")
    if path and os.path.exists(path):
        with open(path) as f:
            raw = json.load(f)
        return {k: (float(v[0]), float(v[1])) for k, v in raw.items()}
    return DEFAULT_PRICES


def price_per_1m(model: str) -> tuple[float, float]:
    """Return (input_price, output_price) in USD per 1M tokens."""
    return _load_prices().get(model, (0.0, 0.0))


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Return USD cost for a single run. Zero if pricing unknown."""
    p_in, p_out = price_per_1m(model)
    return (input_tokens * p_in + output_tokens * p_out) / 1_000_000.0


def cost_per_successful_task(
    total_cost_usd: float, tasks_passed: int
) -> float | None:
    """The flagship QE metric: how much does a successful task cost?

    None when no tasks passed (division by zero would hide that worse signal)."""
    if tasks_passed <= 0:
        return None
    return total_cost_usd / tasks_passed
