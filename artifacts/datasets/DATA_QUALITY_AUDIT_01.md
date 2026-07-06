# DATA_QUALITY_AUDIT_01 — DS-CRYPTO-SPOT-BAKEOFF-V1

**Verdict: PASS_WITH_NOTES**

- Auditor: independent data-quality auditor (SKILL_DATA_QUALITY_AUDITOR, task T-004-05, REQ-010)
- Date: 2026-07-06
- Scope: frozen dataset DS-CRYPTO-SPOT-BAKEOFF-V1 (Binance public Spot klines, BTCUSDT + ETHUSDT, 5m/15m/1h, 2021-01 → 2026-06)
- Method: all figures below were **recomputed independently** with ad-hoc `uv run python` scripts (hashlib, zipfile/csv, duckdb). The producer's quality module was not rerun; its outputs were only used as claims to verify against.
- No discrepancies in data, hashes, row counts, coverage, or gap structure. Two informational notes (see Notes).

---

## Check 1 — Raw zip SHA-256 (random sample + boundary files): PASS

Recomputed SHA-256 (hashlib, 1 MiB chunks) and file size for 30 of 396 zips:
20 random (seed 20260706) plus **all 12** files at the 2024-12/2025-01 boundary
(2 symbols x 3 intervals x 2 months — superset of the 4 required), compared to
`data/raw/binance_spot/raw_manifest.json`.

- Sample covered both symbols and all three intervals.
- Result: **30/30 exact sha256 and size matches, 0 mismatches.**
- Boundary examples: `BTCUSDT-1h-2024-12.zip` dfec812f73a84257…, `BTCUSDT-1h-2025-01.zip` e7f2aaa5396a8062…, `ETHUSDT-5m-2024-12.zip` f02545d5f40476d5…, `ETHUSDT-5m-2025-01.zip` 356e860d31d3bf5c… — all match manifest.

## Check 2 — Parquet row counts and coverage (independent duckdb): PASS

Own queries: `SET TimeZone='UTC'; select count(*), min(timestamp_open_utc), max(timestamp_open_utc), count(*)-count(distinct timestamp_open_utc) from '<parquet>'`.

| table | rows (recomputed) | rows (manifest) | min open UTC | max open UTC | dup opens |
|---|---|---|---|---|---|
| BTCUSDT_5m | 577,803 | 577,803 | 2021-01-01 00:00:00 | 2026-06-30 23:55:00 | 0 |
| BTCUSDT_15m | 192,602 | 192,602 | 2021-01-01 00:00:00 | 2026-06-30 23:45:00 | 0 |
| BTCUSDT_1h | 48,154 | 48,154 | 2021-01-01 00:00:00 | 2026-06-30 23:00:00 | 0 |
| ETHUSDT_5m | 577,803 | 577,803 | 2021-01-01 00:00:00 | 2026-06-30 23:55:00 | 0 |
| ETHUSDT_15m | 192,602 | 192,602 | 2021-01-01 00:00:00 | 2026-06-30 23:45:00 | 0 |
| ETHUSDT_1h | 48,154 | 48,154 | 2021-01-01 00:00:00 | 2026-06-30 23:00:00 | 0 |

All 6 tables match `DS-CRYPTO-SPOT-BAKEOFF-V1.manifest.json` rows and coverage exactly.

## Check 3 — ms/µs boundary spot-check (raw CSV vs parquet, decimal-exact): PASS

Opened raw zips myself (zipfile + csv), took first/last rows of
`BTCUSDT-1h-2024-12`, `BTCUSDT-1h-2025-01`, `ETHUSDT-5m-2024-12`, `ETHUSDT-5m-2025-01`,
converted the open_time epoch by hand and located the row in the parquet by exact UTC timestamp.
Hand-verified anchors: 2024-12-01 00:00 UTC = 1733011200**000** (ms); 2025-01-01 00:00 UTC = 1735689600**000000** (µs) — matching Amendment A1 (ms ≤ 2024-12, µs ≥ 2025-01).

