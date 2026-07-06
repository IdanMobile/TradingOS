# Phase 4 — Coding-Agent Handoff Readiness Report

Date checked: 2026-07-05
Status: Complete for constrained prototype handoff; not approval to build the full production platform.

## Executive conclusion

The project has reached the point where further progress on several core decisions requires executable evidence rather than more desk research. The next actor should therefore be a coding agent operating under a constrained prototype-and-bake-off mandate, not an open-ended product build mandate.

The coding agent is authorized to install, run, benchmark, compare, and record evidence for shortlisted reusable systems. It is not authorized to select a final production architecture by preference, enable real-money trading, or bypass the evidence gates.

## Readiness criteria and result

| Criterion | Result | Notes |
|---|---|---|
| North Star stable | PASS | Approved and preserved in TRADING_OS_NORTH_STAR.md |
| Reuse-first rule explicit | PASS | Hard rule D-002 |
| First market sequence locked | PASS | Crypto Spot first |
| First vertical slice bounded | PASS | See specs/CRYPTO_SPOT_MVP_VERTICAL_SLICE_V1.md |
| Engine candidates shortlisted | PASS | Freqtrade, NautilusTrader, LEAN, Hummingbot; vectorbt separate |
| Common bake-off tests defined | PASS | ENGINE_BAKEOFF_BLUEPRINT_V1.md |
| Canonical dataset policy defined | PASS | See specs/CANONICAL_BAKEOFF_DATASET_V1.md |
| Fee/slippage assumptions explicit | PASS | See specs/FEE_AND_SLIPPAGE_ASSUMPTION_PACKAGE_V1.md |
| Backtesting validation gates explicit | PASS | See specs/BACKTESTING_VALIDATION_BLUEPRINT_V1.md |
| Experiment lineage prototype bounded | PASS | MLflow/DVC hypothesis, executable gates |
| Strategy-ingestion workflow defined | PASS | Manual 10-item seed before automation |
| AI/agent benchmark framework defined | PASS | Frozen suite V1 |
| Live venue approved | NOT REQUIRED | Live trading is out of scope; account-level eligibility remains a human gate |
| Paid market-data vendor selected | NOT REQUIRED | Tiered policy; MVP bake-off starts with public/native data |
| Final architecture selected | INTENTIONALLY NO | Bake-off evidence must come first |
| Full dashboard implemented | INTENTIONALLY NO | Product build comes after prototype decisions |

## Venue/operator verification findings

### Binance
- Official Binance supported-region list currently marks Israel as available.
- Official public market data is downloadable through Binance Data Collection / binance-public-data.
- Official Spot fee page currently shows regular-user maker/taker rates of 0.100% / 0.100%, with lower rates possible under separate conditions.
- This is enough to use Binance public data as a canonical research dataset candidate and to keep Binance technically shortlisted.
- It is **not** sufficient to approve live trading for the operator. Exact account/product/API availability must be verified in the operator's own account immediately before any live phase.

### Kraken
- Current Kraken materials identify Israel among countries where services are available in at least some contexts.
- Kraken publishes current API, status, and fee information.
- Exact product availability and account-level API permissions remain account-specific and must be verified before live use.

### Coinbase Advanced / OKX
- Technical API capability remains credible.
- Direct, authoritative Israel account/product availability was not sufficiently established for live approval in this pass.
- Remain candidates, not approved venues.

## Important decision: live venue selection is no longer a blocker

For the next coding-agent phase, live trading is forbidden. Therefore the inability to approve a live venue today does not block the engine/data/lineage prototypes.

A separate HUMAN-ONLY LIVE VENUE GATE remains mandatory before any real-money execution:
1. operator account eligibility;
2. exact product availability;
3. API trading permission;
4. automated-trading terms;
5. current fees and limits;
6. deposit/withdrawal path;
7. kill switch and credential isolation.

## Historical-data decision

The first bake-off will use a public, reproducible Tier-0 dataset rather than paid microstructure data.

Primary canonical source candidate:
- Binance public Spot data for BTCUSDT and ETHUSDT.

Why:
- official public source;
- downloadable daily/monthly files;
- supports reproducible local snapshots;
- enough for candle-level infrastructure parity tests;
- avoids premature paid-data commitment.

Paid tick/L2/L3 sources remain deferred until a hypothesis explicitly requires them. Tardis.dev remains a leading crypto microstructure candidate; Databento remains a strong future multi-asset candidate.

## Fee and slippage decision

A single optimistic fee assumption is forbidden. The coding agent must execute a scenario grid:
- F0: zero-fee diagnostic only; never approval evidence;
- F1: 0.10% entry + 0.10% exit baseline for Binance regular-user-style spot assumptions where relevant;
- F2: 1.5x baseline fee stress;
- F3: venue-specific current schedule when a venue is under evaluation.

Slippage scenarios:
- S0: 0 bps diagnostic only;
- S1: 1 bp per side;
- S2: 5 bps per side;
- S3: 10 bps per side;
- S4: adverse stress chosen from observed spread/volatility evidence when available.

A strategy cannot be promoted because it works only in F0/S0.

## Why handoff is now appropriate

The remaining high-value unknowns are executable:
- installation friction;
- deterministic rerun parity;
- cross-engine semantic differences;
- artifact export quality;
- MLflow/DVC operational fit;
- actual resource use on the operator's laptop;
- data conversion friction;
- strategy semantics across frameworks.

More prose research cannot reliably settle these. The correct next step is controlled execution.

## Sources checked

Primary/current sources:
- Binance supported regions: https://www.binance.com/en-GB/support-region-list
- Binance public data: https://data.binance.vision/
- Binance public data repository: https://github.com/binance/binance-public-data
- Binance Spot fees: https://www.binance.com/en/fee
- Kraken regulation/availability: https://support.kraken.com/articles/where-is-kraken-licensed-or-regulated
- Kraken fees: https://www.kraken.com/features/fee-schedule
- Kraken status: https://status.kraken.com/
- Freqtrade lookahead analysis: https://www.freqtrade.io/en/stable/lookahead-analysis/
- Freqtrade backtesting: https://www.freqtrade.io/en/stable/backtesting/
- NautilusTrader: https://nautilustrader.io/
- LEAN: https://www.quantconnect.com/lean/
- Hummingbot Dashboard: https://hummingbot.org/dashboard/
- Hummingbot API: https://hummingbot.org/hummingbot-api/
- Tardis billing/data docs: https://docs.tardis.dev/faq/billing-and-subscriptions
- Databento: https://databento.com/

## Final Phase 4 conclusion

**READY FOR CONSTRAINED CODING-AGENT PROTOTYPE EXECUTION.**

Not ready for:
- full product implementation;
- final production architecture;
- real-money trading;
- autonomous deployment.
