# AgentEvalHub

Multi-provider + cross-device reliability harness for AI agents. Run the same
agent spec against Claude, OpenAI, Gemini, Ollama — and against real or mocked
Android surfaces. Score every run on task success, tool-call correctness, safety
under attack, cost, latency, and regression over time.

Built as a QA portfolio project for the agentic-AI era.

---

## Why this exists

Single-prompt LLM testing is becoming commoditized. What companies in 2026+
actually need help with is testing **autonomous agents**: multi-step tool use,
safety under adversarial input, silent drift when vendors update models, and —
increasingly — whether the phone gives the same answer as the PC. This repo is
a minimal, honest take on that problem.

---

## Quick start

```bash
git clone <your-repo-url>
cd agent-eval-hub
python -m venv .venv && source .venv/bin/activate

# Install the package + dev tools (pytest, ruff, mypy, pre-commit, detect-secrets)
pip install -e .[dev]

cp .env.example .env
# fill in ANTHROPIC_API_KEY, OPENAI_API_KEY, and/or GEMINI_API_KEY
export $(cat .env | xargs)

# Run the same suite against two providers
agent-eval --suite suites/tool_use.yaml --provider claude --model claude-sonnet-4-6
agent-eval --suite suites/tool_use.yaml --provider openai --model gpt-4o-mini

# Or the module form (identical):
python -m agent_eval_hub.runner.run_suite --suite suites/tool_use.yaml --provider claude --model claude-sonnet-4-6

# Run the harness's own unit tests
pytest
```

Exit code is non-zero if any task fails, so this script drops straight into CI
as a deploy gate.

---

## Layout

```
pyproject.toml                 packaging, pytest markers, ruff + mypy config
.pre-commit-config.yaml        ruff + detect-secrets + fast-test hooks
.secrets.baseline              detect-secrets baseline

src/agent_eval_hub/
  adapters/                    one file per LLM provider (Claude/OpenAI/Gemini/Ollama)
  devices/                     one file per device backend (mock/adb/Appium Android)
  graders/
    deterministic.py           contains_all, regex_match, tool_called, refused, ...
    device.py                  device_state (snapshot-based assertions)
    consistency.py             jaccard + answer_similar_to (dispatchable)
    llm_judge.py               JSON-constrained judge with defensive parsing
  runner/
    agent_loop.py              multi-turn tool-use loop
    scorer.py                  SuiteReport + TaskScore
    run_suite.py               main CLI: eval a suite
    run_cross_surface.py       CLI: compare two surfaces for answer divergence
  storage/
    duckdb_store.py            run history + divergence log + find_regressions
  dashboard/
    app.py                     Streamlit UI
    seed_demo.py               fake 8-week run history for demos

suites/                        YAML task definitions
  tool_use.yaml                baseline agent tool-use
  rag_qa.yaml                  RAG grounding (uses llm_judge)
  red_team.yaml                5 adversarial attack classes
  device_ui.yaml               Android UI tasks (runs via device backend)

fixtures/                      test data (not shipped in the wheel)
  devices/basic_ui.json        canned action responses for mock_android

tests/
  conftest.py                  shared fixtures: ScriptedAdapter, tmp_db, mock_android_fixture
  test_*.py                    unit + integration (see pytest markers below)

.github/workflows/
  eval-on-pr.yml               fast tests + live provider evals (gated on secrets)
  drift-weekly.yml             cron drift check, auto-opens issue on regression
```

---

## Modules 1–5 — complete

- [x] Provider-agnostic adapter layer (Claude, OpenAI, Gemini, Ollama — Ollama is local and free)
- [x] YAML-defined task suites with mocked tool results
- [x] Deterministic graders: `contains_all`, `regex_match`, `tool_called`, `no_error`
- [x] LLM-as-judge grader wired into the YAML dispatcher with per-task rubrics
- [x] RAG grounding suite — grounded answers, refusal on missing context, hallucination resistance, multi-passage synthesis
- [x] Red-team suite — indirect prompt injection, system-prompt leak, exfiltration via tool args, goal hijacking, harmful-content refusal
- [x] Safety graders — `refused`, `did_not_contain`, `did_not_call_tool`
- [x] Run history — DuckDB-backed persistence of every run + per-task trace
- [x] Drift detection — `find_regressions` SQL: PASS → FAIL vs previous run
- [x] Streamlit dashboard — pass-rate + token trends, regressions table, divergence panel
- [x] Weekly drift GitHub Action — scheduled cron, auto-opens issue on regression
- [x] **Module 5 — Device adapter layer** (mock / adb / Appium Android), with `device_state` snapshot grader
- [x] **Module 5 — Cross-surface consistency** — same task against two surfaces, token-set Jaccard divergence, persisted + surfaced in the dashboard
- [x] **Module 5 — Structural cleanup** — `src/` layout, `pyproject.toml`, dispatchable `answer_similar_to` grader, `pytest` markers, pre-commit hooks

---

## Running a suite

