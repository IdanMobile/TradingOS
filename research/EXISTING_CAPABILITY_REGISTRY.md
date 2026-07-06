# Existing Capability Registry — Trading Intelligence OS

Status: v1, evidence-refreshed 2026-07-06 (supersedes scattered candidate lists in Phase 1–4 reports for *currency*; those reports remain the discovery record)
Method: candidates from package research (checked 2026-07-05) re-verified against official sources on 2026-07-06 via web research. Evidence strength tags: S=strong (official source fetched), M=medium (corroborated secondary), W=weak (unverified — see RESEARCH_GAP_MATRIX).
Decisions here are **registry statuses**, not approvals. Approval states live in `DECISION_LOG.md` / `decisions/`.

## 1. Trading & backtesting engines

| Candidate | Version @ 2026-07-06 | Maintenance | License | Capability | Limitations | Fit / status |
|---|---|---|---|---|---|---|
| Freqtrade | 2026.6 (2026-06-29), monthly CalVer, py≥3.11 [S] | very active; lookahead/recursive analysis retained & expanded in 2026.6 [S] | **GPL-3.0** [S] | crypto backtest/dry-run/live, hyperopt(Optuna), bias diagnostics, UI/API | crypto-only; GPL means our code must not link-import it — use via CLI/subprocess + artifacts | FIRST-TIER BAKE-OFF (D-013) — confirmed current |
| NautilusTrader | v1.230.0 (2026-06-29), bi-weekly, py≥3.12<3.15 [S] | very active (company-backed); still "Beta" semantics → API churn expected [S] | LGPL-3.0 [S] | event-driven deterministic backtest+live, Binance Spot adapter (bar-based confirmed) | margin on Binance adapter not implemented; churn risk; py3.12 floor constrains env | FIRST-TIER BAKE-OFF — confirmed current |
| LEAN | rolling (last commit 2026-07-02); no GitHub releases since 2017 — judge by commits [S] | very active daily | Apache-2.0 (engine) [S] | multi-asset research/backtest/live; local via Docker + LEAN CLI | local-vs-cloud data licensing boundary UNCONFIRMED [W → RG-02]; .NET+Docker weight | FIRST-TIER BAKE-OFF |
| Hummingbot | v2.15.0 (2026-06-16) [S] | active, foundation-maintained, py≥3.10.12 | Apache-2.0 [S] | V2 controllers + Dashboard backtest, bot ops, market making | research-backtest depth thinner than others; MQTT bridge migration (aiomqtt) may affect integrations | FIRST-TIER BAKE-OFF (ops/MM role) |
| vectorbt (OSS) | **v1.1.0 (2026-07-05)** — OSS line REACTIVATED 2026 (v1.0.0 Apr 2026) [S] | active again; pandas 3 / py3.14 / NumPy 2.4 stack [S] | **Apache-2.0 + Commons Clause — VERIFIED 2026-07-06** from v1.1.0 dist-info LICENSE.md (`engines/vectorbt/LICENSE_CAPTURED.txt`) [S]; internal use OK, no resale (CG-10) | vectorized sweeps, research acceleration | no live/paper; multiple-testing hazard; new dep-stack (pandas 3) may conflict with other engines | ACCELERATOR PROBE — **assumption "OSS abandoned, PRO required" is now FALSE**; probe OSS first |
| vectorbt PRO | commercial successor, active [M] | active | proprietary/membership | as above, more features | cost; lock-in | FALLBACK if OSS probe fails |
| backtesting.py | 0.6.5 (2025-07-30); last commit 2025-12-20 [S] | **stalled** | **AGPL-3.0** [S] | simple backtests | stalled + AGPL | REJECTED for platform use |
| Backtrader | 1.9.78.123 (2023-04-19); no commits since 2023 [S] | **abandoned**; declared py support 3.2–3.7 | GPL-3.0 | legacy reference | dead upstream | REJECTED (reference-reading only) |

## 2. Experiment lineage / data versioning

| Candidate | Version/status @ 2026-07-06 | License | Notes | Status |
|---|---|---|---|---|
| MLflow | 3.14.0 (2026-06-17), ~monthly cadence; GenAI tracing/eval/review-queues mature; local-first fully viable [S] | Apache-2.0 | now credible as BOTH run tracker AND LLM-eval/trace backbone (strengthens D-019 and may simplify WS8) | PROTOTYPE (WS5) — hypothesis strengthened |
| DVC | 3.6x active [S/M] | Apache-2.0 | **acquired by lakeFS/Treeverse 2025-11-18**; continues as OSS for small-data use [S] | PROTOTYPE (WS5) — ownership-change reverify trigger set |
| lakeFS | active, Python SDK 0.16.0 (2026-04); stewards DVC; $20M raise 2025 [S/M] | Apache-2.0 [S] | object-store scale; heavier than laptop-first needs | LATER CANDIDATE (unchanged) |
| W&B | self-host needs server license even for free tier; ≤0.65 EOL 2026-01-30 [M] | proprietary | licensing gate conflicts with local-first | REJECTED for MVP |
| Aim / ClearML | active; Aim light/local, ClearML heavy suite w/ capped free tier [M] | OSS/mixed | fallback options if MLflow gate fails | REGISTERED FALLBACKS |

