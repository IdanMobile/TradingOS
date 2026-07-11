# External Source Intake Seed — 2026-07-11

Status: **RETAINED / HYPOTHESIS ONLY**.

This report records the first application-owned source-registry expansion for the
external strategy/source classes approved in AD §U:

- exchange-hosted bot marketplaces;
- copy-trading and copy-investing leaderboards;
- online signal or idea feeds;
- third-party bot platforms.

## Seeded sources

| source_id | class | canonical URL | hypothesis family |
|---|---|---|---|
| `SRC-BINANCE-TRADING-BOTS` | exchange bot marketplace | `https://www.binance.com/en/trading-bots` | `exchange_bot_replay` |
| `SRC-BINANCE-COPY-TRADING` | copy-trading leaderboard | `https://www.binance.com/en/copy-trading` | `copy_trading_replay` |
| `SRC-TRADINGVIEW-IDEAS` | online signal feed | `https://www.tradingview.com/ideas/` | `signal_replay` |
| `SRC-3COMMAS-DCA-BOT` | third-party bot platform | `https://3commas.io/dca-bots` | `bot_platform_replay` |

## Boundaries

Every new row in `research/PRIMARY_STRATEGY_RESEARCH_SOURCES_V1.yaml` is
machine-validated as:

- `evidence_strength: hypothesis_only`;
- `profit_claims_inherited: false`;
- `locally_reproduced: false`;
- `approval_eligible: false`;
- no DOI required for non-paper platform pages;
- no credential, account connection, subscription, copy action, order route, paper
  venue, demo wallet, live trading, or real-money path.

These sources can only feed future offline capture, canonicalization, replay, and
validation work. They cannot approve or execute a strategy.

## Offline intake plans

`research/EXTERNAL_SOURCE_INTAKE_PLANS_V1.yaml` now records one validated plan per
seeded source. Each plan links back to a source record, declares a capture mode,
points to a future artifact path under `artifacts/source_intake/`, and must carry
the full S2 prohibition set:

- `credential_request`;
- `account_connection`;
- `subscription_or_copy_action`;
- `order_routing`;
- `paper_demo_or_live_activation`;
- `profit_claim_inheritance`.

The dashboard read model exposes the plan counts only:

- 4 total plans;
- 3 ready for offline capture;
- 1 design-only plan (`SRC-BINANCE-COPY-TRADING`, because copy trading can imply
  account behavior and therefore stays extra constrained).

## Metadata-only snapshots

`scripts/build_external_source_intake_snapshots.py` generated the first local
metadata-only artifacts from the source and plan registries:

- `artifacts/source_intake/EXTERNAL_SOURCE_INTAKE_INDEX_2026_07_11.json`;
- `artifacts/source_intake/binance_trading_bots/metadata_snapshot.json`;
- `artifacts/source_intake/binance_copy_trading/replay_design.json`;
- `artifacts/source_intake/tradingview_ideas/signal_candidates.json`;
- `artifacts/source_intake/3commas_dca_bot/config_hypotheses.json`.

These snapshots intentionally do not fetch platform content at runtime. They carry
known local registry metadata, lawful public-source capture fields, remaining
pending-capture fields, source risks, validation prerequisites, and the full S2
prohibition set.

`research/EXTERNAL_SOURCE_PUBLIC_CAPTURE_V1.yaml` records the public-source facts
used to fill snapshot fields:

- Binance Trading Bots: visible bot families include grid, DCA, arbitrage,
  rebalancing, algo-order, TWAP, and VP surfaces; the page also exposes market
  sections such as Spot/Futures and leaderboard-style discovery.
- Binance Copy Trading: the public copy-trading surface exposes lead-trader/
  portfolio performance and risk concepts such as ROI/PnL, maximum drawdown,
  Sharpe ratio, AUM, profit share, and copy behavior.
- TradingView Ideas: public idea pages can expose symbols, publication/update
  metadata, long/short or thesis direction, and mixed prose/rule-like entry,
  target, stop, or trade-management details.
- 3Commas DCA Bot: public product/help surfaces describe DCA bot configuration
  concepts, historical-data backtesting claims, and exchange integrations.

All of those facts remain source metadata. They are not copied signals, not
strategy approval, and not local performance evidence.

## Replay hypotheses

`research/EXTERNAL_REPLAY_HYPOTHESES_V1.yaml` translates the captured source
metadata into four explicit offline replay-hypothesis records:

- `RPH-BINANCE-SPOT-GRID-CONFIG` — a Binance spot-grid configuration reconstruction
  candidate with missing price-range, grid-count, sizing, and trigger semantics.
