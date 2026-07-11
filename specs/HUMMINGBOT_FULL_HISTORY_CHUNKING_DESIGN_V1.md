# Hummingbot Full-History Chunking/Throughput Design V1

Date: 2026-07-11. Status: DESIGN COMPLETE — execution is a throughput track, not a
credential or approval blocker (D-037). Closes the "chunking/throughput design"
item of T-006-05; the rerun decision framing is §5.

## 1. Problem evidence

Full-history (2021-01-01→2026-06-30, 577,803 bars) Hummingbot B2 F1/S1 hit the
1800 s lane timeout before writing `raw.json`, and a feature-cached retry still hit
3600 s (`artifacts/reports/HUMMINGBOT_FULL_HISTORY_TIMEOUT_2026_07_11.md`). The
bounded 30-day matrix (B1–B4 × {F0/S0,F1/S1} × {run1,run2}) is complete, normalized,
fee-audited, and byte-deterministic
(`artifacts/reports/HUMMINGBOT_PRODUCTIONIZATION_STEP_2026_07_11.md`). Measured
bounded throughput: ~32 s per cached 30-day B2 probe → full history ≈ 67 windows
× 32 s ≈ 36 min of pure compute, but the monolithic run exceeds any single-window
timeout because the container's per-run overhead and memory growth are superlinear
in window length.

## 2. Design: bounded contiguous windows with stitched normalization

1. **Window unit**: 30 calendar days (the proven bounded unit), contiguous,
   non-overlapping except a **warm-up prefix** of `max(indicatorـwindow) + 1` bars
   (B2: 5 bars; B3: 20; B4: 20) prepended to each window and discarded from
   normalized output (prevents cold-start signal divergence at window seams).
2. **Per-window execution**: reuse the existing bounded lane exactly — named
   container, explicit `--window-start/--window-end`, per-window timeout 1800 s,
   timeout manifest + container stop on breach (already implemented). Feature cache
   stays enabled (proven ~32 s/window).
3. **Stitching (converter C3 extension)**: per-window normalized trades/equity are
   concatenated in window order after dropping warm-up rows. Open position at a
   window boundary is carried by replaying the boundary state: the stitcher rejects
   the run (hard error, no silent approximation) if the position state at a seam
   differs from the next window's warm-up-derived state — a recorded CapabilityGap
   per AD §L C2 rules.
4. **Identity/provenance**: the stitched result's manifest lists every window
   (start/end, container digest, per-window raw/normalized hashes, warm-up bars
   dropped) plus a stitched-content hash; rerunning any window reproduces its hash
   (bounded determinism is already evidenced).
5. **Determinism check**: full-history determinism = two stitched passes (run1/run2)
   byte-identical, mirroring the bounded matrix's existing rule.

## 3. Acceptance criteria (execution task, when scheduled)

- B2/B3/B4 F1/S1 full-history stitched runs complete with zero timeout manifests;
- seam audit: zero unexplained position-state discontinuities;
- fee recomputation audit passes on the stitched trades;
- run1/run2 stitched hashes identical;
- cross-check: stitched B2 30-day sub-range byte-equals the retained bounded run.

## 4. Failure modes

- Seam state mismatch → hard error + CapabilityGap record (no silent stitch).
- Any window timeout → that window's timeout manifest + named-container stop
  (existing behavior); the stitched run is FAILED, partial windows retained.
- Cache invalidation mid-sequence → rerun affected window only (content-addressed).

## 5. Rerun decision framing (operator)

Run the chunked full-history matrix only when one of these holds: (a) a candidate
with positive bounded evidence needs Hummingbot-lane confirmation; (b) the
bot-operations capability lane is being promoted into an active S3 role; (c) a
cross-engine parity question requires full-range Hummingbot data. Until then the
bounded lane remains the retained capability/regression evidence and the ~40 min
compute (plus stitcher implementation, est. S complexity) stays unspent — the
current candidate population is negative, so (a) is not met today.

## 6. Traceability

T-006-05 (throughput track) · REQ-018 · AD §K Hummingbot role ·
`artifacts/bakeoff/hummingbot/BLOCKER_REPORT.md` · parity WS4 rules AD §L.
