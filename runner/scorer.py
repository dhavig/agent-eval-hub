from __future__ import annotations

from dataclasses import dataclass, field

from graders.deterministic import GradeResult
from graders.llm_judge import JudgeResult
from runner.agent_loop import RunTrace


@dataclass
class TaskScore:
    task_id: str
    provider: str
    model: str
    passed: bool
    grades: list[GradeResult | JudgeResult] = field(default_factory=list)
    trace: RunTrace | None = None


@dataclass
class SuiteReport:
    suite: str
    scores: list[TaskScore]

    @property
    def pass_rate(self) -> float:
        return sum(1 for s in self.scores if s.passed) / len(self.scores) if self.scores else 0.0

    @property
    def total_input_tokens(self) -> int:
        return sum(s.trace.input_tokens for s in self.scores if s.trace)

    @property
    def total_output_tokens(self) -> int:
        return sum(s.trace.output_tokens for s in self.scores if s.trace)

    def print_summary(self) -> None:
        print(f"\n=== {self.suite} ===")
        for s in self.scores:
            mark = "PASS" if s.passed else "FAIL"
            print(f"  [{mark}] {s.task_id} ({s.provider}/{s.model})")
            for g in s.grades:
                gm = "ok " if g.passed else "x  "
                print(f"      {gm} {g.name}: {g.detail if hasattr(g, 'detail') else g.reason}")
        print(f"  pass_rate={self.pass_rate:.0%}  tokens_in={self.total_input_tokens}  tokens_out={self.total_output_tokens}")
