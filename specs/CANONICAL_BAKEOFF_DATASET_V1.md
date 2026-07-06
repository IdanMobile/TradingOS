# Canonical Bake-Off Dataset V1

Status: Approved specification for coding-agent execution.
Purpose: create one frozen, reproducible dataset package used across engine comparisons.

## Scope

Market family: Crypto Spot
Instruments:
- BTCUSDT
- ETHUSDT

Required timeframes:
- 5m
- 15m
- 1h

Primary source:
- Binance public Spot data (`data.binance.vision` / `binance-public-data`).

## Calendar window

Use a fixed multi-regime window ending before the current execution date. The coding agent must choose the longest common, clean coverage available for both instruments and all required intervals, with this target:

- Preferred: 2021-01-01T00:00:00Z through 2026-06-30T23:59:59Z
- Minimum acceptable: 2022-01-01T00:00:00Z through 2026-06-30T23:59:59Z

If exact source availability prevents the preferred window, record the reason and use the maximum common intersection. Do not silently change dates.

## Raw snapshot rules

1. Download source files without transformation into `data/raw/binance_spot/`.
2. Preserve source filenames.
3. Record source URLs.
4. Record download timestamp.
5. Generate SHA-256 for every raw file.
6. Do not overwrite raw files.
7. Store a manifest.

## Canonical normalized schema

```text
timestamp_open_utc
open
high
low
close
volume_base
close_timestamp_utc
quote_volume
trade_count
taker_buy_base_volume
taker_buy_quote_volume
source
instrument
interval
```

Rules:
- timestamps normalized to UTC;
- decimal precision preserved as much as practical;
- no forward fill of missing candles without an explicit derived dataset version;
- deduplicate only through an explicit transformation step;
- retain raw source separately.

## Quality checks

Required:
- monotonic timestamps;
- no duplicate open timestamps;
- expected interval spacing;
- OHLC invariants (`low <= open/close <= high`);
- non-negative volume;
- missing-interval report;
- source-file checksum verification;
- timezone verification;
- row counts by instrument/interval/month.

## Frozen dataset identity

Create:

```text
dataset_id: DS-CRYPTO-SPOT-BAKEOFF-V1
manifest_version: 1
source: Binance public Spot data
```

Identity must include:
- exact source files;
- SHA-256 list;
- normalization code commit;
- normalized artifact hash;
- coverage start/end;
- quality report hash.

## Split policy

The engine infrastructure bake-off may run the full frozen set because profitability is not the selection criterion.

Strategy validation must use temporal splits defined by the Backtesting Validation Blueprint. Do not tune on the final holdout.

## Acceptance gates

PASS only if:
- all raw files have hashes;
- normalized schema is identical across instruments;
- quality report exists;
- missing intervals are explicitly reported;
- dataset can be regenerated from manifest and code;
- two independent reruns produce identical normalized hashes.

## Non-goals

V1 is not:
- tick data;
- L2/L3 order book data;
- proof of realistic execution;
- final production data source.

---

## Amendment A1 — 2026-07-06 (per D-029)

Verified against the official binance-public-data repository on 2026-07-06: Binance SPOT data files switched timestamp columns from **milliseconds to microseconds starting with files dated 2025-01-01**. Consequences, binding on implementation:

1. Normalization must detect the timestamp unit explicitly per file (never infer silently from magnitude alone without recording the detection result in the quality report).
2. The canonical normalized schema remains UTC datetimes; both unit regimes must converge to identical representation.
3. A golden test must cover a window spanning the 2024-12-31 → 2025-01-01 boundary for every instrument/interval that crosses it.
4. The quality report must state, per source file, which unit was detected.
