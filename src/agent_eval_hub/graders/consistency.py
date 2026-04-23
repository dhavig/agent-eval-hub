"""Cross-surface answer consistency.

Two forms:
  - `cross_surface_consistency(text_a, text_b, ...)` — used by the cross-surface
    runner that already has two traces in hand.
  - `answer_similar_to(trace, reference, threshold)` — used directly from YAML
    suites: "the agent's answer must resemble this reference string."
Both share `jaccard()` as the underlying similarity metric.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from agent_eval_hub.graders.deterministic import GradeResult
from agent_eval_hub.runner.agent_loop import RunTrace


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
    cases, pair with an llm_judge consistency rubric."""
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


def answer_similar_to(trace: RunTrace, reference: str, threshold: float = 0.5) -> GradeResult:
    """Dispatchable grader: pass when the agent's final_text is similar enough
    to a reference string. Useful when a suite needs "fuzzy contains" rather
    than strict phrase matching.

    Expressible from YAML as:
        - type: answer_similar_to
          reference: "the weather in paris is 15c with light rain"
          threshold: 0.5
    """
    sim = jaccard(trace.final_text, reference)
    return GradeResult(
        name="answer_similar_to",
        passed=sim >= threshold,
        detail=f"jaccard={sim:.2f} vs reference (threshold={threshold:.2f})",
    )
