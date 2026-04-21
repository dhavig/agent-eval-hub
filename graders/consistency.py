from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ConsistencyResult:
    name: str
    passed: bool
    similarity: float
    threshold: float
    detail: str = ""


_TOKEN = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    return set(_TOKEN.findall(text.lower()))


def jaccard(a: str, b: str) -> float:
    """Token-set Jaccard. Cheap, deterministic, no embedding call required.

    Good enough for cross-surface answer agreement on short replies. For subtler
    cases, pair with an llm_judge consistency rubric (the judge grader can take
    both answers and decide "same meaning?" — out of scope for this module)."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def cross_surface_consistency(
    text_a: str,
    text_b: str,
    threshold: float = 0.5,
    label_a: str = "A",
    label_b: str = "B",
) -> ConsistencyResult:
    """Pass when two surfaces' final answers are sufficiently similar.

    The core QA signal for cross-device AI: does the phone give the same answer
    as the PC? If not, your users see inconsistent behavior across surfaces."""
    sim = jaccard(text_a, text_b)
    return ConsistencyResult(
        name="cross_surface_consistency",
        passed=sim >= threshold,
        similarity=sim,
        threshold=threshold,
        detail=f"{label_a} vs {label_b}: jaccard={sim:.2f} (threshold={threshold:.2f})",
    )
