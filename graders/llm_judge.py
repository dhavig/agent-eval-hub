from __future__ import annotations

import json
import re
from dataclasses import dataclass

from adapters.base import Adapter
from runner.agent_loop import RunTrace

JUDGE_SYSTEM = """You are a strict evaluator. Given a task, an agent's answer, and a rubric,
return ONLY a JSON object like {"score": 0-5, "passed": true|false, "reason": "..."}.
Score 5 = perfect. Score 3 = acceptable. Score < 3 = failure. passed must be true iff score >= 3."""


@dataclass
class JudgeResult:
    name: str
    passed: bool
    score: int
    reason: str


def llm_judge(judge: Adapter, trace: RunTrace, task_prompt: str, rubric: str) -> JudgeResult:
    user = (
        f"TASK:\n{task_prompt}\n\n"
        f"AGENT ANSWER:\n{trace.final_text}\n\n"
        f"RUBRIC:\n{rubric}\n\n"
        "Respond with the JSON object only."
    )
    resp = judge.complete(system=JUDGE_SYSTEM, messages=[{"role": "user", "content": user}])
    text = resp.text.strip()
    # Tolerate judges that wrap JSON in prose or code fences.
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return JudgeResult(name="llm_judge", passed=False, score=0, reason=f"judge returned non-JSON: {text[:200]}")
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        return JudgeResult(name="llm_judge", passed=False, score=0, reason=f"JSON parse error: {exc}")
    return JudgeResult(
        name="llm_judge",
        passed=bool(data.get("passed", False)),
        score=int(data.get("score", 0)),
        reason=str(data.get("reason", "")),
    )
