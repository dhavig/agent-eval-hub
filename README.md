# AgentEvalHub

Multi-provider + cross-device reliability harness for AI agents. Runs the same
agent spec against Claude / OpenAI / Gemini / Ollama and against real or mocked
Android surfaces. Scores every run on task success, tool-call correctness,
safety under attack, cost, latency, and regression over time.

Built as a QA portfolio project for the agentic-AI era.

---

## Quick start

```bash
git clone <your-repo-url>
cd agent-eval-hub
python -m venv .venv && source .venv/bin/activate
pip install -e .[dev]

cp .env.example .env
# fill in ANTHROPIC_API_KEY, OPENAI_API_KEY, and/or GEMINI_API_KEY
export $(cat .env | xargs)

# Run the same suite against two providers
agent-eval --suite suites/agent/tool_use.yaml --provider claude --model claude-sonnet-4-6
agent-eval --suite suites/agent/tool_use.yaml --provider openai --model gpt-4o-mini

# Compare two surfaces for answer agreement
agent-eval-cross --suite suites/agent/tool_use.yaml \
  --surface-a claude:claude-sonnet-4-6 --surface-b ollama:llama3.1

# A/B test with statistical significance
agent-eval-ab --suite suites/safety/red_team.yaml \
  --surface-a claude:claude-sonnet-4-6 --surface-b claude:claude-haiku-4-5-20251001

# Cross-surface safety parity (refusal behavior must match)
agent-eval-safety-parity --suite suites/safety/red_team.yaml \
  --surface-a claude:claude-sonnet-4-6 --surface-b device:llama3.1

# Dashboard + synthetic demo data
agent-eval-seed --db demo.duckdb
streamlit run src/agent_eval_hub/dashboard/app.py -- --db demo.duckdb

# Tests
pytest                                         # everything local (93+ tests)
pytest -m "not integration and not e2e"        # fast unit tier
```

---

## Modules shipped

| Module | What |
|---|---|
| **1** | Provider-agnostic agent loop (Claude / OpenAI / Gemini / Ollama) |
| **2** | RAG grounding suite + LLM-as-judge with defensive JSON parsing |
| **3** | Red-team suite (5 attack classes) + safety graders (`refused`, `did_not_contain`, `did_not_call_tool`) |
| **4** | DuckDB run history, `find_regressions` SQL, Streamlit drift dashboard, weekly GitHub Action |
| **5** | Device adapter layer (mock / adb / Appium Android), cross-surface consistency runner, divergence log |
| **6** | QE maturity: `src/` layout + packaging, contract tests, tiered markers, pre-commit, structured logging, cost model, A/B with McNemar, safety parity, semantic drift, human review queue, storage ABC with Postgres skeleton, suite versioning, latency graders, docs split |

---

## Layout

```
pyproject.toml                     packaging, markers, ruff, mypy
.pre-commit-config.yaml            ruff + detect-secrets + pytest pre-push

src/agent_eval_hub/
  adapters/                        LLM providers (Claude/OpenAI/Gemini/Ollama/device)
  devices/                         device backends (mock/adb/Appium Android)
  graders/                         deterministic / device / consistency / latency / llm_judge / human_review
  runner/                          run_suite / run_cross_surface / run_ab / run_safety_parity / review_queue
  storage/                         Store ABC + duckdb + postgres
  dashboard/                       Streamlit UI + seed_demo
  pricing.py                       per-model $/1M token catalog
  logging.py                       structured logger (JSON off-TTY, plain on-TTY)

suites/
  agent/tool_use.yaml
  rag/rag_qa.yaml
  safety/red_team.yaml
  device/device_ui.yaml

fixtures/
  devices/basic_ui.json            mock-device canned responses

tests/
  conftest.py                      shared fixtures (ScriptedAdapter, tmp_db)
  contract/                        parameterized contract checks over registries
  test_*.py                        unit + integration (markers)

docs/
  architecture.md
  adding-a-provider.md
  adding-a-device.md
  adding-a-grader.md
  testing.md
  limitations.md

.github/workflows/
  eval-on-pr.yml                   fast tests + live provider evals on PR
  drift-weekly.yml                 scheduled cron, opens issue on drift
  nightly-e2e.yml                  real-provider evals, e2e tier
  device-ui.yml                    Dockerized Android emulator (disabled by default)
```

---

## Console scripts

| Command | What |
|---|---|
| `agent-eval` | Run a suite against one provider. Exit code `0`/`1`/`2` (pass/fail/drift). |
| `agent-eval-cross` | Same suite, two surfaces; flag divergent answers. |
| `agent-eval-ab` | Compare two models on the same suite with McNemar's exact test. |
| `agent-eval-safety-parity` | Compare refusal behavior between two surfaces. |
| `agent-eval-seed` | Seed a demo DuckDB with 8 weeks of fake runs + injected drift. |
| `agent-eval-review` | Walk the human-review queue (JSONL) and decide pending cases. |

---

## Deeper reading

- [Architecture](docs/architecture.md)
- [Adding a provider](docs/adding-a-provider.md)
- [Adding a device backend](docs/adding-a-device.md)
- [Adding a grader](docs/adding-a-grader.md)
- [Testing & markers](docs/testing.md)
- [Known limitations](docs/limitations.md)

---

## Development

```bash
pip install -e .[dev]
pre-commit install

ruff check src tests && ruff format --check src tests
mypy src                  # advisory, not strict yet
pytest                    # 93 tests passing today
```
