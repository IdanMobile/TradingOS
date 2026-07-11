# Hummingbot full-history timeout recheck — 2026-07-11

## Summary

Docker was available and the Hummingbot full-history lane was retried from the
current retained worktree. The first missing run, `B2 BTCUSDT F1/S1 run1`,
started in the digest-pinned/local-candle container path and consumed roughly one
full CPU core, but did not produce `raw.json` before the lane's initial
1800-second timeout.

A follow-up productionization pass added bounded-window controls, deterministic
container names, timeout cleanup, and cached feature computation in the
Hummingbot runner. The cache proved the bounded 30-day B2 F1/S1 window can
complete in about 32 seconds with unchanged fills/fee audit results. The same
cached runner was then retried on the full 2021-01-01..2026-07-01 history with a
3600-second timeout. It still timed out, wrote a clean `TIMEOUT` manifest, and
stopped the named container.

This is a runtime/throughput blocker for the full-history Hummingbot matrix, not
a credential, paper/demo/testnet, venue, order-routing, live-trading, or
real-money blocker.

## Command

```bash
uv run python -m tios.adapters.hummingbot.lane \
  --pairs BTCUSDT \
  --baselines B2 \
  --scenarios F1/S1 \
  --run-tag run1
```

Cached full-history retry:

```bash
uv run python -m tios.adapters.hummingbot.lane \
  --pairs BTCUSDT \
  --baselines B2 \
  --scenarios F1/S1 \
  --run-tag full_cached_run1 \
  --timeout-seconds 3600
```

The lane invoked Docker with local frozen candles:

```text
python /lane/_run.py --baseline B2 --trading-pair BTC-USDT \
  --csv /lane/data/BTCUSDT_5m.csv \
  --start 1609459200 --end 1782864000 \
  --trade-cost 0.001 --out /out/raw.json
```

## Evidence

- Input conversion completed: `BTCUSDT_5m.csv: 577803 rows from BTCUSDT_5m.parquet`.
- Container observed active at about one full CPU core for the run.
- Host process raised `subprocess.TimeoutExpired` after 1800 seconds.
- `artifacts/bakeoff/hummingbot/B2/BTCUSDT/F1_S1/run1/` remained empty; no
  `raw.json`, manifest, or normalized artifacts are claimed.
- The orphaned Docker container left by the timeout was stopped manually with
  `docker stop priceless_almeida`.
- Cached bounded 30-day probe `cache_probe30` completed successfully in about
  32 seconds and matched the bounded matrix counts.
- Cached full-history retry wrote
  `artifacts/bakeoff/hummingbot/B2/BTCUSDT/F1_S1/full_cached_run1/manifest.json`
  with `status=TIMEOUT`, `timed_out=true`, `timeout_seconds=3600`,
  `stopped_container=true`, and full window
  `2021-01-01T00:00:00+00:00..2026-07-01T00:00:00+00:00`.
- No named Hummingbot container remained running after the cached timeout.

## Follow-up

Do not rerun the same full-history command blindly. Possible evidence-only
follow-ups are:

1. Keep the bounded-window Hummingbot lane as the current capability/regression
   evidence path.
2. Design a chunked or profiled full-history Hummingbot path before widening the
   timeout again.
3. Keep Hummingbot B3/B4 and full-history determinism as retained full-history
   throughput blockers until that design exists.
