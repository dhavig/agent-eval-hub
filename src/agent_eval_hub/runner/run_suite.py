from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from agent_eval_hub.adapters import KNOWN_PROVIDERS, get_adapter
from agent_eval_hub.adapters.base import Adapter, Tool, ToolCall
from agent_eval_hub.devices import get_device
from agent_eval_hub.devices.base import DeviceAdapter
from agent_eval_hub.graders import consistency as cons
from agent_eval_hub.graders import deterministic as det
from agent_eval_hub.graders import device as dev
from agent_eval_hub.graders.llm_judge import llm_judge
from agent_eval_hub.runner.agent_loop import RunTrace, run_agent
from agent_eval_hub.runner.scorer import SuiteReport, TaskScore


def build_graders(judge: Adapter | None) -> dict[str, Callable[[RunTrace, dict, str], Any]]:
    """Build the grader dispatch table. `judge` is injected into llm_judge.
    Each entry takes (trace, cfg, task_prompt) and returns a GradeResult-like."""

    def _wrap_det(fn):
        return lambda trace, cfg, _prompt: fn(trace, cfg)

    def _llm_judge(trace: RunTrace, cfg: dict, task_prompt: str):
        if judge is None:
            raise RuntimeError(
                "llm_judge grader used but no judge provided. "
                "Pass --judge-provider and --judge-model."
            )
        return llm_judge(judge=judge, trace=trace, task_prompt=task_prompt, rubric=cfg["rubric"])

    return {
        "contains_all": _wrap_det(lambda t, c: det.contains_all(t, c["phrases"])),
        "regex_match": _wrap_det(lambda t, c: det.regex_match(t, c["pattern"])),
        "tool_called": _wrap_det(lambda t, c: det.tool_called(t, c["tool_name"], c.get("required_args"))),
        "no_error": _wrap_det(lambda t, c: det.no_error(t)),
        "refused": _wrap_det(lambda t, c: det.refused(t)),
        "did_not_contain": _wrap_det(lambda t, c: det.did_not_contain(t, c["forbidden"])),
        "did_not_call_tool": _wrap_det(
            lambda t, c: det.did_not_call_tool(t, c["tool_name"], c.get("forbidden_args"))
        ),
        "device_state": _wrap_det(lambda t, c: dev.device_state(t, c["key"], c.get("equals"))),
        "answer_similar_to": _wrap_det(
            lambda t, c: cons.answer_similar_to(t, c["reference"], c.get("threshold", 0.5))
        ),
        "llm_judge": _llm_judge,
    }


def build_tool_handlers(tool_results: dict[str, str]) -> dict[str, Any]:
    def make(_name: str, result: str):
        def handler(call: ToolCall) -> str:
            return result
        return handler
    return {name: make(name, result) for name, result in tool_results.items()}


def build_device_tool_handlers(device: DeviceAdapter, tool_names: list[str]) -> dict[str, Any]:
    """Each declared tool routes through the device's execute() method. The
    agent loop calls handler(ToolCall) -> str, so we translate + stringify."""
    def make(name: str):
        def handler(call: ToolCall) -> str:
            result = device.execute(name, call.arguments or {})
            status = "" if result.success else " [FAILED]"
            return f"{result.output}{status}"
        return handler
    return {name: make(name) for name in tool_names}


def build_device(device_cfg: dict) -> DeviceAdapter:
    backend = device_cfg["backend"]
    kwargs = {k: v for k, v in device_cfg.items() if k != "backend"}
    return get_device(backend, **kwargs)


def load_suite(path: Path) -> dict[str, Any]:
    with path.open() as f:
        return yaml.safe_load(f)


def run_suite(
    suite_path: Path,
    provider: str,
    model: str,
    judge: Adapter | None = None,
) -> SuiteReport:
    suite = load_suite(suite_path)
    adapter = get_adapter(provider, model)
    tools = [Tool(**t) for t in suite.get("tools", [])]
    graders = build_graders(judge)

    device: DeviceAdapter | None = None
    if "device" in suite:
        device = build_device(suite["device"])

    scores: list[TaskScore] = []
    try:
        for task in suite["tasks"]:
            if device is not None and not task.get("tool_results"):
                device.reset()
                handlers = build_device_tool_handlers(device, [t.name for t in tools])
            else:
                handlers = build_tool_handlers(task.get("tool_results", {}))

            trace = run_agent(
                adapter=adapter,
                task_id=task["id"],
                system=task["system"],
                user_prompt=task["user"],
                tools=tools,
                tool_handlers=handlers,
            )
            if device is not None:
                trace.device_snapshot = device.snapshot()

            grade_results = [graders[g["type"]](trace, g, task["user"]) for g in task["graders"]]
            scores.append(
                TaskScore(
                    task_id=task["id"],
                    provider=adapter.provider,
                    model=adapter.model,
                    passed=all(g.passed for g in grade_results),
                    grades=grade_results,
                    trace=trace,
                )
            )
    finally:
        if device is not None:
            device.close()

    return SuiteReport(suite=suite["name"], scores=scores)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", required=True, type=Path)
    parser.add_argument("--provider", required=True, choices=list(KNOWN_PROVIDERS))
    parser.add_argument("--model", required=True)
    parser.add_argument("--judge-provider", choices=list(KNOWN_PROVIDERS), default=None)
    parser.add_argument("--judge-model", default=None)
    parser.add_argument("--db", type=Path, help="Optional DuckDB path to persist the run")
    parser.add_argument("--git-sha", type=str, default=None)
    args = parser.parse_args()

    judge = None
    if args.judge_provider and args.judge_model:
        judge = get_adapter(args.judge_provider, args.judge_model)

    report = run_suite(args.suite, args.provider, args.model, judge=judge)
    report.print_summary()

    if args.db:
        from agent_eval_hub.storage.duckdb_store import connect, find_regressions, record_run
        con = connect(args.db)
        run_id = record_run(con, report, git_sha=args.git_sha)
        print(f"\nrecorded run_id={run_id} to {args.db}")
        regressions = find_regressions(con, report.suite, args.provider)
        if regressions:
            print(f"DRIFT DETECTED in {report.suite} ({args.provider}):")
            for r in regressions:
                print(f"  - {r['task_id']}: PASS -> FAIL")
        con.close()
        if regressions:
            return 2

    return 0 if report.pass_rate == 1.0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
