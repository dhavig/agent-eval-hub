"""Cross-surface consistency runner.

Runs the same suite against two surfaces (e.g. a cloud Claude + a device Ollama)
and flags tasks where the two answers diverge. This is the core QA question for
cross-device AI: does the phone's answer match the PC's answer?

Exit codes:
    0 — all tasks agree within threshold
    1 — at least one task diverged
"""
from __future__ import annotations

import argparse
from pathlib import Path

from agent_eval_hub.graders.consistency import cross_surface_consistency
from agent_eval_hub.runner.run_suite import run_suite


def parse_surface(spec: str) -> tuple[str, str]:
    """`provider:model` -> (provider, model)."""
    if ":" not in spec:
        raise SystemExit(f"--surface-a/--surface-b must be provider:model, got {spec!r}")
    provider, model = spec.split(":", 1)
    return provider, model


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", required=True, type=Path)
    parser.add_argument("--surface-a", required=True, help="provider:model (e.g. claude:claude-sonnet-4-6)")
    parser.add_argument("--surface-b", required=True, help="provider:model (e.g. ollama:llama3.1)")
    parser.add_argument("--threshold", type=float, default=0.5, help="Jaccard threshold (0..1)")
    parser.add_argument("--db", type=Path, help="Optional DuckDB path to persist the divergence report")
    args = parser.parse_args()

    prov_a, model_a = parse_surface(args.surface_a)
    prov_b, model_b = parse_surface(args.surface_b)

    print(f"Running {args.suite.name} against surface A = {prov_a}:{model_a}")
    report_a = run_suite(args.suite, prov_a, model_a)
    print(f"Running {args.suite.name} against surface B = {prov_b}:{model_b}")
    report_b = run_suite(args.suite, prov_b, model_b)

    scores_a = {s.task_id: s for s in report_a.scores}
    scores_b = {s.task_id: s for s in report_b.scores}
    common = [tid for tid in scores_a if tid in scores_b]

    divergences = []
    print(f"\n=== cross-surface consistency ({len(common)} tasks) ===")
    for tid in common:
        a = scores_a[tid].trace.final_text if scores_a[tid].trace else ""
        b = scores_b[tid].trace.final_text if scores_b[tid].trace else ""
        r = cross_surface_consistency(a, b, threshold=args.threshold, label_a=prov_a, label_b=prov_b)
        mark = "ok " if r.passed else "x  "
        print(f"  {mark} {tid}: similarity={r.similarity:.2f}")
        if not r.passed:
            divergences.append({
                "task_id": tid,
                "similarity": r.similarity,
                "surface_a": prov_a,
                "surface_b": prov_b,
                "answer_a": a,
                "answer_b": b,
            })

    print(f"\n  divergent: {len(divergences)}/{len(common)} (threshold={args.threshold})")

    if args.db and divergences:
        from agent_eval_hub.storage.duckdb import connect, record_divergences
        con = connect(args.db)
        record_divergences(con, suite=report_a.suite, divergences=divergences)
        con.close()
        print(f"  recorded {len(divergences)} divergence(s) to {args.db}")

    return 1 if divergences else 0


if __name__ == "__main__":
    raise SystemExit(main())
