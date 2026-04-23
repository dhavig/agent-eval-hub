# Adding a new grader

1. Decide where it lives:
   - **`graders/deterministic.py`** — pass/fail on `final_text` or `tool_calls` alone
   - **`graders/device.py`** — reads `device_snapshot`
   - **`graders/consistency.py`** — similarity-based
   - **`graders/latency.py`** — perf / budget assertions
   - **`graders/llm_judge.py`** — requires a judge model
   - New file — when the concern is distinct enough (e.g. cost graders, safety parity graders)

2. Write the function:
   ```python
   from agent_eval_hub.graders.deterministic import GradeResult
   from agent_eval_hub.runner.agent_loop import RunTrace

   def my_grader(trace: RunTrace, some_config: str) -> GradeResult:
       return GradeResult(name="my_grader", passed=..., detail=...)
   ```

3. Register it in `build_graders(...)` in `src/agent_eval_hub/runner/run_suite.py`:
   ```python
   "my_grader": _wrap_det(lambda t, c: my_grader(t, c["some_config"])),
   ```

4. Use it from any suite:
   ```yaml
   graders:
     - type: my_grader
       some_config: "hello"
   ```

5. Write a test under `tests/` asserting both the true and false case with a constructed `RunTrace`.

## Design rules

- **One name, one responsibility.** `my_grader` should test exactly one thing. If the name has an "and" in it, split it into two graders.
- **Use `GradeResult(name=..., passed=..., detail=...)`** so the dashboard and scorer can show it consistently.
- **Negative assertions are first-class.** Safety and reliability testing needs "did NOT happen" graders (`did_not_contain`, `did_not_call_tool`). Don't invert a positive grader in YAML — write the explicit negative version.
- **Never require a judge unless the question genuinely needs one.** A judge grader means a paid API call per task.
