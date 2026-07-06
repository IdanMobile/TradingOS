# Phase 2 Targeted Discovery Report

Date: 2026-07-05
Status: Targeted discovery complete for this tranche; several decisions remain gated.

## Scope
1. Engine bake-off design.
2. Crypto Spot exchange/operator-fit shortlist.
3. Existing strategy sources.
4. Experiment-lineage direction.
5. AI/agent evaluation direction.

## Finding 1 — Engine selection should be role-based
### Freqtrade
Strong Crypto Spot MVP candidate because current official documentation includes backtesting, dry-run/live workflows, hyperoptimization, lookahead analysis, recursive analysis, and FreqAI workflows.

Planning implication: promote Freqtrade into first bake-off tier rather than treating it only as a strategy-source repository.

### NautilusTrader
Strong execution-grade candidate. Current official material emphasizes deterministic event-driven simulation, shared research/live semantics, configurable fill/fee/latency/order-book models, and modular adapters.

Planning implication: test it for execution realism and long-term production core suitability.

### LEAN
Strong broad multi-asset candidate and architecture prior art. Retain because future Stocks/ETFs expansion is approved.

Planning implication: evaluate local ownership, data dependencies, and artifact integration rather than assuming QuantConnect cloud use.

### Hummingbot
Current official Dashboard/API/controller ecosystem is particularly strong for reusable crypto-native bot operations, backtesting controllers, market making, and fleet management.

Planning implication: test it as specialized crypto operations infrastructure, not necessarily universal research core.

## Finding 2 — Existing strategy supply is much larger than our initial registry implied
Validated discovery sources include:
- QuantConnect Strategy Library: academic-literature strategy tutorials.
- QuantConnect community Strategies: community algorithms with ongoing platform backtests.
- Official Freqtrade strategy repository.
- Hummingbot V2 Controllers and strategy repositories.
- TradingView Community Scripts: over 150,000 community scripts according to current official Pine documentation, with roughly half open-source.

Planning implication: create an ingestion/reproduction pipeline for public strategies instead of manually collecting ad hoc links.

## Finding 3 — Strategy provenance must distinguish source class
Proposed source classes:
1. Primary academic paper.
2. Official framework tutorial/reference strategy.
3. Maintained open-source implementation.
4. Community strategy with transparent source.
5. Social/forum claim.
6. Proprietary/opaque claim.

A source class affects evidence confidence, but never transfers profitability into our internal score.

## Finding 4 — Exchange selection remains unresolved
A reliable Israel-specific availability matrix could not be completed from authoritative public evidence in this tranche.

What is currently supported:
- Kraken publishes current regulation/region and funding support material.
- Coinbase publishes prohibited-region material, but the search evidence did not directly establish a complete Israel product matrix.
- Binance availability and product restrictions are jurisdiction-sensitive and must be verified directly at account/product level before execution.

Decision: do not approve Binance, Kraken, Coinbase, OKX, Bybit, or any other venue as live MVP exchange yet.

Recommended next method:
- Build a formal venue matrix.
- Verify account eligibility from Israel.
- Verify spot API access.
- Verify paper/testnet capability.
- Verify exact pairs.
- Verify fees.
- Verify API rate limits.
- Verify order types.
- Verify withdrawal/deposit operations.
- Verify terms for automated trading.
- Verify legal/tax/accounting implications separately.

## Finding 5 — Experiment lineage should likely be layered
Current direction:
- MLflow-class tooling for run/metric/artifact/model/LLM-agent tracing.
- DVC-class tooling for Git-friendly dataset/artifact reproducibility.
- Custom Trading Evidence Registry above them for strategy-market-timeframe approval, provenance, contradiction, and promotion state.

Decision status: blueprint recommended; exact product combination not yet approved.

## Finding 6 — AI/agent evaluation should include controlled and natural benchmarks
Controlled benchmark:
- same task
- same source corpus
- same tools
- same budget/timeout
- repeated runs

Natural best-configuration benchmark:
- model-specific prompts
- model-specific tool policies
- optimized agent workflows

Both are necessary because the first isolates model effects while the second measures real operational value.

## Finding 7 — External 2026 benchmark prior art is useful, not sufficient
QuantCode-Bench directly supports executable strategy-generation evaluation and reports failures in operationalizing financial logic/API semantics, not merely syntax.

Planning implication: our Agent Benchmark Lab should include execution, trade occurrence, semantic alignment, and downstream validation—not textual quality alone.

## Current recommendation maturity
| Item | State |
|---|---|
| Freqtrade first-tier Crypto Spot bake-off | Recommended |
| NautilusTrader first-tier execution-grade bake-off | Recommended |
| LEAN retained in bake-off | Recommended |
| Hummingbot specialized operations/controller bake-off | Recommended |
| One universal engine | Rejected |
| TradingView Community Scripts as hypothesis source | Validated source candidate |
| QuantConnect strategy sources | Validated source candidate |
| Public strategy profitability claims | Rejected as evidence |
| Live exchange | Unresolved |
| MLflow + DVC layered pattern | Strong design candidate |
| Custom approval/evidence layer | Recommended; detailed schema pending |
