# AgentEvalHub

Multi-provider reliability harness for AI agents. Run the same agent spec against Claude, OpenAI, and (soon) Gemini / local models. Score every run on task success, tool-call correctness, cost, latency, and regression over time.

Built as a QA portfolio project for the agentic-AI era.

---

## Why this exists

Single-prompt LLM testing is becoming commoditized. What companies in 2026+ actually need help with is testing **autonomous agents**: multi-step tool use, safety under adversarial input, and silent drift when vendors update models. This repo is a minimal, honest take on that problem.

---

## Quick start

```bash
git clone <your-repo-url>
cd agent-eval-hub
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# fill in ANTHROPIC_API_KEY, OPENAI_API_KEY, and/or GEMINI_API_KEY
export $(cat .env | xargs)

# run the same suite against two providers
python -m runner.run_suite --suite suites/tool_use.yaml --provider claude --model claude-sonnet-4-6
python -m runner.run_suite --suite suites/tool_use.yaml --provider openai --model gpt-4o-mini

# run unit tests for the harness itself
pytest -q
```

Exit code is non-zero if any task fails, so this script drops straight into CI as a deploy gate.

---

## Layout

```
adapters/   one file per LLM provider, all conforming to the same contract
devices/    one file per device backend (mock/adb/Appium), same ABC pattern
suites/     YAML task definitions (tools, prompts, expected graders)
graders/    deterministic + LLM-as-judge + cross-surface consistency
runner/     agent loop + suite runner + scorer + cross-surface runner
storage/    DuckDB run history + divergence log
dashboard/  Streamlit drift + divergence UI
tests/      pytest tests for the harness's own code
.github/    CI workflow that runs the suite on every PR
```

---

## Current scope (Modules 1 + 2 + 3 + 4 + 5 — complete)

- [x] Provider-agnostic adapter layer (Claude, OpenAI, Gemini, Ollama — Ollama is local and free)
- [x] YAML-defined task suites with mocked tool results
- [x] Deterministic graders: `contains_all`, `regex_match`, `tool_called`, `no_error`
- [x] **LLM-as-judge grader wired into the YAML dispatcher with per-task rubrics**
- [x] **RAG grounding suite** — 4 tasks covering grounded answers, refusal on missing context, hallucination resistance on adjacent passages, and multi-passage synthesis
- [x] CI workflow that runs evals on every PR
- [x] Red-team suite — 5 attack scenarios: indirect prompt injection, system prompt leak, exfiltration via tool args, goal hijacking, harmful-content refusal
- [x] Safety graders — `refused`, `did_not_contain`, `did_not_call_tool`
- [x] Run history — DuckDB-backed persistence of every run + per-task trace
- [x] Drift detection — `find_regressions` SQL: PASS -> FAIL vs previous run
- [x] Streamlit dashboard — pass-rate + token trends, regressions table
- [x] Weekly drift GitHub Action — scheduled cron, auto-opens issue on regression
- [x] **Device adapter layer — same ABC pattern extended to Android surfaces (mock / adb / Appium)**
- [x] **Device-aware suite** (`suites/device_ui.yaml`) with `device_state` grader asserting physical side-effects
- [x] **Cross-surface consistency runner** — run the same task against two surfaces (cloud vs. device) and flag divergent answers
- [x] **Divergence log + dashboard panel** — "tasks where the phone disagreed with the PC"

### Running the RAG suite with an LLM judge

```bash
python -m runner.run_suite \
  --suite suites/rag_qa.yaml \
  --provider openai --model gpt-4o-mini \
  --judge-provider claude --judge-model claude-opus-4-7 \
  --db runs.duckdb
```

Use a stronger model as judge than the one under test — otherwise the test-taker grades their own exam.

### Running a suite with persistence

```bash
python -m runner.run_suite \
  --suite suites/red_team.yaml \
  --provider claude --model claude-sonnet-4-6 \
  --db runs.duckdb \
  --git-sha $(git rev-parse HEAD)
```

Exit codes:
- `0` — all tasks passed
- `1` — at least one task failed
- `2` — drift detected (task regressed from PASS to FAIL vs previous run)

### Launching the dashboard

```bash
streamlit run dashboard/app.py -- --db runs.duckdb
```

