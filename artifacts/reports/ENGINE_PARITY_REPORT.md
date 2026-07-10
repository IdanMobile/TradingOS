# Engine Parity Report

Status: **AVAILABLE LANES COMPLETE — missing lanes remain documented blockers.**

Comparable contexts: **3** · single-engine contexts: **28**.

## Comparable contexts

| Baseline | Scenario | Instrument | Scope | Engines | Classification | Fill counts |
|---|---|---|---|---|---|---|
| B1 | F0_S0 | BTCUSDT | FULL_CANONICAL_2021-01-01..2026-07-01 / PORTFOLIO_BTCUSDT | freqtrade, hummingbot | EXPECTED_EXECUTION_TIMING_DIVERGENCE | freqtrade:2, hummingbot:2 |
| B1 | F1_S1 | BTCUSDT | FULL_CANONICAL_2021-01-01..2026-07-01 / PORTFOLIO_BTCUSDT | freqtrade, hummingbot | EXPECTED_EXECUTION_TIMING_DIVERGENCE | freqtrade:2, hummingbot:2 |
| B2 | F0_S0 | BTCUSDT | FULL_CANONICAL_2021-01-01..2026-07-01 / PORTFOLIO_BTCUSDT | freqtrade, hummingbot | EXPLAINED_ENGINE_EXECUTION_AND_DATA_GAP_DIVERGENCE | freqtrade:132770, hummingbot:132924 |

## Interpretation

B1 Freqtrade/Hummingbot rows share the full BTCUSDT dataset and fill count, but
their boundary timestamps differ because Freqtrade fills on the next bar open while
Hummingbot's backtesting engine fills on the current bar close. The BTC-only B2
comparison removes the original Freqtrade BTC/ETH max-open-trade contention. Its
remaining fill-count divergence is retained as explained execution/order-state and
data-gap behavior in `B2_PARITY_RESIDUAL_REPORT.md`; it is not reduced to P&L.

Nautilus rows are retained as bounded engine evidence, not merged into full-period
parity. Aggregate profit is not compared where sizing, instrument sets, or mark-to-
market semantics differ.

## Coverage and blockers

- freqtrade: 15 pair-level contexts
- hummingbot: 3 pair-level contexts
- nautilus: 16 pair-level contexts
- LEAN execution requires a running Docker daemon.
- Nautilus evidence uses a bounded 2024-01-01..2024-01-14 window and is not full-period parity evidence.
- Hummingbot B3/B4 normalized artifacts are absent from the current worktree.

Machine-readable detail: `artifacts/bakeoff/parity/engine_parity.json`.
