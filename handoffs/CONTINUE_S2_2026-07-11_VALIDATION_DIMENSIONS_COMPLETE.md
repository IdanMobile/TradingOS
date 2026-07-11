# Handoff — Continue S2 after validation-dimension completion (2026-07-11)

Audience: the next coding agent/session (any AI). Read order: this file →
`handoffs/START_HERE_SINGLE_CODING_AGENT_PROMPT.md` (SSOT, still the controller) →
`PROJECT_STATE.md` → `TODO.md`/`todos/` → `MISSING_AND_OPEN_ITEMS.md`.

## Current objective and phase

Constrained S2 offline research lab (D-036/D-037). This session completed every
agent-executable validation-evidence task; the project is now blocked only by
human gates, credential gates, and deliberately deferred throughput/scope tracks.
**No strategy is approved; nothing trades; live states are unreachable (tested).**

## What this session completed (all evidence retained)

1. **Full AD/docs/TODO/env audit** — 4 reports in `artifacts/reports/`:
   `AD_IMPLEMENTATION_GAP_AUDIT_2026_07_11.md`, `OPEN_TASKS_AND_DOCS_AUDIT_…`,
   `ENV_AND_CREDENTIALS_AUDIT_…`, `WORKSPACE_TODO_API_SYNC_…`. `.env.example`
   gained `TIOS_AI_MODE`/`TIOS_AI_PROVIDER` (names only).
2. **T-002-05 / D-038** — the loopback `POST /api/v1/workspace-actions/decision`
   route is the approved single audited write exception; AD §AI + type catalog §7
   updated. Any expansion needs a new decision gate.
3. **T-009-04 / RG-07 — production G10 ACTIVE** — candidate-specific PBO/CSCV+DSR
   with independent recomputation (`scripts/run_g10_candidate.py`,
   `engines/vectorbt/g10_returns.py`). All families FAIL (B2 PBO 0.8685, DSR≈0).
   Evidence: `artifacts/validation/G10_CANDIDATE_EVIDENCE_2026_07_11.json`.
   B2 package gate G10 = FAIL. Future G10 PASS needs stats-specialist review.
4. **Cross-engine reproduction dimension CLOSED** — three-way B2 reproduction
   (core derivation, vectorbt exact, single-pair Freqtrade full-history rerun with
   99.904% fill↔signal reconciliation, all exits signal-driven). Verdict
   PASS_WITH_SCOPE_NOTE (fill/P&L parity NOT claimed). Evidence:
   `artifacts/validation/CROSS_ENGINE_REPRODUCTION_2026_07_11.json`,
   runner `scripts/run_cross_engine_reproduction.py`.
5. **Latest batch** `LAB-f04ef5d705e0de4d3fff5fe83ada90b2d91223dc89cfa35364c5fd8439ca3121`
   — rerun after the source-registry expansion; **zero BLOCKED score dimensions**;
   candidate rejected on economics, drawdown, walk-forward, robustness, baseline,
   G10. 66 trials retained, no winner, `execution_authority=NONE`.
6. **Hummingbot full-history chunking design** —
   `specs/HUMMINGBOT_FULL_HISTORY_CHUNKING_DESIGN_V1.md` (execution deliberately
   unscheduled; see its §5 rerun framing).

## Verification state (last run this session)

`make required` = ruff + format + mypy-strict + **341 tests PASS** + pip-audit clean
(latest full run after the local registry/report search and comparison dashboard slices). A focused dashboard/trading-domain
check after the demo-wallet readiness projection passed with 67 tests. Dashboard/workspace-TODO API live
at `http://127.0.0.1:8765`; `/api/v1/dashboard` projects 14
research sources, 4 source-intake plans, inert trading-domain read models, design-only demo-wallet readiness, comparison read models, and latest lab
`LAB-f04ef5d705e0de4d3fff5fe83ada90b2d91223dc89cfa35364c5fd8439ca3121`.
Playwright responsive smoke passed at 375/768/1024/1440 with no console/page
errors, no horizontal overflow, and the Search view returned DCA registry/source/
strategy/report results through `GET /api/v1/search`; the Comparisons view rendered
candidate dimension, validation gate, G10, seed probe, cross-engine, and evidence-ref
sections from retained artifacts.
Changelog is at v8.29. Note: the dashboard test also pins the latest SEEDCYCLE id
(`tests/test_dashboard.py`) — update it after any seed-cycle rerun.

## Key mechanics the next agent must know (do not rediscover)

