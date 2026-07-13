# Initiative 15 — Paper Trading (S3)

Requirement source: AD §AA, PROGRAM_PLAN S3, North Star G12. Entry criteria: S2 exit
(HG-3) + ≥1 validation-approved strategy context. T-015-01's architecture decision is
complete and locked; paper activation and real paper-observation work remain DEFERRED-S3,
and venue/live work retains its later human gates. Recording implementation machinery does
not authorize a bot to start.

**Supervisory correction (D-046, 2026-07-13):** historical authenticated Bybit demo
activity occurred outside these predicates. It is retained as governance evidence,
not approval or current capability. The standalone demo scripts' network transports
are quarantined until the complete required human-gate, validation, security, and
venue-specific approval chain is recorded. Static synthetic cost stress is not G12
paper divergence evidence.

## T-015-01 Paper-lane architecture decision (local simulator vs venue testnet/demo)
- Inputs: bake-off paper-path evidence; venue demo capabilities (OKX demo confirmed; Binance testnet/demo — REG §6). Acceptance: decision-log entry with evidence.
- Status: **ARCHITECTURE LOCKED; ACTIVATION DEFERRED-S3** — the recommendation
  prepared 2026-07-12 (D-043) is now operator-adopted: local synthetic simulator
  first, venue testnet only after HG-4. Activation remains pending HG-3 and a
  validation-approved strategy context. See `docs/program/S3_READINESS_PACKAGE.md`.

## T-015-02 Paper deployment of first validated strategy
- Acceptance: paper bot runs with environment tagging, synthetic-capital accounting, full logging.
- Status: **DEFERRED-S3** — no strategy is currently validation-approved.

## T-015-03 Backtest-vs-paper divergence tracking (RG-13)
- Acceptance: divergence model (signal frequency, fills, costs, P&L) quantified per G12.
- Status: **DEFERRED-S3** — requires an active paper lane.
- Preparation: **PURE COMPUTATION DONE 2026-07-12** — like-for-like metric maps now
  build typed divergence reports; real paper observations remain gate-dependent.

## T-015-04 Operational drills
- Acceptance: feed-loss/crash/stale-data drills documented; manual kill switch drill (paper).
- Status: **DEFERRED-S3** — requires an active paper lane.
- Preparation: **LIFECYCLE/EVALUATION DONE 2026-07-12** — heartbeat-derived stability,
  immutable operational incidents, and drill evidence validation are implemented;
  producing real operational evidence remains gate-dependent.

## T-015-05 Human-only venue gates package (HG-4 prep)
- The ten items in MISSING_AND_OPEN_ITEMS "Human-only before live trading". Human approval: **Yes, entirely operator-owned**.
- Status: **DEFERRED-S4-HUMAN** — no live venue work is authorized.
