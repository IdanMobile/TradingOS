# Research Gap Matrix — Trading Intelligence OS

Status: v2, 2026-07-10. Gaps CLOSED by retained execution evidence are listed in §2 with evidence. Open gaps in §1 carry owner + trigger. "Executable" gaps (resolvable only by running code) are deliberately routed to stage workstreams, not desk research — per D-025.

## 1. Open gaps

| ID | Exact question | Why it matters | Current evidence | Missing evidence | Method | Decision affected | Blocking? | Owner | Reverify/when |
|---|---|---|---|---|---|---|---|---|---|
| RG-05 | Kraken + Coinbase exact Israel retail availability (account-level) | venue shortlist ordering; S3 human gate prep | Kraken inconclusive; Coinbase "not accepted" via secondary [M/W] | official supported-countries pages / support answers | SOURCE_VERIFIER; ultimately HUMAN account check (HG-4) | venue matrix ranking | no for S1/S2 | R2 then operator | before S3 |
| RG-06 | Which fee tier applies to the operator's actual accounts (any venue)? | F3 scenario realism | none (account-specific) | operator account data | HUMAN | validation cost grids (F3) | no until S3 | operator | S3 entry |
| RG-07 | PBO/DSR implementation details vs primary papers (estimator choices, small-sample behavior) | G10 gate correctness | papers identified [S]; `G10_RETENTION` evidence proves all 66 trials/method refs retained | worked estimator implementation review + known-answer fixtures + independent recomputation | validation stats specialist during S2 validation expansion | G10 production activation | blocks full validation/promotion, not offline research | R4/R7 | before any G10 PASS claim |
| RG-08 | OpenAI GPT-5.6 tier pricing + Gemini 3.x context windows + Google deprecation policy (primary sources) | benchmark cost tables; harness pinning strategy | aggregator-sourced [W] | official pricing/model pages | SOURCE_VERIFIER | WS8 cost accounting | no (harness design is provider-agnostic) | R2 | before first paid benchmark run |
| RG-09 | promptfoo ownership (OpenAI acquisition rumor) — neutrality of eval tooling | eval-tool selection integrity | single unconfirmed mention [W] | official announcement or absence thereof | SOURCE_VERIFIER | WS8 tooling (only if promptfoo considered) | no (MLflow-first direction) | R2 | if promptfoo enters WS8 |
| RG-13 | Divergence model: backtest-vs-paper reconciliation method | S3 qualification design | G12 sketch | paper-lane data | S3 | paper gates | no until S3 | architect | S3 |
| RG-14 | CI provider choice (or none) for a single-operator local-first repo | dev workflow | none | cost/benefit at S2 scale | decide at S2 entry with repo evidence | AD §AH | no | operator+agent | S2 entry |
| RG-16 | Ontology seed scope: which concepts do MVP artifacts actually reference? | dictionary seeding batch | none | extraction from S1 artifacts | run ONTOLOGY_CURATOR over S1 outputs | S2 dictionary batch | no | R6 | S2 |

## 2. Gaps closed 2026-07-06 (this planning pass)

