# Trading Intelligence OS — Research Backlog

Last updated: 2026-07-06
Status: Strategic research sufficient for constrained prototype handoff. Remaining research is execution-triggered.
Note: detailed gap tracking moved to `research/RESEARCH_GAP_MATRIX.md` (RG-xx rows with owners/triggers); a freshness re-verification pass was completed 2026-07-06 into `research/EXISTING_CAPABILITY_REGISTRY.md`. This backlog keeps the priority-band view only.

## P0 — Execute now through coding agent

1. Engine bake-off: Freqtrade, NautilusTrader, LEAN, Hummingbot.
2. vectorbt accelerator probe.
3. Canonical Binance public Spot dataset snapshot and quality report.
4. MLflow/DVC lineage prototype.
5. Backtesting validation harness exercise.
6. 10-item strategy ingestion seed batch.
7. Minimal AI/agent benchmark fixtures and harness.
8. Minimal read-only evidence dashboard.
9. Evidence-backed prototype decision report.

## P1 — Triggered by prototype findings

- exact adapters needed between selected engines and OS evidence layer;
- alternative lineage tool if MLflow/DVC fail gates;
- dashboard framework choice based on prototype data contracts;
- advanced DSR/PBO implementation validation;
- expanded Tool & Engine Registry;
- expanded Existing Strategy Registry;
- dictionary/ontology seed tooling;
- job orchestration choice;
- observability stack.

## P2 — Before paper/live phase

- direct operator account/venue verification;
- exchange-specific fee/order semantics;
- credential isolation;
- paper-vs-backtest divergence model;
- operational kill switches;
- live adapter contract tests;
- status/changelog monitoring.

## P3 — Only when a hypothesis requires it

- Tardis/other crypto tick and order-book data;
- normalized multi-venue data vendor;
- news intelligence;
- sentiment;
- on-chain data;
- alternative data.

## P4 — Future market expansion

- Crypto Perpetual Futures
- US Stocks/ETFs
- Databento and other multi-asset data
- brokerage APIs
- corporate actions
- options/futures