## 3. Orchestration / jobs / scheduling

| Candidate | Status @ 2026-07-06 | Judgment for laptop-first single operator |
|---|---|---|
| APScheduler | 3.11.3 (2026-06-28), active [S] | GOOD FIT for scheduling |
| Celery / RQ / Huey | maintained [M]; arq regaining maintenance (verify before use) [M] | RQ/Huey adequate; Celery heavier |
| Prefect | OSS Apache-2.0 self-host viable [M] | middle option if real DAG/retry UI needed; NOT required for MVP |
| Dagster | active; asset-centric; paid tier pricing changed 2026-05 [M] | overkill for MVP |
| Temporal | MIT, needs server+Postgres(+ES) [M] | overkill — REJECTED for MVP |
| MVP DIRECTION | — | DB-table job queue + APScheduler inside the monolith (Module `jobs`); adopt Prefect only if prototype shows real need (Custom Build Gate applies in reverse: reuse simplest sufficient) |

## 4. Observability

| Candidate | Status | Notes |
|---|---|---|
| OpenTelemetry (Python) | SDK stable; **GenAI semconv still experimental, churning every release** [S/M] | wrap behind thin abstraction if adopted; do not hard-pin attribute names |
| Prometheus / Grafana / Loki | Apache-2.0 / AGPL-3.0 (internal use fine) [S] | credible self-host stack for S2/S3; overkill for S1 |
| Sentry self-hosted | FSL license, internal use unrestricted [S] | optional S2 |
| Logfire | MIT SDK, OTel-based; own backend is SaaS-gravity [M] | SDK acceptable, backend not local-first |
| MVP DIRECTION | — | structured logging + MLflow run views + minimal dashboard; full stack deferred to S2 (AD §AC) |

## 5. Storage / data

| Candidate | Status @ 2026-07-06 | Notes |
|---|---|---|
| PostgreSQL | 18 GA (Sept 2025); 19 beta — build against 18; PG14 EOL 2026-11 [S] | operational DB candidate |
| SQLite | 3.53.3 (2026-06-26) [S] | prototype-stage operational store candidate (zero-ops); FTS5 for search |
| DuckDB | 1.5.x active [M] | analytical queries over Parquet artifacts |
| Parquet/Arrow (pyarrow 24, polars 1.42) | active [M] | canonical artifact formats |
| TimescaleDB | core Apache-2.0; company now TigerData (2025-06) [S] | only if time-series query load demands it — not MVP |
| pgvector | 0.8.4 (2026-06-30) [M] | vector retrieval ONLY if a justified retrieval need appears (none in MVP) |

## 6. Connectivity & market data

| Candidate | Status @ 2026-07-06 | Notes |
|---|---|---|
| Binance public Spot data | data.binance.vision active/free; **timestamps µs since 2025-01-01** (was ms) [S] | canonical dataset source CONFIRMED (D-022a); normalization must handle unit boundary |
| Binance Spot API/Testnet | active; new Spot Demo Mode env since 2026-01; changelog churn (SBE, rate limits, FIX TLS) [S] | technically shortlisted; Israel status gray for live (unlicensed) — human gate unchanged |
| Kraken | active; base fees 0.25/0.40 taker/maker tier-0 [S] | Israel signal inconclusive [W → RG-05] |
| Coinbase Advanced | docs moved to docs.cdp.coinbase.com; **Israel residents not accepted per secondary sources** [M → RG-05] | DEMOTE from candidate list pending verification |
| OKX | active; demo env confirmed; **Israel explicitly supported** [S] | PROMOTE in connectivity-test ranking |
| CCXT | 4.5.64 (2026-07-03), MIT, very active [S] | reuse + native fallback confirmed |
| Tardis.dev | active; public pricing ~$350–6000/mo by tier [S] | Tier-2 candidate unchanged; purchase still not approved |
| CoinAPI / Kaiko | active [M/S] | Tier-1 candidates unchanged |
| Databento | **NOT a spot-crypto vendor** — crypto coverage is CME/CFE-futures-adjacent only [M] | REVISE package assumption: future multi-asset (equities/futures) yes; crypto-spot no |