Shows pass-rate trend, token usage trend, current regressions, and the last 20 runs.

### Trying the dashboard without API keys

Seed a synthetic DB with 8 weeks of fake runs including one injected regression:

```bash
python -m dashboard.seed_demo --db demo.duckdb
streamlit run dashboard/app.py -- --db demo.duckdb
# -> pick suite=red_team, provider=openai to see the drift
```

### Weekly drift check

`.github/workflows/drift-weekly.yml` runs every Monday 13:00 UTC against each pinned `(provider, model)` pair across all suites. On drift (exit code 2) it auto-opens a labeled GitHub issue.

**v1 limitation:** the run DB is stored via `actions/cache` which evicts after 7 days of inactivity. For production, swap this for S3 or hosted Postgres.

---

## Module 5 — Cross-device consistency

The core QA problem for a cross-device AI assistant (e.g. Lenovo Qira, Apple
Intelligence, Google's cross-surface assistants) is **answer consistency across
surfaces**. A user asking "what's on my calendar?" on a phone and on a PC
expects the same answer. When the on-device model and the cloud model drift
apart, you get inconsistent behavior — and today nobody's testing for it.

Module 5 adds three pieces:

1. **Device adapter layer (`devices/`)** — a `DeviceAdapter` ABC with three backends:
   - `mock_android` — fixture-driven, CI-friendly (no emulator required)
   - `adb_android` — shells out to `adb` against a real device or emulator; raises `DeviceUnavailable` cleanly if adb isn't on PATH
   - `appium_android` — UI automation via Appium WebDriver (optional dep, same lazy-import pattern as LLM SDKs)
2. **Device-aware suite** (`suites/device_ui.yaml`) — tools like `launch_app`, `get_screen_text`, `list_packages` are routed through the device. A new grader `device_state` asserts on the physical result (e.g. `current_app == com.example.weather`), not just that the tool call happened.
3. **Cross-surface runner** (`runner/run_cross_surface.py`) — runs the same suite against two surfaces (e.g. cloud Claude + on-device Ollama), scores token-set Jaccard agreement per task, flags divergences, and records them to DuckDB. The Streamlit dashboard gains a "Cross-surface divergences" panel.

### Running the device suite (no phone needed)

```bash
python -m runner.run_suite \
  --suite suites/device_ui.yaml \
  --provider claude --model claude-sonnet-4-6
```

The suite declares `device: {backend: mock_android, fixture: devices/fixtures/basic_ui.json}`,
so every tool call resolves through the fixture instead of an API or a device.

### Running the device suite against a real emulator

```bash
# 1. start an emulator (one-time setup)
sdkmanager "system-images;android-34;google_apis;x86_64"
avdmanager create avd -n eval-hub -k "system-images;android-34;google_apis;x86_64"
emulator -avd eval-hub -no-window &

# 2. wait for it to be ready
adb wait-for-device

# 3. swap the backend — one-line change in the suite's `device:` block
#    device: {backend: adb_android}
python -m runner.run_suite --suite suites/device_ui.yaml --provider claude --model claude-sonnet-4-6
```

### Running a cross-surface consistency check

```bash
python -m runner.run_cross_surface \
  --suite suites/tool_use.yaml \
  --surface-a claude:claude-sonnet-4-6 \
  --surface-b ollama:llama3.1 \
  --threshold 0.5 \
  --db runs.duckdb
```

Exit codes:
- `0` — every task agrees above threshold
- `1` — at least one task diverged (divergences logged to DuckDB when `--db` is passed)

Open the dashboard to see the divergence panel:

```bash
streamlit run dashboard/app.py -- --db runs.duckdb
```

---

## Adding a new task

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

---

## Adding a new provider

1. Create `adapters/<name>.py` subclassing `Adapter`
2. Register it in `adapters/__init__.py`
3. That's it — existing suites run against it unchanged

---

## Adding a new device backend

Same pattern, parallel module:

1. Create `devices/<name>.py` subclassing `DeviceAdapter`
2. Register it in `devices/__init__.py` (lazy-imported so missing SDKs only break their own backend)
3. Swap the `device: {backend: <name>}` line in any suite — no harness change
