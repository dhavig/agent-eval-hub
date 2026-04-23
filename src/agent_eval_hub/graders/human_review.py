"""Human-in-the-loop grader.

When the LLM judge is uncertain (score in the ambiguous middle band), the case
is queued to disk for a human to score later — instead of letting the judge
force a pass/fail it isn't confident about. The review CLI
(`agent-eval-review`) pulls cases from the queue.
"""
from __future__ import annotations

from pathlib import Path

from agent_eval_hub.adapters.base import Adapter
from agent_eval_hub.graders.llm_judge import JudgeResult, llm_judge
from agent_eval_hub.runner.agent_loop import RunTrace


def llm_judge_with_human_fallback(
    judge: Adapter,
    trace: RunTrace,
    task_prompt: str,
    rubric: str,
    uncertain_if_score_in: tuple[int, int] = (2, 3),
    queue_path: str | Path = "review_queue.jsonl",
) -> JudgeResult:
    """Run the LLM judge; if the score lands in the uncertain band, append the
    case to a JSONL queue for human review. Returns the judge's verdict for now
    (so CI isn't blocked), but flags `reason` so downstream can filter.

    The queue file is JSONL (one JSON object per line) — append-safe across
    concurrent workers, trivially inspectable with `jq`."""
    result = llm_judge(judge=judge, trace=trace, task_prompt=task_prompt, rubric=rubric)
    lo, hi = uncertain_if_score_in
    if lo <= result.score <= hi:
        _enqueue(queue_path, task_prompt, trace.final_text, rubric, result.reason)
        return JudgeResult(
            name="llm_judge",
            passed=result.passed,
            score=result.score,
            reason=f"[queued for human review] {result.reason}",
        )
    return result


def _enqueue(queue_path: str | Path, task_prompt: str, answer: str, rubric: str, reason: str) -> None:
    import json
    from datetime import datetime, timezone
    path = Path(queue_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "task_prompt": task_prompt,
        "agent_answer": answer,
        "rubric": rubric,
        "judge_reason": reason,
    }
    with path.open("a") as f:
        f.write(json.dumps(record) + "\n")