- `todos/*.md` task statuses are parsed by regex `## T-NNN-NN Title` + `Status:` —
  the dashboard test pins **zero open tasks**; human-gated items must contain
  HUMAN/HG-/S3/S4/DEFERRED in the status string to land in the gated bucket.
- Tests pin the latest LAB batch id in 3 places (`tests/test_validation_package.py`,
  `tests/test_research_lab_v0.py`, `tests/test_dashboard.py`) and
  `artifacts/validation/validation_status.json` carries it too — update all four
  after any lab rerun (the lab reruns whenever any `VALIDATION_EVIDENCE_FILES`
  hash changes; list in `scripts/run_research_lab_v0.py`).
- Core never imports engines: engine work goes through
  `engines/<name>/.venv/bin/python` subprocesses.
- Decision log entries use `### D-NNN` headings (uniqueness-gated); next free: D-039.
- The jobs runner forces `TIOS_AI_MODE=mock`; six-hour offline schedule exists.

## Remaining work, in priority order

0. **UPDATE (later on 2026-07-11)**: seed reproduction was continued in-session.
   Seeds 03/04/07 are now REPRODUCED against the new 32-bar
   `fixtures/micro/bars_long.csv` (BB population-std, Wilder RSI, true recursive
   EMA — see `tests/test_strategy_seed_reproduction.py`), and the seed cycle
   covers **5 candidates / 43 trials** (`SEEDCYCLE-25fc2ebb…`), all ≈ −100% on
   the proxy. Agent-closable seeds are exhausted: 05/08 need a human tri-state
   supertrend decision; 06/09/10 are not applicable.
1. **UPDATE (D-039/D-040)**: the operator delegated offline research-direction
   decisions to AI, and the AI chose the cheapest decisive A/B: run the five
   reproduced seed candidates across BTCUSDT/ETHUSDT x 5m/15m/1h. The retained
   cycle is
   `SEEDCYCLE-9b1652a62996fda4b753c6695f43569ab860acd8decb48c9c5994566f4a6488f`
   with 258 trials and no winner. It produced positive proxy rows, led by QC2
   Donchian ETHUSDT 1h window=40 (+149.1%). Report:
   `artifacts/reports/SEED_CYCLE_MULTI_GRID_REPORT_2026_07_11.md`.
2. **UPDATE**: first validation-probe evidence now exists:
   `artifacts/validation/seed_candidates/SEED_VALIDATION_PROBE_2026_07_11.json`.
   QC2 ETHUSDT 1h window=40 is positive in all three chronological thirds and beats
   buy-and-hold at normal fees, but its immediate parameter neighborhood is mostly
   negative and it lacks production G10/cross-engine/paper evidence. QC2 BTCUSDT 1h
   and FT1 ETHUSDT 15m failed the probe on holdout/benchmark checks. Do not prepare
   HG-3 or paper/demo; these are still unvalidated research signals.
3. **UPDATE**: production-style G10 for the surviving QC2 ETHUSDT 1h context now
   exists at
   `artifacts/validation/seed_candidates/SEED_G10_QC2_ETHUSDT_1H_2026_07_11.json`.
   It FAILS: PBO 0.2614 but DSR 0.7564 < 0.95. No seed candidate is validated.
4. **UPDATE**: external source-family intake is seeded. The source registry now has
   non-paper source classes and four read-only hypothesis records:
   `SRC-BINANCE-TRADING-BOTS`, `SRC-BINANCE-COPY-TRADING`,
   `SRC-TRADINGVIEW-IDEAS`, and `SRC-3COMMAS-DCA-BOT`. They are all
   `hypothesis_only`, non-reproduced, non-eligible, and carry no copy/credential/
   venue/order authority. `EXTERNAL_SOURCE_INTAKE_PLANS_V1.yaml` adds one validated
   offline capture/replay plan per source, and `/api/v1/dashboard` projects 4 intake
   plans. `scripts/build_external_source_intake_snapshots.py` retained metadata-only
   snapshot artifacts under `artifacts/source_intake/`; first lawful public-source
   fields are filled from `EXTERNAL_SOURCE_PUBLIC_CAPTURE_V1.yaml`. The new
   `EXTERNAL_REPLAY_HYPOTHESES_V1.yaml` records 4 non-eligible replay hypotheses
   (2 spec candidates, 1 signal replay candidate, 1 non-reconstructable copy-trading
   row). The first canonical non-executing external candidate is retained at
   `strategies/external/3commas-dca-config/`; it validates with ambiguities and remains
   not reproduced, unvalidated, non-eligible, and `execution_authority=NONE`. Evidence:
   `artifacts/reports/EXTERNAL_SOURCE_INTAKE_SEED_2026_07_11.md`.