```bash
# Any suite, any provider
agent-eval --suite suites/red_team.yaml --provider claude --model claude-sonnet-4-6

# With persistence (needed for drift detection)
agent-eval \
  --suite suites/red_team.yaml \
  --provider claude --model claude-sonnet-4-6 \
  --db runs.duckdb \
  --git-sha $(git rev-parse HEAD)

# RAG / judge-backed suites need a (stronger) judge model
agent-eval \
  --suite suites/rag_qa.yaml \
  --provider openai --model gpt-4o-mini \
  --judge-provider claude --judge-model claude-opus-4-7 \
  --db runs.duckdb
```

Exit codes:
- `0` — all tasks passed
- `1` — at least one task failed
- `2` — drift detected (task regressed from PASS → FAIL vs previous run)

---

## Cross-device consistency (Module 5)

The core QA problem for a cross-device AI assistant (Lenovo Qira, Apple
Intelligence, Google's cross-surface assistants) is **answer consistency across
surfaces**. A user asking "what's on my calendar?" on a phone and on a PC
expects the same answer. When the on-device model and the cloud model drift
apart, users see inconsistent behavior.

### Device suite without a phone

```bash
agent-eval --suite suites/device_ui.yaml --provider claude --model claude-sonnet-4-6
```

The suite declares `device: {backend: mock_android, fixture: fixtures/devices/basic_ui.json}`,
so every tool call resolves through the fixture instead of an API or a device.

### Device suite on a real emulator

```bash
# One-time emulator setup
sdkmanager "system-images;android-34;google_apis;x86_64"
avdmanager create avd -n eval-hub -k "system-images;android-34;google_apis;x86_64"
emulator -avd eval-hub -no-window &
adb wait-for-device

# Swap the backend — one-line change in the suite's `device:` block:
#   device: {backend: adb_android}
agent-eval --suite suites/device_ui.yaml --provider claude --model claude-sonnet-4-6
```

### Cross-surface consistency check

```bash
agent-eval-cross \
  --suite suites/tool_use.yaml \
  --surface-a claude:claude-sonnet-4-6 \
  --surface-b ollama:llama3.1 \
  --threshold 0.5 \
  --db runs.duckdb
```

Exit codes: `0` agree, `1` diverged. Divergences are logged to DuckDB and shown
in the dashboard's "Cross-surface divergences" panel.

---

## Dashboard

```bash
streamlit run src/agent_eval_hub/dashboard/app.py -- --db runs.duckdb
```

Shows pass-rate trend, token usage trend, current regressions, recent runs,
and cross-surface divergences.

### Trying the dashboard without API keys

Seed a synthetic DB with 8 weeks of fake runs + one injected regression:

```bash
agent-eval-seed --db demo.duckdb
streamlit run src/agent_eval_hub/dashboard/app.py -- --db demo.duckdb
# -> select suite=red_team, provider=openai to see the drift
```

---

## Testing

The harness has its own test suite. Markers let CI run tiers independently:

```bash
pytest                                                   # everything (52 tests)
pytest -m "not integration and not e2e and not device"   # fast unit tests only (47)
pytest -m integration                                    # end-to-end with stub adapters (5)
pytest -m e2e                                            # real-provider calls (not enabled yet)
pytest -m device                                         # real emulator/Appium (not enabled yet)
```

Shared fixtures live in `tests/conftest.py`:
- `scripted_adapter(responses)` — factory for a stub LLM that replays pre-baked responses
- `patch_get_adapter({provider: [responses]})` — swap `get_adapter` for a scripted adapter
- `tmp_db` — fresh DuckDB path per test
- `mock_android_fixture` — path to `fixtures/devices/basic_ui.json`

---

## Weekly drift check

`.github/workflows/drift-weekly.yml` runs every Monday 13:00 UTC against each
pinned `(provider, model)` pair across all suites. On drift (exit code 2) it
auto-opens a labeled GitHub issue.

**v1 limitation:** the run DB is stored via `actions/cache` which evicts after
7 days of inactivity. For production, swap this for S3 or hosted Postgres.

---

## Adding things

### A new task
Edit any file in `suites/`:

```yaml
- id: my_new_task
  system: You are a helpful assistant.
  user: What is the capital of France?
  tool_results: {}
  graders:
    - type: contains_all
      phrases: ["Paris"]
```

No code change required.

### A new provider
1. Create `src/agent_eval_hub/adapters/<name>.py` subclassing `Adapter`
2. Register it in `src/agent_eval_hub/adapters/__init__.py` (lazy-imported)
3. That's it — existing suites run against it unchanged

### A new device backend
1. Create `src/agent_eval_hub/devices/<name>.py` subclassing `DeviceAdapter`
2. Register it in `src/agent_eval_hub/devices/__init__.py`
3. Swap the `device: {backend: <name>}` line in any suite — no harness change

### A new grader
1. Add the function to the appropriate file under `src/agent_eval_hub/graders/`
   (deterministic / device / consistency / llm_judge)
2. Register it in the `build_graders(...)` dispatcher in
   `src/agent_eval_hub/runner/run_suite.py`
3. Use `type: <name>` in any suite

---

## Development workflow

```bash
# Install everything including dev tools
pip install -e .[dev]

# Enable pre-commit hooks (ruff, detect-secrets, trailing-whitespace, ...)
pre-commit install

# Lint + format
ruff check src tests
ruff format src tests

# Type-check (advisory — not strict yet)
mypy src

# Run fast tests
pytest -m "not integration"
```