String-exact comparison on 6 fields (open, high, low, close, volume_base, trade_count) for all 8 rows — **all match**, e.g.:

- BTCUSDT 1h, epoch 1735686000000 (ms) → 2024-12-31 23:00 UTC: raw 93488.83000000/93756.00000000/93375.38000000/93576.00000000/336.57995000/68135 == parquet.
- BTCUSDT 1h, epoch 1735689600000000 (µs) → 2025-01-01 00:00 UTC: raw 93576.00000000/94509.42000000/93489.03000000/94401.14000000/755.99010000/93525 == parquet. (Close of last ms bar 93576.00 = open of first µs bar — continuous across the unit switch.)
- ETHUSDT 5m boundary rows likewise exact (e.g. 2024-12-31 23:55 UTC: 3340.49/3342.32/3337.43/3337.78, 264.43280000, 1574).

## Check 4 — Downtime gap cross-check: PASS

QUALITY_REPORT.json `missing_interval_report` lists 7 gaps per table; the gap lists are
**byte-identical between BTCUSDT and ETHUSDT** at every interval (consistent with exchange-wide downtime).

Independent recompute from parquet (duckdb window function over 5m opens, both symbols) reproduces
exactly 7 gaps, 213 missing 5m bars total, identical across symbols. Two largest:

1. last present 2021-04-25 04:00, next present 08:45 → 56 missing 5m bars
2. last present 2021-08-13 01:55, next present 06:30 → 54 missing 5m bars

Source verification (opened raw `{SYM}-5m-2021-04.zip` / `{SYM}-5m-2021-08.zip`, decoded ms epochs):

- 2021-04-25: all 56 expected-missing opens **absent in raw** for both symbols; endpoints 04:00 and 08:45 present.
- 2021-08-13: all 54 expected-missing opens (02:00 … 06:25) **absent in raw** for both symbols; 01:55 and 06:30 present.
- Zero bars found present in raw but missing from parquet → gaps originate at the source, **not** from normalization loss.

## Check 5 — Report/manifest hash integrity: PASS

Recomputed with hashlib:

- `QUALITY_REPORT.json` sha256 = `0f83a1073836708d60138e4aca76c81c20e749136c88571babc550a176fe5cd3` — matches `quality_report_sha256` in frozen manifest.
- `raw_manifest.json` sha256 = `7d2a2336625b9c17f2e83ac98c6ec80ca66f6a70fd93551a2d2e59b60862178a` — matches `raw_manifest.sha256` in frozen manifest.

## Check 6 — Sanity: PASS

- `dropped_duplicate_open_timestamps` = 0 in all 6 tables (and my own distinct-count check found 0 duplicate opens in every parquet).
- BTC and ETH row counts equal per interval (577,803 / 192,602 / 48,154).
- Ratios: 5m/15m = 3.0000, 15m/1h = 3.9997, 5m/1h = 11.9991 — the small shortfall vs 4/12 is fully explained by downtime gaps truncating fewer 5m/15m bars than 1h bars.

---

## Notes (informational, no action required for freeze)

1. **`gap_start_utc` naming**: in `missing_interval_report`, `gap_start_utc` is the timestamp of the **last present bar before the gap**, not the first missing bar (verified: 2021-08-13 5m gap_start 01:55 is present; missing bars are 02:00–06:25). Consumers should not treat `gap_start_utc` itself as missing.
2. **Cross-interval gap edges at source**: around downtimes, Binance's coarser bars resume earlier than finer ones (e.g. 2021-08-13: 1h data resumes at 06:00 while 5m resumes at 06:30), so 1h bars adjacent to gaps may be built from partial intra-hour data at the source. This is a source characteristic, faithfully preserved; backtests spanning gap edges should be aware.

## Confidence

High. Every check was recomputed from the raw bytes / parquet files with independent code; hash sample covered 30/396 raw files (7.6% random + full unit boundary); all comparisons were exact (sha256, integer counts, decimal-string equality). Residual risk is limited to unsampled raw zips (366 files not re-hashed), mitigated by the raw_manifest hash itself matching the frozen manifest.