5. **UPDATE**: the external DCA candidate now has a local-only replay runner and
   retained frozen-data evidence:
   `scripts/run_external_dca_replay.py` and
   `artifacts/external_replay/3commas_dca/EXTDCA-9ed0a866cc1ddb5f7f4e7a94b5c5e48b/`.
   The run covers 6 BTCUSDT/ETHUSDT x 5m/15m/1h trials and 43,738 simulated local
   events. It remains unvalidated, non-eligible, and `execution_authority=NONE`;
   no platform bot, credential, account, paper/demo/live venue, or order route was
   used.
6. **UPDATE**: the dashboard now includes a structured inert Trading Domain product
   surface. `/api/v1/dashboard` exposes `trading_domain` with retained historical
   fill counts, disabled order/position/account/portfolio/risk rails, and a future
   demo-wallet activation predicate. The UI view is "Trading Domain"; all mutable
   capabilities are absent/disabled. Browser smoke passed at 375/768/1024/1440.
   A later v8.26 slice added the explicit `demo_wallet_design` readiness projection
   and UI sections for required future gates, allowed isolated-simulation scope, and
   must-never-include guardrails; it remains design-only with no ledger, mutation API,
   order route, venue connection, or execution authority.
   A later v8.28 slice added read-only S3/S4 gate-readiness cards. They make the
   blocked predicates and next human actions visible, but both stages remain
   `NOT_READY` and no activation/control path exists.
   A later v8.29 slice added `GET /api/v1/stage-gates` as the standalone read-only
   machine contract for the same blocked gate chain.
7. **UPDATE**: the dashboard now includes a local registry/report search product
   surface. `GET /api/v1/search` and the UI Search view project bounded concepts,
   ResearchAsset records, ResearchSource records, seed/external strategies, and
   retained Markdown reports. It is read-only and exposes writes, credentials, venue
   connection, order endpoint, and execution authority as disabled/absent/NONE.
8. **UPDATE**: the dashboard now includes a read-only Comparison product surface.
   `/api/v1/dashboard` projects `comparisons` from retained lab scorecards,
   validation gates, production G10 evidence, seed probes, seed-context G10, and
   cross-engine scope notes. The UI view is "Comparisons"; it selects no winner and
   exposes no approval, job, credential, venue, paper/demo/live, or order control.
9. **Human gates (operator-only)**: judge-calibration review (T-011-04 residual,
   `benchmarks/ai_agent/calibration/`), venue account eligibility (RG-05 human
   slice), HG-3/S2 exit (still blocked: no COMPLETE_APPROVABLE candidate — correct).
10. **Credential gates**: one AI provider key + spend cap unlocks T-011-05 (real
   benchmark, Mode A per `benchmarks/ai_agent/FROZEN_BENCHMARK_SUITE_V1.md`) and
   T-017-05 (cost telemetry — wire in the same change).
11. **Throughput tracks (unscheduled by design)**: Hummingbot chunked full-history
   (spec §3 acceptance), Nautilus full-history/latency scope expansion.
12. **Recurring**: T-001-06 registry sweep (due 2026-10-04), T-000-01/03/04 upkeep.

## What NOT to repeat

- Do not re-audit AD/docs/env (done 2026-07-11; see the 4 reports).
- Do not "fix" the workspace-decision POST route — D-038 approved it as-is.
- Do not rerun G10/reproduction unless inputs changed — both are deterministic and
  their artifacts are retained; the lab reuses idempotently on identical inputs.
- Do not treat any FAIL dimension as a bug: the negative results are the evidence.
- Never enable venue/paper/demo/live paths, credentials, or order routing — gates
  unchanged (D-036/D-037/AD §AA).

## Exact next action for the next session

The current AD, roadmap, TODO inventory, and live `/api/v1/status` projection show no
remaining actionable agent-executable S2 product/platform task: 0 open, 7 gated, 4
recurring. The completion audit is retained at
`artifacts/reports/AGENT_EXECUTABLE_COMPLETION_AUDIT_2026_07_11.md`.

Do not default to manual strategy replay/backtest operation; run additional research
cycles only when needed to verify a new application feature or after an explicit
research-direction decision changes inputs. The next finite work is credential/S3/HG/
human-gated: configure one AI provider key plus spend authority, or wait for a future
complete approvable strategy before preparing HG-3/paper-demo work. Keep all work
offline/historical and retain `NOT_ELIGIBLE` until all validation gates pass.