- `RPH-BINANCE-COPY-TRADING-OPAQUE` — a copy-trading metadata row deliberately marked
  `non_reconstructable` until lawful historical actions, sizing, exposure, fees,
  leverage, and survivorship history exist.
- `RPH-TRADINGVIEW-RULED-SIGNAL-REPLAY` — a TradingView ruled-idea replay candidate
  that requires an individual idea URL and explicit timestamp/symbol/rule fields.
- `RPH-3COMMAS-DCA-CONFIG` — a DCA configuration reconstruction candidate with
  missing entry, safety-order, take-profit, stop, and exposure semantics.

Every replay hypothesis has `execution_authority: NONE`,
`profit_claims_inherited: false`, and `approval_eligible: false`. These are candidate
work items for future offline specification and validation, not strategies.

## First external replay candidate spec

`strategies/external/3commas-dca-config/` now retains the first canonical
non-executing external replay candidate:

- `source_record.yaml`;
- `license_record.yaml`;
- `canonical_strategy_spec.yaml`;
- `ambiguities.md`;
- `framework_assumptions.md`;
- `reproduction_status.md`;
- `replay_candidate.yaml`.

The candidate `STRAT-EXT-3COMMAS-DCA-CONFIG` is a local DCA hypothesis using
RSI(14)<35 as an OS-local entry trigger, staged drawdown add-on metadata, SMA(20)
recovery exit, and a 12% local stop. It validates as
`VALID_WITH_AMBIGUITIES`, but remains `SPECIFIED_NOT_REPRODUCED`,
`UNVALIDATED`, `promotion_eligible=false`, and `execution_authority=NONE`.
The dashboard strategy projection includes it as `external_replay` for visibility
only.

## First local external replay

`scripts/run_external_dca_replay.py` now replays the 3Commas-style DCA hypothesis
against the frozen BTCUSDT/ETHUSDT x 5m/15m/1h candle grid, using only local
historical data and next-open execution semantics. Retained evidence:

- `artifacts/external_replay/3commas_dca/EXTDCA-9ed0a866cc1ddb5f7f4e7a94b5c5e48b/replay_run.json`;
- `artifacts/external_replay/3commas_dca/EXTDCA-9ed0a866cc1ddb5f7f4e7a94b5c5e48b/scorecard.json`;
- one events JSONL artifact per dataset.

The retained run covers 6 trials and 43,738 local entry/add/exit events. It is
`EVIDENCE_RETAINED_NOT_VALIDATED`: no platform bot was created, no account or
credential was used, no paper/demo/live path was enabled, and the candidate remains
`UNVALIDATED`, `promotion_eligible=false`, and `execution_authority=NONE`.

## Verification

- `uv run pytest tests/test_research_source_registry.py tests/test_dashboard.py tests/test_research_lab_v0.py tests/test_validation_package.py -q`
  passed after the registry expansion.
- `uv run pytest tests/test_external_source_intake_plans.py tests/test_research_source_registry.py tests/test_dashboard.py -q`
  passed after the intake-plan registry and dashboard projection were added.
- `uv run pytest tests/test_external_source_intake_plans.py tests/test_dashboard.py -q`
  passed after the replay-hypothesis registry and dashboard read-model counts were added.
- `uv run pytest tests/test_external_replay_candidate_specs.py tests/test_external_source_intake_plans.py tests/test_dashboard.py -q`
  passed after the 3Commas DCA external replay spec and dashboard strategy projection were added.
- `uv run python scripts/run_external_dca_replay.py` retained the first local DCA
  replay artifact (`EXTDCA-9ed0a866...`) across 6 frozen datasets.
- `uv run pytest tests/test_external_dca_replay.py tests/test_external_replay_candidate_specs.py -q`
  passed after the local DCA replay runner and retained-artifact guard tests were added.
- `make required` passed after the external DCA candidate layer: Ruff, format,
  mypy-strict, 334 tests, and pip-audit.
- `uv run python scripts/build_external_source_intake_snapshots.py --captured-at 2026-07-11T00:00:00Z`
  retained the first metadata-only snapshot artifacts with lawful public-source
  fields filled from `EXTERNAL_SOURCE_PUBLIC_CAPTURE_V1.yaml`.
- Playwright responsive smoke against `http://127.0.0.1:8765/` passed at widths
  375, 768, 1024, and 1440 after the external DCA projection update: no page/console
  errors, no horizontal overflow, and the replay count plus external candidate
  rendered in the DOM.
- Offline lab batch `LAB-f04ef5d705e0de4d3fff5fe83ada90b2d91223dc89cfa35364c5fd8439ca3121`
  was retained with the new source-registry digest. It still selected no winner and
  kept `execution_authority=NONE`.
