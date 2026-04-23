"""Cross-surface safety parity.

Red-team prompts typed into a cross-device assistant must refuse on *every*
surface — a cloud refusal plus an on-device compliance is a real shipping risk.
This CLI runs the safety suite against two surfaces and flags any task where
one surface refused and the other didn't.

Exit codes:
    0 — every task has matching refusal behavior across both surfaces
    1 — at least one surface mismatched (safety parity broken)
"""
from __future__ import annotations

import argparse
from pathlib import Path

from agent_eval_hub.graders.deterministic import refused
from agent_eval_hub.logging import get_logger
from agent_eval_hub.runner.run_suite import run_suite

log = get_logger(__name__)


def _parse_surface(spec: str) -> tuple[str, str]:
    p, m = spec.split(":", 1)
    return p, m


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", required=True, type=Path, help="Usually suites/safety/red_team.yaml")
    parser.add_argument("--surface-a", required=True)
    parser.add_argument("--surface-b", required=True)
    args = parser.parse_args()

    pa, ma = _parse_surface(args.surface_a)
    pb, mb = _parse_surface(args.surface_b)

    log.info("safety-parity: surface A = %s:%s", pa, ma)
    rep_a = run_suite(args.suite, pa, ma)
    log.info("safety-parity: surface B = %s:%s", pb, mb)
    rep_b = run_suite(args.suite, pb, mb)

    by_a = {s.task_id: s for s in rep_a.scores}
    by_b = {s.task_id: s for s in rep_b.scores}
    common = sorted(set(by_a) & set(by_b))

    mismatches: list[dict] = []
    for tid in common:
        ta, tb = by_a[tid].trace, by_b[tid].trace
        if ta is None or tb is None:
            continue
        ref_a = refused(ta).passed
        ref_b = refused(tb).passed
        if ref_a != ref_b:
            mismatches.append({
                "task_id": tid,
                "surface_a_refused": ref_a,
                "surface_b_refused": ref_b,
                "answer_a": ta.final_text[:200],
                "answer_b": tb.final_text[:200],
            })

    log.info("=== safety parity ===")
    log.info("  tasks compared: %d", len(common))
    log.info("  mismatches: %d", len(mismatches))
    for m in mismatches:
        log.warning(
            "  %s: A refused=%s  B refused=%s",
            m["task_id"], m["surface_a_refused"], m["surface_b_refused"],
        )

    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
