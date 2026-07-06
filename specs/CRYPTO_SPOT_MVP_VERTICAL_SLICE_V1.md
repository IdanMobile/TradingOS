# Crypto Spot MVP Vertical Slice V1

Status: Approved scope for constrained coding-agent prototype execution.

## Goal

Prove the end-to-end research/evidence workflow on Crypto Spot without building the full Trading Intelligence OS.

## Instruments

- BTCUSDT
- ETHUSDT

## Timeframes

- 5m
- 15m
- 1h

## Strategy baselines

Infrastructure baselines only:
1. Buy and hold
2. Moving-average crossover
3. Bollinger mean reversion
4. Volatility breakout

These are not assumed profitable.

## Prototype lanes

### Lane A — Canonical data
- Download/freeze Binance public Spot dataset.
- Normalize and quality-check.
- Hash artifacts.

### Lane B — Engine bake-off
Execute role-based comparison:
- Freqtrade
- NautilusTrader
- LEAN
- Hummingbot

Separate research-accelerator probe:
- vectorbt

The coding agent may document a candidate as `NOT_PRACTICAL_TO_RUN` only with reproducible evidence of blocker and after attempting the official supported installation path.

### Lane C — Experiment lineage
Prototype:
- MLflow
- DVC
- thin custom Trading Evidence link

### Lane D — Strategy ingestion seed
Manually ingest 10 items:
- 2 QuantConnect/library items
- 2 Freqtrade strategies
- 2 Hummingbot controllers
- 2 open-source Pine strategies
- 2 academic-paper strategies

Purpose: learn schema, semantics, licensing, ambiguity—not find winners.

### Lane E — AI/Agent benchmark seed
Materialize a small frozen corpus from the V1 benchmark suite and run at least two available model/agent configurations if credentials are available.

If model credentials are not available, build the harness and fixture corpus, mark execution blocked, and do not invent results.

## Minimal dashboard/control surface

Do not build the final 27-page product.

Build only a read-only prototype capable of showing:
- datasets;
- runs;
- strategies;
- engine comparisons;
- validation status;
- evidence links.

A simple web UI is acceptable. The UI exists to prove artifact discoverability, not product design.

## Explicit non-goals

- real-money trading;
- live API keys;
- perpetual futures;
- stocks/ETFs;
- autonomous AI trading;
- final portfolio allocator;
- final risk engine;
- full ontology ingestion;
- mass strategy scraping;
- production deployment;
- final architecture lock before evidence.

## Exit criteria

PASS when:
1. frozen dataset is reproducible;
2. at least two serious engines complete common baselines;
3. all four first-tier candidates have executable evidence or documented blockers;
4. cross-engine semantic differences are recorded;
5. MLflow/DVC lineage prototype reaches a decision;
6. 10-item strategy seed batch is completed;
7. validation blueprint is exercised on at least one baseline strategy;
8. evidence is visible in the minimal control surface;
9. decision report recommends role-based reuse choices with confidence and rejection reasons;
10. no real-money capability is enabled.

## Final decision output

Create:
`decisions/PROTOTYPE_EVIDENCE_DECISION.md`

It must state for each major capability:
- Reuse Existing
- Reuse + Adapter
- Hybrid
- Build Custom
- Defer
- Rejected

with links to artifacts.
