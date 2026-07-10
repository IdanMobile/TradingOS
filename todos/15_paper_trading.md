# Initiative 15 — Paper Trading (S3)

Requirement source: AD §AA, PROGRAM_PLAN S3, North Star G12. Entry criteria: S2 exit (HG-3) + ≥1 validated strategy. All tasks DEFERRED-S3; recorded to keep the path explicit, not to authorize work.

## T-015-01 Paper-lane architecture decision (engine dry-run vs venue testnet/demo)
- Inputs: bake-off paper-path evidence; venue demo capabilities (OKX demo confirmed; Binance testnet/demo — REG §6). Acceptance: decision-log entry with evidence.
- Status: **DEFERRED-S3** — requires S2 exit, HG-3, and a validated strategy.

## T-015-02 Paper deployment of first validated strategy
- Acceptance: paper bot runs with environment tagging, synthetic-capital accounting, full logging.
- Status: **DEFERRED-S3** — no strategy is currently validation-approved.

## T-015-03 Backtest-vs-paper divergence tracking (RG-13)
- Acceptance: divergence model (signal frequency, fills, costs, P&L) quantified per G12.
- Status: **DEFERRED-S3** — requires an active paper lane.

## T-015-04 Operational drills
- Acceptance: feed-loss/crash/stale-data drills documented; manual kill switch drill (paper).
- Status: **DEFERRED-S3** — requires an active paper lane.

## T-015-05 Human-only venue gates package (HG-4 prep)
- The ten items in MISSING_AND_OPEN_ITEMS "Human-only before live trading". Human approval: **Yes, entirely operator-owned**.
- Status: **DEFERRED-S4-HUMAN** — no live venue work is authorized.
