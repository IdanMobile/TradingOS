# Trading Intelligence OS — Missing and Open Items

Last updated: 2026-07-06

## Open research gaps (tracked in detail in `research/RESEARCH_GAP_MATRIX.md`)

- RG-02 LEAN local data/pricing boundary (verify before WS3 LEAN lane).
- RG-03 vectorbt OSS exact license text (blocks vectorbt probe lane only).
- RG-05 Kraken/Coinbase Israel availability (before S3; Coinbase demoted provisionally).
- RG-08 OpenAI/Gemini primary-source pricing + context windows (before paid benchmark runs).
- Remaining RG-xx rows: see the matrix; none block S1 start.

## Resolved 2026-07-06 (planning pass)

- Duplicate decision IDs D-022/D-023 → renumbered D-027/D-028 (D-031).
- Binance timestamp-unit change → dataset spec Amendment A1 (D-029).
- Stale candidate assumptions corrected (vectorbt OSS active; Backtrader/backtesting.py rejected; Databento reclassified) (D-032).

## Blocking current coding-agent prototype

None identified. The project passed the constrained coding-agent readiness gate.

## Must be resolved by prototype evidence

1. Role fit of Freqtrade, NautilusTrader, LEAN, and Hummingbot under common tests.
2. Whether vectorbt should be reused as a research accelerator and under which overfitting controls.
3. Cross-engine signal/order semantic differences.
4. Actual installation and maintenance friction on the development machine.
5. MLflow + DVC vs simpler lineage combination.
6. Canonical data conversion and regeneration reliability.
7. Practical validation-harness design and artifact schema.
8. Real schema/license/semantic lessons from 10-item strategy seed ingestion.
9. Minimal dashboard data contract.
10. Initial AI/agent benchmark harness practicality.

## Human-only before live trading

1. Exact Israel/operator account eligibility for selected venue.
2. Exact product availability in operator account.
3. API trading permissions.
4. Current automated-trading terms.
5. Current fee tier.
6. Funding/deposit/withdrawal path.
7. Credential isolation and revocation process.
8. Capital amount and maximum acceptable drawdown.
9. Tax/accounting workflow.
10. Final human approval.

## Deferred until justified

- paid tick/order-book data purchase;
- perpetual futures;
- leverage;
- US stocks/ETFs;
- on-chain data;
- social sentiment;
- news vendor selection;
- portfolio optimizer;
- full risk engine;
- mass strategy scraping;
- production deployment;
- autonomous AI trade path;
- full ontology ingestion;
- final 27-page dashboard implementation.

## Re-verification required

Before implementation/live use recheck:
- exchange APIs and changelogs;
- provider model versions/pricing;
- data provider pricing/licensing;
- engine versions/deprecations;
- venue fees;
- account eligibility.