| Closed | Question | Answer | Evidence |
|---|---|---|---|
| CG-01 | Are the four first-tier engines still maintained? | Yes, all active (Freqtrade 2026.6; Nautilus v1.230.0; LEAN rolling daily; Hummingbot v2.15.0). Backtrader dead, backtesting.py stalled+AGPL — both rejected. | registry §1 [S] |
| CG-02 | Is vectorbt OSS abandoned (PRO required)? | **No — reversed.** OSS reactivated 2026 (v1.0.0 Apr, v1.1.0 Jul 2026). Probe OSS first. | registry §1 [S] |
| CG-03 | Is Binance public data still viable as canonical source? | Yes, but **timestamp unit changed ms→µs on 2025-01-01** — normalization must handle the boundary; dataset spec amended via ADDENDUM (see `specs/` note in DECISION_LOG D-029). | registry §6 [S] |
| CG-04 | MLflow/DVC still the right lineage prototype pair? | Yes; MLflow 3.14 materially stronger (GenAI tracing/eval mature — may also serve WS8); DVC ownership moved to lakeFS (2025-11) — still Apache-2.0/active; hypothesis stands, prototype still required. | registry §2 [S] |
| CG-05 | Venue shortlist still correct? | Adjusted: OKX up (Israel explicitly supported + demo env), Coinbase down (Israel not accepted per secondary — RG-05 verify), Kraken unchanged (inconclusive), Binance unchanged (technically strong; live-eligibility gray). | registry §6 [S/M] |
| CG-06 | Is Databento a crypto data candidate? | Not for spot crypto — coverage is CME/CFE-adjacent. Keep only as future multi-asset (equities/futures) candidate. Package assumption revised. | registry §6 [M] |
| CG-10 | (was RG-03, closed 2026-07-06 S1 execution) vectorbt OSS v1.1.0 exact license? | **Apache 2.0 with Commons Clause** — verified from the installed package's own LICENSE.md (dist-info). Internal research use permitted; "Sell" rights excluded. vectorbt probe lane UNBLOCKED for this project's internal use. | `engines/vectorbt/LICENSE_CAPTURED.txt` (sha256 a914859a…ec84) [S] |
| CG-11 | (was RG-04, closed 2026-07-06 S1 execution) Does the vectorbt pandas-3 stack coexist with other engine stacks? | Made moot by per-engine isolation (AD-02): five isolated envs built and smoke-tested on the target Mac (T-003-03); no mono-env attempted or needed. | `engines/*/env_manifest.txt` [S] |
| CG-07 | Current AI model landscape for benchmark planning? | Anthropic Claude 5 family / OpenAI GPT-5.x / Gemini 3.x; **no provider guarantees determinism** → harness multi-samples; OpenAI Evals platform dying (2026-11-30) → not a dependency; Inspect+MLflow best local-first eval fits. | registry §7 [S/M] |
| CG-08 | Dashboard/ontology stack directions? | Streamlit for WS9 evidence surface; Next.js+shadcn for S2 console; plain relational tables + FTS for dictionary (<10k concepts); FIBO (MIT) safe seed; graph DBs rejected (Kuzu archived, Memgraph BSL, Neo4j overkill). | registry §8–9 [S] |
| CG-09 | Postgres/tooling versions for S1/S2 planning? | PG 18 GA (build against 18, not 19-beta; PG14 EOL 2026-11); SQLite 3.53 fine for prototype; OTel GenAI semconv still unstable → abstraction layer required if adopted. | registry §4–5 [S] |
| CG-12 | (was RG-01, closed 2026-07-10 S1 execution) Do first-tier engines install/run enough evidence on the operator Mac? | Freqtrade, vectorbt, Nautilus, and Hummingbot retained executable evidence; LEAN installed but local backtest remains Docker-blocked, so LEAN is deferred rather than blocking S2. | `artifacts/reports/ENGINE_BAKEOFF_REPORT.md`, `engines/*/env_manifest.txt` |
| CG-13 | (was RG-02, closed as blocker classification 2026-07-10) LEAN local crypto backtest boundary | Local mechanism/env exists, but execution is blocked while Docker is stopped; S2 records LEAN as deferred portability evidence, not a paper/live dependency. | `artifacts/bakeoff/lean/STATUS.md`, `artifacts/reports/ENGINE_BAKEOFF_REPORT.md` |
| CG-14 | (was RG-10, closed 2026-07-10 S1 execution) Real MLflow+DVC operational friction | Prototype passed reproduce, compare, trace, local-first, replaceability, and fresh-clone restore/hash replay gates; D-035/D-037 lock the S2 policy. | `artifacts/reports/LINEAGE_PROTOTYPE_REPORT.md`, `DECISION_LOG.md` D-035/D-037 |
| CG-15 | (was RG-11, closed 2026-07-10 S1 execution) 10-item seed batch lessons | Strategy ingestion seed evidence exists with schema/license/ambiguity lessons retained for S2 ingestion design. | `artifacts/reports/STRATEGY_INGESTION_REPORT.md` |
| CG-16 | (was RG-12, closed 2026-07-10 S1/S2 execution) Minimal dashboard data contract | Read-only `/api/v1/status`, `/api/v1/dashboard`, and `/api/v1/market` contracts are tested and browser-verified; S2 Automation view extends the same read-only projection. | `tests/test_dashboard.py`, `src/tios/services/dashboard_api/status.py` |
| CG-17 | (was RG-15, closed for bounded S2 2026-07-10) Job-queue sufficiency | SQLite jobs DB plus bounded local scheduler is sufficient for the retained offline Research Lab cadence; escalation trigger remains measured queue saturation or multi-machine requirement. | `artifacts/jobs/jobs.sqlite3`, `src/tios/services/jobs/`, AD §S |

## 3. Standing re-verification triggers

- Engine versions/licenses: before each engine's bake-off lane starts (they release monthly/bi-weekly).
- Model IDs/pricing: before any paid benchmark execution; Sonnet 5 intro pricing ends 2026-08-31.
- DVC roadmap under lakeFS stewardship: at S2 architecture lock.
- Binance/Kraken/OKX changelogs: monthly during S1; before any connectivity test.
- All registry rows: 90-day default expiry (SOURCE_VERIFIER owns).
