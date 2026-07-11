# T-006-05 Hummingbot lane — blocker report (PARTIAL, updated 2026-07-11)

Status: **PARTIAL**, 2026-07-11. A prior attempt on this task hit a reproducible
`TypeError` in every attempted baseline and stopped short of a completed run. This
attempt found the precise root cause and fixed it without patching engine
internals. The current worktree retains complete B1 F0/S0 and F1/S1 runs plus a
complete B2 F0/S0 raw result recovered and normalized with an explicit recovery
manifest. B3/B4 artifacts are absent and are not claimed complete.

Docker was made available on 2026-07-11 and the first missing full-history run
(`B2 BTCUSDT F1/S1 run1`) was retried. The container consumed roughly one full
CPU core but hit the lane's 1800 second timeout before producing `raw.json`.
The orphaned Docker container was stopped manually. This is a runtime/throughput
blocker for the current full-history Hummingbot lane, not a credential or
paper/live blocker. Evidence:
`artifacts/reports/HUMMINGBOT_FULL_HISTORY_TIMEOUT_2026_07_11.md`.

Follow-up productionization on 2026-07-11 added bounded-window controls,
timeout cleanup with named containers, and a deterministic 30-day BTCUSDT
B1-B4 x `{F0/S0,F1/S1}` matrix across `bounded30_run1` and `bounded30_run2`.
This closes the bounded capability/regression lane while leaving full-history
completion as a throughput optimization track. Evidence:
`artifacts/reports/HUMMINGBOT_PRODUCTIONIZATION_STEP_2026_07_11.md`.

A cached full-history retry of `B2 BTCUSDT F1/S1` with a 3600 second timeout also
timed out, but wrote a `TIMEOUT` manifest and stopped the named container. The
same cache path completed the bounded 30-day B2 F1/S1 probe in about 32 seconds,
so the remaining gap is full-history throughput/chunking, not the bounded
capability lane.

## What blocked execution (prior attempts)
`BacktestingEngineBase.run_backtesting()` failed inside
`position_executor_simulator.simulate()` on every baseline that reached the
point of opening a position:

```
File ".../executors_simulator/position_executor_simulator.py", line 29, in simulate
    df_filtered = df[:tl_timestamp].copy()
TypeError: cannot do slice indexing on RangeIndex with these indexers [7916660700.0] of type float
```

## Actual root cause (confirmed by direct reproduction in the pinned image)
This is a **hummingbot 2.15.0 / pandas 3.0.3 compatibility bug**, not an
index-loss bug in `merge_asof` (the prior attempt's working theory):

1. pandas 3.0.3's `DataFrame.set_index()` silently returns a `RangeIndex`
   (not a plain `Index`) whenever the target column is an evenly-spaced
   **int64** sequence — confirmed directly:
   `pd.DataFrame({"timestamp":[100,400,700,1000]}).set_index("timestamp").index`
   → `RangeIndex(start=100, stop=1300, step=300)`. A **float64** column with
   the same values does *not* collapse — it stays a plain `Index`.
2. `BacktestingEngineBase.prepare_market_data()` calls exactly this
   `set_index("timestamp")` (via `BacktestingDataProvider.ensure_epoch_index`)
   on the post-`merge_asof` frame. Our injected candle timestamps were int64
   (whole epoch seconds), so this always produced a `RangeIndex`.
3. `simulate_execution`'s per-row loop sets
   `market_data_provider._time = row["timestamp"]` from `iterrows()`, which
   upcasts the entire row (mixed int/float columns) to `float64` — so
   `config.timestamp` (and therefore `tl_timestamp = config.timestamp + tl`)
   is a **float**, even though the source data is whole seconds.
4. `position_executor_simulator.simulate()`'s bare `df[:tl_timestamp]` slice
   (not `.loc[]`) on a `RangeIndex` explicitly rejects **float** slice bounds
   (`Index._validate_indexer`), even when the `RangeIndex`'s own values are
   integral. Hence the `TypeError`.

Reproduced live with a debug monkeypatch that printed `processed_features.index`
right after `prepare_market_data()` returned: `RangeIndex`, confirming (1)-(2);
and with a minimal pandas-only repro isolating the `set_index`/slice behavior.

## Fix (applied, no engine-internals patch)
`engines/hummingbot/_run_template.py::load_candles` now casts the injected
`timestamp` column to `float64` before anything reaches the engine
(`df["timestamp"] = df["timestamp"].astype(float)`). A float64 evenly-spaced
column never collapses to `RangeIndex`, so both the index and the
float `tl_timestamp` slice bound end up the same (non-Range) type and the
slice succeeds. This is a host-side data-shape change, not a monkeypatch of
`BacktestingEngineBase`/`position_executor_simulator` — it stays within the
project's "supported extension points only" convention. Marked with a
`ponytail:` comment noting the upgrade path (drop once hummingbot pins
`timestamp` to a fixed dtype internally).

## What still holds from the prior attempt
- Digest-pinned image `hummingbot/hummingbot@sha256:1b14fca4...` (see
  `engines/hummingbot/env_manifest.txt`).
- `PYTHONPATH=/home/hummingbot` import fix (now also applied inside
  `lane.py`'s docker invocation itself — the prior attempt's manual probes
  had it, but the lane script's own command line was missing it, causing a
  fresh `ModuleNotFoundError` on the first full-matrix run this attempt).
- The `DirectionalTradingControllerBase` signal-based controller
  (`engines/hummingbot/_run_template.py`) reproducing B1-B4 formulas
  bar-for-bar via the supported `stop_actions_proposal` extension point.

## Artifacts
- `src/tios/adapters/hummingbot/lane.py` — host-side orchestrator.
- `src/tios/adapters/hummingbot/normalize_result.py` — raw.json → trades/
  equity/normalized_metrics `NormalizedResult` artifacts (new this attempt).
- `engines/hummingbot/_run_template.py` — in-container runner with the fix.
- `artifacts/bakeoff/hummingbot/B1/BTCUSDT/{F0_S0,F1_S1}/run1/` — complete normalized runs.
- `artifacts/bakeoff/hummingbot/B2/BTCUSDT/F0_S0/run1/` — complete raw result plus recovered normalized artifacts; host command provenance was interrupted and is explicitly unavailable.
- Full-history B2 F1/S1, B3/B4, and Hummingbot full-history determinism reruns
  remain open under the 2026-07-11 runtime/throughput blocker, including the
  cached 3600 second timeout.
- Bounded 30-day B1-B4 x `{F0/S0,F1/S1}` run1/run2 evidence is complete and
  deterministic.
