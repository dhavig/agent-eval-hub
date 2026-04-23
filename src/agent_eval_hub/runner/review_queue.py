"""Human review CLI for the llm_judge_with_human fallback grader.

The `llm_judge_with_human` grader appends ambiguous cases to a JSONL queue.
This tool walks the queue interactively; a reviewer reads the rubric and the
agent answer, then types PASS / FAIL / SKIP. Decisions are written back to
the queue file so they aren't lost.

Not a web UI — deliberately a terminal tool so it runs over SSH and through
any review workflow (tmux, paste into a ticket, whatever).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agent_eval_hub.logging import get_logger

log = get_logger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, default=Path("review_queue.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("review_decisions.jsonl"))
    args = parser.parse_args()

    if not args.queue.exists():
        log.warning("No queue at %s — nothing to review.", args.queue)
        return 0

    items = [json.loads(line) for line in args.queue.read_text().splitlines() if line.strip()]
    log.info("Loaded %d pending items from %s", len(items), args.queue)

    decisions: list[dict] = []
    for i, item in enumerate(items, 1):
        print(f"\n=== [{i}/{len(items)}] ===")
        print(f"TASK PROMPT: {item.get('task_prompt', '')}")
        print(f"RUBRIC:      {item.get('rubric', '')}")
        print(f"JUDGE SAID:  {item.get('judge_reason', '')}")
        print(f"AGENT ANSWER:\n{item.get('agent_answer', '')}")
        print("Verdict? [p]ass / [f]ail / [s]kip: ", end="", flush=True)
        try:
            choice = sys.stdin.readline().strip().lower()
        except KeyboardInterrupt:
            print("\naborted, saving what we have")
            break
        if choice.startswith("p"):
            decisions.append({**item, "human_passed": True})
        elif choice.startswith("f"):
            decisions.append({**item, "human_passed": False})
        else:
            continue  # skip: leaves it in the queue for later

    with args.output.open("a") as f:
        for d in decisions:
            f.write(json.dumps(d) + "\n")
    log.info("Wrote %d decisions to %s", len(decisions), args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
