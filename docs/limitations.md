# Known limitations

Honesty matters more in QE tooling than anywhere else. Here's what v0.3.0
doesn't handle well.

## Storage

- **DuckDB backing store evicts after 7 days of GitHub `actions/cache` inactivity.** For production, switch to `--db postgres://...`. The `PostgresStore` is shipped as a skeleton — the schema + CRUD work, but it's not yet exercised in CI.
- **No data versioning.** Suites have a `version:` field now, but running the same suite against two different models' YAML versions doesn't warn.

## Graders

- **`jaccard` similarity is lexical, not semantic.** Two answers that mean the same thing in different words score low. Upgrade path: layer an `llm_judge` consistency rubric on top.
- **`refused` is a regex heuristic.** Models that refuse politely without using the known markers slip through. Paired with `llm_judge` in subtle cases.

## Device layer

- **No CI runs against a real emulator yet.** The Dockerized Android workflow ships disabled. The mock + adb/Appium *classes* are tested; the wired-up emulator run isn't.
- **"On-device model" is currently Ollama-on-localhost.** Swap for llama.cpp / MLX / Android AICore in production. The `DeviceOllamaAdapter` naming exists so cross-surface reports read correctly today.

## A/B + statistical tests

- **McNemar's exact test needs 5+ discordant pairs** to avoid unreliability. With suites under ~10 tasks, expect frequent "inconclusive" verdicts. Add more tasks or rerun with more replications.

## Cost model

- **Pricing is list-price, per 1M tokens, published.** Contract rates, cached-input discounts, volume discounts — out of scope. Override via `AGENT_EVAL_PRICING_JSON` if you care.
- **No cost for device-side inference.** On-device models are priced at zero, which is right for marginal cost but ignores battery, memory, and thermal cost — a real concern on phones. Out of scope for v0.3.

## Human review

- **Terminal-only CLI.** No web UI, no ticketing integration. JSONL queue is the interface.
- **Queue is file-based, not concurrency-safe beyond append.** For multi-reviewer workflows, back it with Postgres.

## Observability

- **Logs are text + JSON; no OpenTelemetry / metrics export.** Dashboards summarize; they don't alert. For production, pipe the JSON logs into your existing stack.
