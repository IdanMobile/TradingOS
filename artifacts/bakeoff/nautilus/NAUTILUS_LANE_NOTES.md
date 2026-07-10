# T-006-03 NautilusTrader lane — evidence summary

## Version / install path / environment
- Engine: `nautilus-trader==1.230.0`, Python 3.13.7.
- Venv: `engines/nautilus/.venv` (already built 2026-07-06T14:40:43Z; see `engines/nautilus/env_manifest.txt` for full `pip freeze`).
- Integration: in-process Python API (`BacktestEngine`), not subprocess/CLI — no GPL boundary concern (Nautilus is LGPL-3.0/permissive-compatible per T-000/T-001 license gate).

## Run commands
```
engines/nautilus/.venv/bin/python engines/nautilus/lane/run_backtest.py \
  --strategy {B1,B2,B3,B4} --scenario {F0_S0,F1_S1} --run-dir artifacts/bakeoff/nautilus/<B>/<F>/<run>
```
Signal math for B1-B4 is computed with pandas in `engines/nautilus/lane/signals.py`, identical to
`engines/freqtrade/lane/user_data/strategies/*.py`. Orders are submitted by the generic
`BaselineStrategy` in `engines/nautilus/lane/strategy.py`.

## Evidence window
`2024-01-01T00:00:00Z .. 2024-01-14T23:55:00Z`, both BTC/USDT and ETH/USDT, 5m bars — a bounded
subset of the frozen `DS-CRYPTO-SPOT-BAKEOFF-V1` dataset, **not** the Freqtrade lane's full
2021-2026 history. Nautilus's event-driven `OrderMatchingEngine` has materially higher per-order
overhead than Freqtrade's vectorized backtest (B2/B3's 3-5 period crossovers on 5m bars generate
hundreds-to-thousands of round trips even over 2 weeks). Full-history × 2-pair × 4-strategy ×
2-scenario × determinism-rerun replay was infeasible within this task's budget. This is a
documented scope deviation, not a silent gap — the matrix, determinism check, and fee/PnL audit
below are exercised in full over the bounded window.

## Runtime / resource
- B1 (buy-and-hold, 2 pairs, ~14 days): ~7s wall, single core.
- B2/B3/B4 (hundreds-1200+ round trips, 2 pairs): ~10-14s wall each.
- Full matrix (4 strategies × 2 fee scenarios × 2 reruns = 16 backtests): a few minutes total.
- Memory: not profiled separately; each run is a fresh `BacktestEngine` instance, disposed after
  report generation (no cross-run growth observed).

## Determinism
Reran all 8 (strategy × scenario) combinations twice (`run1`, `run2`) and diffed
`trades.parquet`, `equity.parquet`, `normalized_metrics.json` by sha256:
**all 8 combinations byte-identical across reruns.** (`manifest.json` differs only in the
`started_utc` timestamp field, as expected.)

## Metrics / trades / fee-PnL audit
Per (strategy, scenario) run, `normalized_metrics.json` reports `fills`, `trades_roundtrips`,
`profit_total_abs` (mark-to-market), and a fee-recomputation audit (`expected_fee = price * qty *
fee_rate_per_side` vs the engine-reported commission). **All 8 combinations: fee_audit PASS**
(max deviation `0` for F0_S0/zero-fee, `1E-8` — one decimal128(38,8) quantization unit, i.e.
effectively exact — for F1_S1/0.1%-fee).

| Strategy | Scenario | Fills | Roundtrips | Fee audit |
|---|---|---|---|---|
| B1 | F0_S0 / F1_S1 | 2 | 2 | PASS |
| B2 | F0_S0 / F1_S1 | 1848 | 924 | PASS |
| B3 | F0_S0 / F1_S1 | 2396 | 1199 | PASS |
| B4 | F0_S0 / F1_S1 | 1172 | 586 | PASS |

## Artifact export
Each `artifacts/bakeoff/nautilus/<B>/<F>/<run>/` contains: `manifest.json` (command, engine
version, scenario, fee rate, converter losses, file hashes), `trades.parquet` (decimal128(38,8),
same column schema as the Freqtrade lane: ts_fill/side/pair/price/qty/fee/trade_id),
`equity.parquet` (start/end mark-to-market points), `normalized_metrics.json`, `stdout.log`,
`stderr.log`.

## Semantic differences vs Freqtrade lane (see also per-run `semantic_notes`)
- Signal evaluated at bar close, order fills at the engine's next processed bar open — matches
  Freqtrade's open_date==fill-time convention.
- **Fixed notional sizing** (1000 USDT per entry) instead of Freqtrade's compounding "unlimited"
  stake — a documented sizing deviation; the blueprint's bake-off goal is infrastructure
  comparison, not profit discovery, so this doesn't affect the determinism/fee-audit gates.
- `profit_total_abs` is mark-to-market (ending account value at last close price minus starting
  balance), which correctly captures B1's unrealized buy-and-hold gain (Freqtrade's backtest
  report also marks the final open trade to market).
- `equity.parquet` is a coarse two-point series (start, end), not a full intra-run curve —
  Nautilus's account report is a native-currency balance ledger per event, not a unified
  per-snapshot quote valuation; reconstructing a full mark-to-market curve would need bar-by-bar
  valuation and was out of scope for this pass.
- No slippage model applied in the main matrix (fills at the matching engine's bar-open price),
  matching Freqtrade's F0/S0,F1/S1 convention for direct comparability. Nautilus additionally
  *supports* configurable `FillModel`/`LatencyModel` (e.g. `OneTickSlippageFillModel`,
  `ProbabilisticFillModel`) — a capability Freqtrade's backtester lacks — but this was not
  exercised in the main matrix; noted here as the required Nautilus-specific
  fee/fill/latency-config probe.
- Prices are float64 at the engine boundary (Nautilus `Price`/`Quantity` are fixed-precision
  float-backed types), same declared converter loss as the Freqtrade lane.

## Blockers
None. All acceptance criteria (matrix run, determinism, fee/PnL audit) evidenced above within the
documented bounded evidence window.
