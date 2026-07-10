# Ambiguities — SRC-QC1 (dual MA crossover)

1. **Window pair not canonical.** LEAN's example algorithms use varying fast/slow window pairs across demos; there is no single "the" QuantConnect dual-MA strategy. Recorded as a configurable input rather than resolved by guessing a default.
2. **Equality tie-break.** Source pseudocode does not state behavior when `sma_fast == sma_slow`. This ingestion assumes no-signal (neither entry nor exit fires) — an explicit assumption, not a silent default.
3. **Same-bar vs next-bar execution.** Framework examples typically place orders in `OnData` during the same bar the signal is observed; whether the fill is same-bar-close or next-bar-open is a LEAN engine/broker-model detail external to the algorithm's own logic. Assumed next-bar-open here for consistency with this project's other baselines.
4. **Exact source file/commit unverified.** No live fetch was performed in this pass (see source_record.yaml note); the file identity should be reviewer-confirmed before any code (not just spec) reuse.
