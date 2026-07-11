# Hummingbot lane productionization step — 2026-07-11

## What changed

The Hummingbot lane now has safer execution controls:

- explicit `--start-date`, `--end-date`, and `--window-days` controls;
- explicit `--timeout-seconds`;
- named Docker containers per run;
- timeout handling that stops the named container and writes a `TIMEOUT` manifest;
- window metadata retained in each run manifest.

This keeps the Hummingbot path offline and evidence-only. It does not add broker
credentials, paper/demo/testnet exchange connectivity, order routing, live
trading, or real-money authority.

## Bounded matrix evidence

Command shape:

```bash
uv run python -m tios.adapters.hummingbot.lane \
  --pairs BTCUSDT \
  --baselines B1,B2,B3,B4 \
  --scenarios F0/S0,F1/S1 \
  --run-tag bounded30_run1 \
  --end-date 2026-07-01 \
  --window-days 30 \
  --timeout-seconds 900
```

The same command was repeated as `bounded30_run2`.

Window: `2026-06-01..2026-07-01`, `8640` BTCUSDT 5m rows.

All 16 bounded cells completed and normalized:

| Baseline | Scenario | Fills | Roundtrips | Fee audit |
|---|---:|---:|---:|---|
| B1 | F0/S0, F1/S1 | 2 | 1 | PASS |
| B2 | F0/S0, F1/S1 | 1942 | 971 | PASS |
| B3 | F0/S0, F1/S1 | 2622 | 1311 | PASS |
| B4 | F0/S0, F1/S1 | 1104 | 552 | PASS |

Determinism: run1/run2 SHA-256 hashes match for `trades.parquet`,
`equity.parquet`, and `normalized_metrics.json` for every baseline/scenario.
Evidence:
`artifacts/bakeoff/hummingbot/BOUNDED30_DETERMINISM_RUN1_RUN2.json`.

## Remaining production-readiness gap

Feature caching reduced the bounded 30-day B2 BTCUSDT F1/S1 path to about
32 seconds with unchanged fills and fee-audit evidence. The same cached runner
still timed out on the full 2021-01-01..2026-07-01 history after 3600 seconds,
but the lane wrote a clean `TIMEOUT` manifest and stopped its named container.

The bounded lane is now suitable for capability/regression evidence;
full-history Hummingbot remains a throughput optimization track, not an approval
dependency.