## 7. AI models / eval / agents (July 2026)

| Item | Status @ 2026-07-06 | Notes |
|---|---|---|
| Anthropic lineup | Fable 5 $10/$50, Opus 4.8 $5/$25, Sonnet 5 $2→$3/$10→$15 (intro ends 2026-08-31), Haiku 4.5 $1/$5; 1M ctx (Haiku 200k) [S] | pinned snapshots; ≥60d retirement notice; temperature/top_p REJECTED (400) on current gen |
| OpenAI lineup | GPT-5.6 flagship (tier pricing unverified [W]); 5.5/5.4 lines live; Evals platform product SHUTTING DOWN 2026-11-30 [S/M] | re-verify pricing before harness cost tables (RG-08) |
| Google lineup | Gemini 3.5 Flash / 3.1 line; ctx windows unconfirmed [W] | RG-08 |
| Determinism | NO provider guarantees reproducibility on flagships [S/M] | benchmark harness MUST multi-sample (already reflected in SKILL_BENCHMARK_RUNNER) |
| Eval frameworks | Inspect (UK AISI) + MLflow strongest local-first fits; promptfoo strong but ownership rumor unverified [M/W → RG-09]; DeepEval viable; Braintrust/LangSmith/Weave SaaS-gravity | WS8 harness: MLflow-first (already prototyped) + Inspect as design reference |
| Agent frameworks | AutoGen effectively dead (folded into MS Agent Framework 1.0, 2026-04); Pydantic AI v2.x fast-moving; LangGraph / OpenAI Agents SDK / Claude Agent SDK are the practical trio [M] | registry entries only; no adoption decision needed for MVP |

## 8. Dashboard / UI

| Candidate | Status @ 2026-07-06 | Fit |
|---|---|---|
| Streamlit | 1.58.0 (2026-05-28), Apache-2.0, active [S] | **SELECTED CANDIDATE for WS9 read-only evidence surface** (cheapest credible; single file; local) — provisional until WS9 executes |
| Dash / Panel / Gradio | all active, permissive [S] | fallbacks; no differentiating need identified |
| MLflow UI / Grafana | free evidence views [S] | complement, not replacement, for the domain evidence surface |
| Next.js + shadcn/ui | active ecosystem [M] | S2 operator-console direction (trading console is not CRUD-shaped → Refine/react-admin rejected) |
| Refine / react-admin | active, MIT [S] | REJECTED for console (CRUD-assumption mismatch); reassess only if console becomes entity-CRUD-dominant |

## 9. Ontology / dictionary / search

| Candidate | Status @ 2026-07-06 | Fit |
|---|---|---|
| Plain relational concept tables (SQLite/Postgres) + FTS5/tsvector | stdlib/built-in | **SELECTED DIRECTION** for <10k concepts (laziest defensible; graph DB unjustified) |
| FIBO (EDM Council) | MIT, active (master_2026Q1, 2026-04-20) [S] | legally clean seed source |
| Investopedia et al. | reuse rights unverified/likely restricted [W] | DO NOT scrape; cite concepts, write own definitions |
| rdflib / Oxigraph | active [S] | adopt only if external linked-data interop becomes real |
| Skosify | dormant since 2021 [S] | REJECTED |
| Neo4j CE / Memgraph / Kuzu | GPLv3 / BSL source-available / **archived 2025-10** [S] | ALL REJECTED for MVP (overkill / license / dead) |
| Meilisearch / Tantivy | active MIT [S] | later, only if FTS5 measurably insufficient |

## 10. Security / secrets / testing / CI

| Candidate | Status | Fit |
|---|---|---|
| python-dotenv | 1.2.2 (2026-03-01) [S] | intake-gate `.env` workflow |
| sops | 3.13.2, MPL-2.0, community-maintained [S] | if secrets must live encrypted in repo (not needed for MVP) |
| 1Password CLI | proprietary, account-bundled [M] | optional operator convenience |
| pytest/hypothesis/ruff/mypy-or-pyright | ecosystem defaults | verify versions at WS1 |
| gitleaks / detect-secrets | verify at WS1 | secret scanning in local gate |
| CI provider | deferred | RG-14; local one-command gate first |

## Registry maintenance rule

Every row's evidence expires per its reverify trigger (default: 90 days, or on named event — release, acquisition, deprecation notice). SOURCE_VERIFIER skill owns refreshes. Rows feeding an Approved decision must be S-strength or carry an explicit open item.
