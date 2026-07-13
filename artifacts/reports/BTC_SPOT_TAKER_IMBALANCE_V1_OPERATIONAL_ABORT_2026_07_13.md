# BTC Spot taker-imbalance V1 operational abort

Date: 2026-07-13 UTC
Campaign: `BTC-SPOT-TAKER-IMBALANCE-G1-G11-V1`
Run commit: `79b5fa3`
Disposition: **ABORTED PRE-SELECTION — no strategy verdict**
Execution authority: `NONE`

## Verified sequence

- V1 started from a clean commit and passed its offline preflight.
- The runner entered phase-one Decimal development computation.
- The independent reference rescanned up to 720 prior rows for each bar and regenerated identical
  event flags for every cost cell. It remained CPU-bound but produced no temporary artifact after
  sustained execution.
- The operator process was interrupted during `taker_events`, before phase-one completion.
- No selection artifact, worker result, validation, reserve, full-history, period, or final
  campaign output was created. The runner's `finally` cleanup removed its temporary directory.

## Authorized repair boundary

V2 may replace repeated baseline scans with mathematically equivalent prefix sums/squared sums and
cache cost-independent event flags per trial/segment. It may not change data, feature, direction,
baseline, threshold, pulse, timing, gap, cost, split, selection, metric, gate, or safety semantics.
Canonical-versus-reference micro-goldens must still pass, and V2 requires a new clean freeze before
running.

## Safety

No bot, venue, credentials, order, paper/demo/live state, sealed V2 holdout, campaign validation or
reserve segment, promotion, human gate, or execution authority was accessed or activated.
