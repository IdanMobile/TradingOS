# Initiative 20 — Future Market Expansion (S3+, design-only)

Requirement source: AD §AK, North Star §5. NO implementation authorized; these are design/verification tasks gated on earlier stages.

## T-020-01 Perps readiness design review
- Verify AD §AK additive claims against selected engines' perp support at that time; funding-aware cost gate design; liquidation-aware stress design. Entry: S3.
- Status: **DONE FOR AUTHORIZED DESIGN-ONLY SLICE 2026-07-11 / IMPLEMENTATION DEFERRED-S3** — perps design gates and invariants retained in `artifacts/reports/FUTURE_MARKET_EXPANSION_DESIGN_REVIEW_2026_07_11.md`. No implementation, credentials, paper/demo/testnet, order routing, live trading, or real-money path is authorized.

## T-020-02 US equities/ETFs data+broker landscape refresh
- Re-run capability research (Databento reclassified per AD-14 as the multi-asset candidate; broker APIs; corporate-actions handling). Entry: Phase-3 planning.
- Status: **DONE FOR AUTHORIZED DESIGN-ONLY SLICE 2026-07-11 / IMPLEMENTATION DEFERRED-S3** — equities/ETFs landscape and future gates retained in `artifacts/reports/FUTURE_MARKET_EXPANSION_DESIGN_REVIEW_2026_07_11.md`. No paid data access, broker connection, credentials, or implementation is authorized.

## T-020-03 Core-spine invariance audit
- At each expansion: verify spec→experiment→validation→evidence→approval contracts survive unchanged; any breach → Architecture Guardian + decision log. Recurring.
- Status: **DONE FOR AUTHORIZED DESIGN-ONLY SLICE 2026-07-11 / RECURRING AT EXPANSION BOUNDARIES** — core-spine invariants for perps/equities are retained in `artifacts/reports/FUTURE_MARKET_EXPANSION_DESIGN_REVIEW_2026_07_11.md`. Future expansion still requires stage authorization and decision-log review.
