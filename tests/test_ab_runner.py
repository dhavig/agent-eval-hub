"""A/B runner + McNemar's test."""
from __future__ import annotations

import pytest

from agent_eval_hub.runner.run_ab import mcnemar_exact_p


def test_mcnemar_returns_none_when_too_few_discordants():
    assert mcnemar_exact_p(1, 1) is None
    assert mcnemar_exact_p(2, 2) is None
    assert mcnemar_exact_p(3, 1) is None  # 4 total, still too few


def test_mcnemar_small_but_usable():
    p = mcnemar_exact_p(3, 2)
    assert p is not None and 0 < p <= 1


def test_mcnemar_lopsided_is_significant():
    """10 tasks where A passed but B failed, 0 the other way → clear win for A."""
    p = mcnemar_exact_p(10, 0)
    assert p is not None and p < 0.01


def test_mcnemar_balanced_is_not_significant():
    """Equal disagreement both directions → no signal."""
    p = mcnemar_exact_p(6, 6)
    assert p is not None and p > 0.5


def test_mcnemar_capped_at_one():
    """Two-sided p must not exceed 1 even when k is equal to n/2."""
    p = mcnemar_exact_p(4, 4)
    assert p is None or p <= 1.0
