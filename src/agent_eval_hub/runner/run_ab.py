"""A/B runner with a proper statistical significance test.

Runs the same suite twice — once under surface A, once under surface B — and
asks "is B meaningfully better than A?" via McNemar's test on paired pass/fail
outcomes. Beats naive "compare pass rates" because two runs of the same model
can disagree on *different* tasks; McNemar's accounts for exactly that.

Exit codes:
    0 — B not worse than A (or indistinguishable)
    1 — A won (B regressed)
    2 — inconclusive (not enough disagreements to run the test)
"""
from __future__ import annotations

import argparse
from math import comb
from pathlib import Path

from agent_eval_hub.logging import get_logger
from agent_eval_hub.runner.run_suite import run_suite

log = get_logger(__name__)


def _parse_surface(spec: str) -> tuple[str, str]:
    if ":" not in spec:
        raise SystemExit(f"Surface spec must be provider:model, got {spec!r}")
    p, m = spec.split(":", 1)
    return p, m


def mcnemar_exact_p(b: int, c: int) -> float | None:
    """Exact two-sided McNemar p-value using the binomial distribution.

    b = A passed, B failed (discordant pair favoring A)
    c = A failed, B passed (discordant pair favoring B)
    Returns None if b + c < 5 (test unreliable — use sign test / more runs).
    """
    n = b + c
    if n < 5:
        return None
    k = min(b, c)
    # Two-sided: P(X <= k) + P(X >= n-k) under H0 p=0.5
    tail = sum(comb(n, i) for i in range(k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", required=True, type=Path)
    parser.add_argument("--surface-a", required=True, help="baseline provider:model")
    parser.add_argument("--surface-b", required=True, help="challenger provider:model")
    parser.add_argument("--alpha", type=float, default=0.05, help="significance threshold")
    args = parser.parse_args()

    pa, ma = _parse_surface(args.surface_a)
    pb, mb = _parse_surface(args.surface_b)

    log.info("A/B: surface A = %s:%s", pa, ma)
    rep_a = run_suite(args.suite, pa, ma)
    log.info("A/B: surface B = %s:%s", pb, mb)
    rep_b = run_suite(args.suite, pb, mb)

    by_a = {s.task_id: s for s in rep_a.scores}
    by_b = {s.task_id: s for s in rep_b.scores}
    common = sorted(set(by_a) & set(by_b))

    a_only = b_only = both_pass = both_fail = 0
    for tid in common:
        pa_ok = by_a[tid].passed
        pb_ok = by_b[tid].passed
        if pa_ok and not pb_ok:
            a_only += 1
        elif pb_ok and not pa_ok:
            b_only += 1
        elif pa_ok and pb_ok:
            both_pass += 1
        else:
            both_fail += 1

    pval = mcnemar_exact_p(a_only, b_only)
    pass_rate_a = rep_a.pass_rate
    pass_rate_b = rep_b.pass_rate
    cost_a = rep_a.total_cost_usd
    cost_b = rep_b.total_cost_usd
    cps_a = rep_a.cost_per_successful_task_usd
    cps_b = rep_b.cost_per_successful_task_usd

    log.info("=== A/B result ===")
    log.info("  A (%s:%s): pass_rate=%.0f%%  cost=$%.5f  $/pass=%s",
             pa, ma, pass_rate_a * 100, cost_a, f"${cps_a:.5f}" if cps_a else "n/a")
    log.info("  B (%s:%s): pass_rate=%.0f%%  cost=$%.5f  $/pass=%s",
             pb, mb, pass_rate_b * 100, cost_b, f"${cps_b:.5f}" if cps_b else "n/a")
    log.info("  discordant pairs: A-only=%d, B-only=%d   (concordant: both_pass=%d, both_fail=%d)",
             a_only, b_only, both_pass, both_fail)

    if pval is None:
        log.warning("  McNemar: inconclusive (too few discordant pairs; need %d+, had %d)",
                    5, a_only + b_only)
        return 2

    log.info("  McNemar exact p-value: %.4f (alpha=%.2f)", pval, args.alpha)
    if pval >= args.alpha:
        log.info("  VERDICT: no significant difference — B is not worse than A. Safe to swap.")
        return 0
    if b_only > a_only:
        log.info("  VERDICT: B significantly better than A.")
        return 0
    log.warning("  VERDICT: A significantly better than B (B regressed).")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
