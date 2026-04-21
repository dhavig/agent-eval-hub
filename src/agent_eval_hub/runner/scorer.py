from __future__ import annotations

from dataclasses import dataclass, field

from agent_eval_hub.graders.deterministic import GradeResult
from agent_eval_hub.graders.llm_judge import JudgeResult
from agent_eval_hub.logging import get_logger
from agent_eval_hub.pricing import cost_per_successful_task, estimate_cost
from agent_eval_hub.runner.agent_loop import RunTrace

log = get_logger(__name__)


@dataclass
class TaskScore:
    task_id: str
    provider: str
    model: str
    passed: bool
    grades: list[GradeResult | JudgeResult] = field(default_factory=list)
    trace: RunTrace | None = None

    @property
    def cost_usd(self) -> float:
        if self.trace is None:
            return 0.0
        return estimate_cost(self.model, self.trace.input_tokens, self.trace.output_tokens)


@dataclass
class SuiteReport:
    suite: str
    scores: list[TaskScore]
    suite_version: int | None = None

    @property
    def pass_rate(self) -> float:
        return sum(1 for s in self.scores if s.passed) / len(self.scores) if self.scores else 0.0

    @property
    def tasks_passed(self) -> int:
        return sum(1 for s in self.scores if s.passed)

    @property
    def total_input_tokens(self) -> int:
        return sum(s.trace.input_tokens for s in self.scores if s.trace)

    @property
    def total_output_tokens(self) -> int:
        return sum(s.trace.output_tokens for s in self.scores if s.trace)

    @property
    def total_cost_usd(self) -> float:
        return sum(s.cost_usd for s in self.scores)

    @property
    def cost_per_successful_task_usd(self) -> float | None:
        return cost_per_successful_task(self.total_cost_usd, self.tasks_passed)

    def print_summary(self) -> None:
        log.info("=== %s ===", self.suite)
        for s in self.scores:
            mark = "PASS" if s.passed else "FAIL"
            log.info("  [%s] %s (%s/%s)", mark, s.task_id, s.provider, s.model)
            for g in s.grades:
                gm = "ok" if g.passed else "x "
                detail = g.detail if hasattr(g, "detail") else getattr(g, "reason", "")
                log.info("      %s %s: %s", gm, g.name, detail)
        cps = self.cost_per_successful_task_usd
        cps_str = f"${cps:.5f}" if cps is not None else "n/a"
        log.info(
            "  pass_rate=%.0f%%  tokens_in=%d  tokens_out=%d  cost=$%.5f  $/pass=%s",
            self.pass_rate * 100,
            self.total_input_tokens,
            self.total_output_tokens,
            self.total_cost_usd,
            cps_str,
        )
