# Initiative 04 — Data Foundation (S1, WS2) — CRITICAL PATH

Requirement source: `specs/CANONICAL_BAKEOFF_DATASET_V1.md` + amendment D-029 (µs timestamps). Skill: R7 + SKILL_DATA_QUALITY_AUDITOR.

## T-004-01 Raw snapshot downloader
- Purpose: reproducible raw capture from data.binance.vision. Requirement: REQ-006.
- Actions: downloader for BTCUSDT/ETHUSDT 5m/15m/1h monthly+daily files over target window (prefer 2021-01-01→2026-06-30); record URLs, timestamps, SHA-256; never overwrite; manifest.
- Outputs: `data/raw/binance_spot/**` + raw manifest. Acceptance: re-run downloads nothing new when complete; manifest hashes verify. Failure: source unreachable after documented retries → stop per SSOT WS2. Complexity: M. Status: **DONE 2026-07-06** (396 files, all official-checksum-verified; re-run downloads 0).

## T-004-02 Normalization to canonical schema
- Purpose: canonical bars per spec schema. Requirement: REQ-007.
- Actions: implement converter C5 including **ms→µs unit boundary at 2025-01-01** (CG-03) with explicit unit detection + boundary tests; UTC normalization; no forward-fill; dedup only as explicit step.
- Outputs: `data/normalized/**` Parquet + normalized hash. Acceptance: schema identical across instruments; boundary-window golden test passes. Complexity: M. Dependencies: T-004-01. Status: **DONE 2026-07-06** (1.64M rows; boundary goldens on real 2024-12/2025-01 rows).

## T-004-03 Quality gate implementation
- Purpose: executable spec quality checks. Requirement: REQ-008.
- Actions: monotonicity, duplicates, spacing, OHLC invariants, volume ≥0, missing-interval report, checksum verification, row counts.
- Outputs: quality report (json+md). Acceptance: all checks run; deliberately-corrupted fixture fails each check. Complexity: M. Dependencies: T-004-02. Status: **DONE 2026-07-06** (overall PASS; every check proven failable).

## T-004-04 Freeze + double-regeneration proof
- Purpose: DS-CRYPTO-SPOT-BAKEOFF-V1 identity. Requirement: REQ-009 (EG-1).
- Actions: freeze manifest (source files, hashes, code commit, coverage, quality hash); regenerate from scratch twice; compare normalized hashes.
- Outputs: dataset manifest; regeneration evidence. Acceptance: identical hashes twice; dataset registered. Failure: nondeterminism → diagnose before proceeding (blocks EG-1). Complexity: S. Dependencies: T-004-03. Status: **DONE 2026-07-06** (identical content hashes across 2 fresh regenerations; frozen manifest at artifacts/datasets/).

## T-004-05 Independent data-quality audit
- Purpose: auditor pass distinct from producer. Requirement: REQ-010.
- Actions: run SKILL_DATA_QUALITY_AUDITOR checklist (recompute, downtime cross-check, boundary check).
- Outputs: audit report attached to manifest. Acceptance: PASS or PASS_WITH_NOTES. Complexity: S. Dependencies: T-004-04. Status: **DONE 2026-07-06** (independent audit PASS_WITH_NOTES, zero discrepancies; artifacts/datasets/DATA_QUALITY_AUDIT_01.md).
