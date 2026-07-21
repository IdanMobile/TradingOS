# Handoff — Continue from the funding-carry / market-neutral finding (2026-07-12)

**Status: SUPERSEDED on 2026-07-13 by D-045/D-046,
`docs/supervisor/SUPERVISORY_BASELINE_2026-07-13.md`, and
`docs/supervisor/IMPROVEMENT_PLAN_2026-07-13.md`. Do not execute this file's exact next action
or inherit its DSR, carry-edge, paper-divergence, venue, or validation claims. Current safe
stage is constrained offline S2; authenticated Bybit demo networking is quarantined; the
retained carry runs are static/model-limited hypotheses, not empirical G12 or validated edge.**

Audience: the next session (post-compaction), any AI. Read order: this file →
`docs/product/STRATEGY_RESEARCH_DIRECTION.md` (the CEO/CTO brief) → `PROJECT_STATE.md`
(dated entries at the end) → `research/SOURCE_REGISTRY.md` (strategy-discovery section)
→ `DECISION_LOG.md` D-041.

## Current objective and phase

Find a DSR-validated trading strategy without ever faking a pass. Constrained S2
research is still the phase; **no venue, no orders, no real money; `execution_authority`
stays NONE** (D-036/D-037/AD §AA). The operator is engaged and wants forward motion but
has repeatedly endorsed the discipline of NOT crossing gates or lowering thresholds.

## The one thing that matters — what we found

After ruling out every predictive price strategy, **funding-rate carry (delta-neutral
long-spot / short-perp) is the first REAL, robust, market-neutral edge.** Basis-aware
backtest (`scripts/run_funding_carry_basis.py`, 12 pairs, 6021 8h periods): best carry
+12.7%/yr, maxDD -0.5%, DSR 1.0 — **but `verdict_is_genuine: false`.** It genuinely
survives basis risk (a well-arbitraged perp tracks spot within ~0.1%), but Sharpe ~9 is
still inflated vs real-world ~2-4 because the model omits execution slippage, intraperiod
basis spikes, leverage/liquidation, and exchange COUNTERPARTY risk (the actual 2022
killer). **The remaining validation is EXECUTION-level (needs S3 paper trading) and
OPERATIONAL (counterparty = venue choice), NOT price prediction.** This makes carry the
evidence-backed candidate that justifies preparing HG-3/S3 and the S4 perp capability.

## The honest scoreboard (all through production-G10 DSR ≥ 0.95; NONE genuinely passed)

| Family | Best | DSR | Verdict | Runner |
|---|---|---|---|---|
| Predictive single-asset TA (2277 trials, vol-targeted) | Sharpe 1.46 | 0.69 | FAIL | `run_trend_validation.py` |
| Public-20 + signal-5 screen | 1 screen-pass | — | FAIL | `run_external_strategy_search.py`, `run_signal_strategy_search.py` |
| Universe search (25 strat × 43 datasets) | many "pass" screen | — | overfit artifact | `run_universe_search.py` |
| Cross-sectional momentum long-only | Sharpe 1.14 | 0.9456 | FAIL (fragile) | `run_cross_sectional_momentum.py` |
| Cross-sectional long-short | Sharpe 0.97 | 0.70 | FAIL | same |
| Stat-arb pairs (naive daily) | Sharpe 0.58 | 0.15 | FAIL | `run_stat_arb_pairs.py` |
| **Funding carry, single-exchange** | ~8.8%/yr | 1.0* | inflated | `run_funding_carry.py` |
| **Funding carry, basis-aware** | +12.7%/yr | 1.0* | *not genuine — S3/S4 next | `run_funding_carry_basis.py` |

## Verification state

`make check` = ruff + mypy-strict + **438 tests PASS** (last run this session). All
strategy runners are `scripts/run_*.py` + `data_profile.py` + `backtest_human_view.py`;
each has a `tests/test_*.py`. Every artifact under `artifacts/validation/<name>/` and
`artifacts/research_lab/<name>/` is stamped `execution_authority=NONE`.

## Key mechanics the next session MUST know (do not rediscover)

- **DSR estimator**: `src/tios/validation/multiple_testing.deflated_sharpe_ratio` +
  `sharpe_variance_from_trials`. Threshold 0.95. This is the gate; NEVER lower it.
- **Data pipeline (built this session)**: `tios.dataset.acquire` (checksum-verified,
  resumable; modes `plan`/`fetch`; kinds `klines,aggTrades,fundingRate,basis`),
  `normalize_multi` (klines→parquet in `data/normalized_multi/`), `tick_features`
  (aggTrades→1m microstructure), `daily_update` (REST append; writes
  `data/normalized_multi/daily_update_status.json`).
- **Data on disk**: spot klines 50/50 pairs (raw), funding 50 pairs, basis (spot8h+perp8h)
  12 pairs (`BASIS_PAIRS` in acquire.py), 1 tick-feature file. `normalized_multi/` has
  daily + some 1h/4h parquet (regenerate via `normalize_multi.normalize_pair` as needed).
  `data/normalized/` is the FROZEN bake-off set — NEVER mutate it (tests depend on it;
  `daily_update` targets ONLY `normalized_multi`).
- **Console**: `python -m tios.services.dashboard_ui.server`; Operations tab (data
  freshness + per-strategy results + governed "Refresh data now" trigger, D-041).
- **Scheduler**: `ops/install_daily_update.sh` (launchd). Works only after Full Disk
  Access granted to the uv python (project is in ~/Downloads = TCC-protected); operator
  granted it and the agent runs daily at 06:10.
- **graphify**: run `graphify update .` after code/doc changes. Sources are in the
  registry + 2 pulled into the corpus via `graphify add`.

## Remaining work, in priority order

1. **Wire funding carry into the S3 paper-probe lane** (`scripts/run_s3_paper_probe.py`
   pattern) to measure real execution/slippage on the carry candidate — the honest next
   validation step. Keep it `NOT_ELIGIBLE` / synthetic until HG-3.
2. **Professional stat-arb**: add in-sample cointegration test + rolling hedge ratio +
   1h frequency + BTC-ETH focus (naive daily failed at DSR 0.15; the pro version is
   untested and has literature Sharpe ~2.2). Data in hand.
3. **Risk-parity combination framework**: blend carry + stat-arb sleeves by equal risk
   contribution once ≥2 validate; caveat = correlations converge in crises.
4. **Operator decisions** (surface, don't cross): (a) authorize S3 paper run for carry;
   (b) the S4 perp/margin capability; (c) procure multi-exchange / order-book data (paid)
   for cross-exchange arb + realistic slippage.

## What NOT to do (hard-won)

- Do NOT keep spawning predictive price-strategy variants hoping one crosses 0.95 — that
  is p-hacking; single-asset/cross-sectional TA is rigorously ruled out.
- Do NOT lower the DSR threshold or claim a PASS is genuine when the risk model is
  incomplete (funding-carry PASS is inflated — see `verdict_is_genuine`).
- Do NOT connect a venue, enter credentials, or route orders. Do NOT mutate
  `data/normalized/` (frozen bake-off). Do NOT re-download the 50 pairs (present) or
  re-run deterministic failed searches.

## Exact next action

Build option 1: drive the funding-carry candidate through a synthetic S3 paper-probe to
measure execution/slippage (reuse `run_s3_paper_probe.py` structure + the basis-aware
carry P&L), keeping everything `NOT_ELIGIBLE` / `execution_authority=NONE`. In parallel,
option 2 (professional stat-arb). Then present the S3/S4/data decisions to the operator.
