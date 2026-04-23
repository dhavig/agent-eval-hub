# Architecture

## Layering

```
CLI entrypoints        (agent-eval, agent-eval-cross, agent-eval-ab, ...)
    │
    ▼
Runner                 (run_suite, run_cross_surface, run_ab, run_safety_parity)
    │
    ▼
Grader dispatch        (deterministic + device + consistency + latency + judge)
    │                           │
    ▼                           ▼
Adapter layer        +   Device layer           (cloud LLMs)   /   (on-device surfaces)
    │                           │
    ▼                           ▼
Provider SDKs        +   adb / Appium / mock

Scorer → Storage (DuckDB / Postgres) → Dashboard (Streamlit)
```

## Module map

| Module | Responsibility |
|---|---|
| `adapters/` | LLM provider wrappers sharing one `Adapter` ABC. Lazy-imported. |
| `devices/` | Android device backends sharing one `DeviceAdapter` ABC. Lazy-imported. |
| `graders/` | Scoring functions grouped by concern: deterministic, device, consistency, latency, llm_judge, human_review. |
| `runner/` | Agent loop + suite runner + cross-surface + A/B + safety parity + review CLI. |
| `storage/` | `Store` ABC with DuckDB (default) and Postgres (skeleton) backends. |
| `dashboard/` | Streamlit UI over the run history + divergences. |
| `pricing.py` | Per-model `$/1M token` catalog + `cost_per_successful_task` calculation. |
| `logging.py` | Structured logger — plain on TTY, JSON when piped. |

## Key design choices

- **Adapter + Device ABCs mirror each other.** Same lazy-import pattern, same narrow method surface. Adding a backend = one file + one registry entry.
- **Grader dispatch is a plain dict of `(trace, cfg, task_prompt) → GradeResult`.** No registration decorators, no plugin framework, no inheritance tree.
- **Suite versions live in YAML, get recorded to DB.** Lets dashboards distinguish "the suite changed" from "the model drifted."
- **Tri-state CLI exit code** (`0` pass / `1` fail / `2` drift). Drift is a first-class signal, not a log line.
- **Cost is computed from token counts + a pricing catalog.** The catalog is overridable via env, so private contracts can be modeled without patching code.
- **Human-in-the-loop grader wraps the LLM judge** rather than replacing it — if the judge is confident, it decides; if not, the case queues for a reviewer.

## Surfaces that matter for cross-device AI

The project exists because a cross-device assistant has multiple axes of drift:
1. Model version drift within one surface (solved by `find_regressions`)
2. Cost/token drift within one surface (solved by `find_token_regressions`)
3. Answer agreement across surfaces (solved by `run_cross_surface`)
4. Safety agreement across surfaces (solved by `run_safety_parity`)
5. Latency SLO violations on device (solved by the `latency_under` grader)

Each is a different SQL query or CLI, but they all consume the same trace shape.
