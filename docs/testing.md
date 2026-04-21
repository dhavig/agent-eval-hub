# Testing

## Tiered markers

Every test belongs to one of four tiers, declared in `pyproject.toml`:

| Marker | What it means | Runs in |
|---|---|---|
| `unit` | Default. No network, no subprocess, no external services. | PR CI, pre-commit |
| `integration` | End-to-end through the runner but with stub adapters + mocked devices. | PR CI |
| `e2e` | Hits real LLM providers (needs API keys). | Nightly workflow |
| `device` | Real emulator or Appium required. | Manual / dedicated runner |
| `contract` | (folder, not marker) Parameterized contract checks over registries. | Runs with `unit`. |

## Commands

```bash
pytest                                    # everything that can run locally
pytest -m "not integration and not e2e"   # fastest set (pre-commit default)
pytest -m integration                     # stub-adapter end-to-end
pytest -m e2e                             # live providers (gated on keys)
pytest -m device                          # real emulator (gated on adb/appium)
pytest tests/contract/                    # registry contract assertions
```

## Shared fixtures

Live in `tests/conftest.py`:

- **`scripted_adapter(responses)`** — factory for the `ScriptedAdapter`; replays a list of `AgentResponse`s one per `.complete()` call.
- **`patch_get_adapter({provider: [responses]})`** — patches `runner.run_suite.get_adapter` so CLIs pick up scripted responses.
- **`tmp_db`** — fresh DuckDB path per test.
- **`mock_android_fixture`** — path to `fixtures/devices/basic_ui.json`.

## What to mark

- A test that calls a real provider → `@pytest.mark.e2e`
- A test that calls `run_suite()` or a CLI main → `pytestmark = pytest.mark.integration`
- A test that instantiates `AdbAndroidAdapter` against a real emulator → `@pytest.mark.device`
- Everything else → no marker (runs by default).

## Contract tests

Every new adapter and device backend must be added to the parameterized dispatch tables in `tests/contract/`. The tests then auto-verify:
- Correct ABC inheritance
- Correct registry ↔ class wiring
- Canonical `.complete()` / `execute()` signatures

Contract failures block PRs because they're cheap to run and catch the easiest-to-ship breakage.
