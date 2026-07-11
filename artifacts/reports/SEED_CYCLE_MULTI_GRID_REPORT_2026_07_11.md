# Seed Cycle Multi-Grid Report — 2026-07-11

## Scope

This report records the D-040 AI-decided offline A/B test: run the five reproduced
seed candidates across the full frozen crypto-spot grid:

- BTCUSDT and ETHUSDT
- 5m, 15m, and 1h
- the same next-open, all-in, fee-aware proxy used by the seed cycle

No venue, credential, paper/demo/testnet, order route, live trading, or real-money
capability was used or enabled.

## Evidence

- Cycle:
  `artifacts/research_lab/seed_cycle_v0/SEEDCYCLE-9b1652a62996fda4b753c6695f43569ab860acd8decb48c9c5994566f4a6488f/`
- Status: `COMPLETED`
- Counts: 5 candidates, 6 datasets, 258 trials, 5 evidence records
- Execution authority: `NONE`
- Winner selected: `false`
- Reuse check: `uv run python scripts/run_seed_research_cycle_v0.py` returned the
  same cycle with `reused: true`

## Best proxy rows

| Rank | Candidate | Dataset | Parameters | Total return | Trades |
|---:|---|---|---|---:|---:|
| 1 | STRAT-QC2-donchian-breakout | ETHUSDT_1h | window=40 | 1.4911659432022965 | 553 |
| 2 | STRAT-QC2-donchian-breakout | BTCUSDT_1h | window=80 | 0.2071731415899850 | 284 |
| 3 | STRAT-FT1-sample-strategy | ETHUSDT_15m | rsi_window=21,rsi_threshold=20 | 0.1937609034996807 | 184 |
| 4 | STRAT-FT1-sample-strategy | ETHUSDT_5m | rsi_window=21,rsi_threshold=20 | 0.1380578244405416 | 510 |
| 5 | STRAT-FT1-sample-strategy | BTCUSDT_1h | rsi_window=21,rsi_threshold=20 | 0.0694584993017005 | 32 |

## Interpretation

The original 5m-only reproduced seed population was dominated by fee churn. The
D-040 grid shows the expected effect: lower-frequency contexts reduce churn, and a
small number of proxy configurations become positive. This is a research signal,
not validation.

The strongest proxy context is `STRAT-QC2-donchian-breakout` on `ETHUSDT_1h` with
`window=40`. It is still `UNVALIDATED` and `NOT_ELIGIBLE` because it has not passed
out-of-sample/walk-forward, parameter-neighborhood robustness, multiple-testing
selection-bias controls, cross-engine reproduction, red-team review, or paper/demo
divergence checks.

## Next offline step

Under D-039, the next AI-decided research direction is to build retained validation
evidence for the top positive proxy contexts, starting with:

1. `STRAT-QC2-donchian-breakout`, `ETHUSDT_1h`, `window=40`
2. `STRAT-QC2-donchian-breakout`, `BTCUSDT_1h`, `window=80`
3. `STRAT-FT1-sample-strategy`, `ETHUSDT_15m`, `rsi_window=21`, `rsi_threshold=20`

Stop before any HG-3, paper/demo wallet, venue connection, credential use, order
routing, live trading, or real-money path.

## Validation-probe follow-through

The first validation-probe artifact is retained at:

`artifacts/validation/seed_candidates/SEED_VALIDATION_PROBE_2026_07_11.json`

It covers the three positive proxy contexts above with chronological thirds,
fee stress, buy-and-hold comparison, and parameter-neighborhood evidence.

Current read:

- `STRAT-QC2-donchian-breakout`, `ETHUSDT_1h`, `window=40` remains the only
  context that is positive in all three chronological thirds and beats the
  full-period buy-and-hold proxy under the normal fee setting. It is still
  fragile: the immediate parameter neighborhood is mostly negative.
- `STRAT-QC2-donchian-breakout`, `BTCUSDT_1h`, `window=80` has a positive full
  period, but the final-third holdout is negative and it does not beat buy-and-hold.
- `STRAT-FT1-sample-strategy`, `ETHUSDT_15m`, `RSI(21)<20` has a positive full
  period, but the final-third holdout is negative and it does not beat buy-and-hold.

All three contexts remain `UNVALIDATED` / `NOT_ELIGIBLE`.

## G10 follow-through

Production-style G10 evidence for the surviving probe context is retained at:

`artifacts/validation/seed_candidates/SEED_G10_QC2_ETHUSDT_1H_2026_07_11.json`

Verdict: **FAIL**.

- Selected context: `STRAT-QC2-donchian-breakout`, `ETHUSDT_1h`, `window=40`
- Searched population: QC2 windows `{10,20,40,80}` on `ETHUSDT_1h`
- PBO: `0.2613830613830614`
- DSR: `0.7564434755513448`
- Rule: PASS requires PBO <= `0.5` and DSR >= `0.95`

The context remains rejected for promotion use. It was the strongest proxy row, but
the deflated Sharpe evidence is insufficient after accounting for the searched grid.
