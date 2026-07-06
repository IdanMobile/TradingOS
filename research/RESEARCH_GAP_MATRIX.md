# Research Gap Matrix — Trading Intelligence OS

Status: v1, 2026-07-06. Gaps CLOSED by the 2026-07-06 research pass are listed in §2 with evidence. Open gaps in §1 carry owner + trigger. "Executable" gaps (resolvable only by running code) are deliberately routed to S1 workstreams, not desk research — per D-025.

## 1. Open gaps

| ID | Exact question | Why it matters | Current evidence | Missing evidence | Method | Decision affected | Blocking? | Owner | Reverify/when |
|---|---|---|---|---|---|---|---|---|---|
| RG-01 | Do all four engines install & run baselines on the operator's Mac (ARM) within acceptable friction? | engine role selection | none (desk research exhausted) | executable install/run evidence | S1 WS3 bake-off | PROTOTYPE_EVIDENCE_DECISION | blocks S2, not S1 | coding agent | S1 |
| RG-02 | LEAN CLI local backtesting: exact free-vs-paid data/feature boundary for crypto spot? | bake-off fairness; cost assumptions | docs partially fetched, pricing page 404'd [W] | current QuantConnect datasets/pricing terms | SOURCE_VERIFIER fetch + WS3 executable check | engine bake-off scoring | no (bake-off proceeds; blocker recorded if hit) | R2 + coding agent | before WS3 LEAN lane |
| RG-03 | vectorbt OSS v1.x exact license text (GitHub shows NOASSERTION; community says Apache-2.0+Commons-Clause) | license compliance for accelerator | M-strength secondary | LICENSE file read from repo | SOURCE_VERIFIER (trivial fetch) | accelerator probe legality | yes for WS3 vectorbt lane only | R2 | before vectorbt probe |
| RG-04 | Does vectorbt v1.1 (pandas 3) coexist with Freqtrade/Nautilus dep stacks in one workspace? | env architecture (mono-env vs per-engine envs) | release notes imply pandas-3 jump [S] | executable resolution test | WS1 env bootstrap (per-engine isolated envs is the default assumption) | repo/env structure | no (isolation assumed) | coding agent | WS1 |
| RG-05 | Kraken + Coinbase exact Israel retail availability (account-level) | venue shortlist ordering; S3 human gate prep | Kraken inconclusive; Coinbase "not accepted" via secondary [M/W] | official supported-countries pages / support answers | SOURCE_VERIFIER; ultimately HUMAN account check (HG-4) | venue matrix ranking | no for S1/S2 | R2 then operator | before S3 |
| RG-06 | Which fee tier applies to the operator's actual accounts (any venue)? | F3 scenario realism | none (account-specific) | operator account data | HUMAN | validation cost grids (F3) | no until S3 | operator | S3 entry |
| RG-07 | PBO/DSR implementation details vs primary papers (estimator choices, small-sample behavior) | G10 gate correctness | papers identified [S] | worked implementation review + known-answer fixtures | SKILL_VALIDATION_STATS_SPECIALIST during WS6 | G10 activation | no (G10 is method-candidate in V1) | R4/R7 | WS6 |
| RG-08 | OpenAI GPT-5.6 tier pricing + Gemini 3.x context windows + Google deprecation policy (primary sources) | benchmark cost tables; harness pinning strategy | aggregator-sourced [W] | official pricing/model pages | SOURCE_VERIFIER | WS8 cost accounting | no (harness design is provider-agnostic) | R2 | before first paid benchmark run |
| RG-09 | promptfoo ownership (OpenAI acquisition rumor) — neutrality of eval tooling | eval-tool selection integrity | single unconfirmed mention [W] | official announcement or absence thereof | SOURCE_VERIFIER | WS8 tooling (only if promptfoo considered) | no (MLflow-first direction) | R2 | if promptfoo enters WS8 |
| RG-10 | Real MLflow+DVC operational friction on this machine (restore, compare, trace, local-first) | lineage decision | strengthened hypothesis [S] | executable prototype | S1 WS5 (spec exists) | D-019 finalization | blocks S2 architecture lock | coding agent | WS5 |
| RG-11 | 10-item seed batch: actual schema/license/ambiguity lessons | ingestion automation design | workflow spec only | executed batch | S1 WS7 | S2 ingestion scope | blocks S2 ingestion | coding agent | WS7 |
| RG-12 | Minimal dashboard data contract (what the evidence surface actually needs) | dashboard_api design | six-view list approved | prototype usage evidence | S1 WS9 | S2 console IA | no | coding agent | WS9 |
| RG-13 | Divergence model: backtest-vs-paper reconciliation method | S3 qualification design | G12 sketch | paper-lane data | S3 | paper gates | no until S3 | architect | S3 |
| RG-14 | CI provider choice (or none) for a single-operator local-first repo | dev workflow | none | cost/benefit at S2 scale | decide at S2 entry with repo evidence | AD §AH | no | operator+agent | S2 entry |
| RG-15 | Job-queue sufficiency: does DB-table queue + APScheduler cover WS-scale workloads? | jobs module design | judgment-level [M] | prototype load evidence | S1 execution telemetry | AD §S | no (upgrade path named: Prefect) | coding agent | S2 entry |
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
| CG-07 | Current AI model landscape for benchmark planning? | Anthropic Claude 5 family / OpenAI GPT-5.x / Gemini 3.x; **no provider guarantees determinism** → harness multi-samples; OpenAI Evals platform dying (2026-11-30) → not a dependency; Inspect+MLflow best local-first eval fits. | registry §7 [S/M] |
| CG-08 | Dashboard/ontology stack directions? | Streamlit for WS9 evidence surface; Next.js+shadcn for S2 console; plain relational tables + FTS for dictionary (<10k concepts); FIBO (MIT) safe seed; graph DBs rejected (Kuzu archived, Memgraph BSL, Neo4j overkill). | registry §8–9 [S] |
| CG-09 | Postgres/tooling versions for S1/S2 planning? | PG 18 GA (build against 18, not 19-beta; PG14 EOL 2026-11); SQLite 3.53 fine for prototype; OTel GenAI semconv still unstable → abstraction layer required if adopted. | registry §4–5 [S] |

## 3. Standing re-verification triggers

- Engine versions/licenses: before each engine's bake-off lane starts (they release monthly/bi-weekly).
- Model IDs/pricing: before any paid benchmark execution; Sonnet 5 intro pricing ends 2026-08-31.
- DVC roadmap under lakeFS stewardship: at S2 architecture lock.
- Binance/Kraken/OKX changelogs: monthly during S1; before any connectivity test.
- All registry rows: 90-day default expiry (SOURCE_VERIFIER owns).
