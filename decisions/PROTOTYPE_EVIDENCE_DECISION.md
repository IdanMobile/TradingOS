# Prototype Evidence Decision

Status: **HG-2 APPROVED — CONSTRAINED S2 ENTRY AUTHORIZED (D-036)**
Date: 2026-07-10
Scope: S1 Crypto Spot evidence prototype only; no real-money authorization.

This artifact records the evidence-backed reuse direction accepted for constrained S2
architecture and autonomous research-lab work. Approval does not approve any strategy
or authorize paper, demo/testnet, or live trading.

## Capability decisions

| Capability | Decision state | Evidence-backed direction | Confidence / boundary |
|---|---|---|---|
| Canonical market data | Reuse + Adapter | Binance public Spot archives normalized to decimal Parquet and queried with DuckDB | High for BTCUSDT/ETHUSDT candle research; no tick/L2 claim |
| Primary Crypto Spot research engine | Reuse + Adapter | Freqtrade through the isolated CLI/subprocess lane | Medium-high; full B1–B4 matrix exists, but G4 warning and slippage limitations remain |
| Event-driven simulation | Reuse + Adapter | NautilusTrader as specialized simulator | Medium; B1–B4 bounded matrix is deterministic and fee-audited; full-history and latency/fill probes remain |
| Bot operations / market making | Defer | Retain Hummingbot candidate and compatibility workaround | Medium-low; B1 and B2 evidence exists, B3/B4 and determinism reruns are absent |
| Multi-asset portability | Defer | Retain LEAN candidate | Low executable confidence; local mechanism is prepared but Docker is not running and no backtest completed |
| Research acceleration | Reuse + Adapter | vectorbt behind all-trial retention and binding overfit controls | High for accelerator role; B2/B3/B4 66/66 trials retained and ledgered; never execution/approval authority |
| Generic experiment/data lineage | Reuse + Adapter | MLflow for runs/artifacts/comparison plus DVC for dataset snapshots/restoration | High for local S1; all seven gates evaluated, AI proof is mock-only; S2 must define retention/backup/access policy |
| Trading Evidence Registry | Build Custom | Keep the tiny stable-reference domain registry above generic lineage tools | High for prototype; public MLflow/DVC references link without internal-schema coupling |
| Validation harness | Hybrid | Reuse engine diagnostics and statistical methods behind custom contextual gates | Medium; B2 is correctly rejected, G4 WARN and G10 method deferral prevent production-validation claims |
| Contextual approval governance | Build Custom | Small deterministic state model keyed by strategy×market×instrument×timeframe×config×environment | High for S1 model; evidence required, paper requires human decision, live states unreachable |
| Independent risk preconditions | Build Custom | Validation-owned no-live, cost-grid, drawdown/tail, and promotion-eligibility checks | High for S1; B2 passes risk evidence completeness but remains promotion-ineligible |
| Strategy ingestion | Hybrid | Reuse source implementations and licenses; keep canonical specs/ambiguity decisions custom | Medium-high for directional strategies; market-making and cross-sectional schemas need variants |
| AI evaluation | Hybrid | Null/mock provider only in constrained S2; any real provider remains outside current credential authority | Medium for harness plumbing, no real-model quality evidence yet |
| Evidence dashboard / charting | Hybrid | Custom read model + TradingView Widget + OS-owned evidence chart | Medium-high for local S1 inspection; no command/write path |
| Automatic research jobs and triggers | Build Custom | Start with bounded, deterministic, allowlisted research commands; add persisted scheduling only after idempotency is proven | Research/validation only; no execution authority or venue commands |
| Real-time ticks / order book | Defer | Select and license a public/demo feed at the paper-lane architecture gate | Frozen candles and TradingView display are not tick-stream evidence |
| Demo wallet / paper portfolio | Defer | Build only after S2 exit, independent risk checks, and one validated strategy-context | No synthetic capital or order-routing state exists yet |
| Live trading | Rejected | Rejected for the current phase | No live credentials, write endpoint, capital route, or strategy approval exists |

## Engine evidence interpretation

- Freqtrade is the strongest current Crypto Spot research/backtest candidate, not a
  universal execution engine and not a strategy approver.
- NautilusTrader now provides a complete two-week B1–B4 bounded matrix across
  F0/S0 and F1/S1. All run1/run2 trade, equity, and metric artifacts are byte-identical.
- Full-period Freqtrade/Hummingbot B1 fill counts match but boundary timestamps
  differ by their documented next-open versus same-close execution semantics.
- A BTC-only Freqtrade B2 run removes cross-pair contention. The 66,385 versus
  66,462 residual is explained—not erased—by differing timing/order state plus
  missing-bar handling; this context is prohibited as fill/P&L parity evidence.
- LEAN and missing Hummingbot lanes are retained as explicit environment/coverage gaps.

Evidence: `artifacts/reports/ENGINE_BAKEOFF_REPORT.md` and
`artifacts/bakeoff/parity/engine_parity.json`.

## Strategy decision

B2 moving-average crossover is **REJECTED as a paper candidate** in its tested
context. It is retained as infrastructure and negative-learning evidence because:

- every cost-grid cell is negative;
- development, validation, holdout, five parameter neighbors, and 18 walk-forward
  windows are negative;
- it underperforms cash and buy-and-hold;
- the red-team verdict is no approval.

No B1–B4 baseline is approved for real money.

## HG-2 decision checklist

1. DONE — B2 residual retained with precise execution/order-state and data-gap evidence.
2. DONE — Freqtrade lane closed with exact PASS/WARN/capability-gap outcomes.
3. DONE — LEAN and Hummingbot missing coverage remains exact under the documented-blocker rule.
4. DONE — lineage A/B/C and vectorbt B2/B3/B4 + 66-trial ledger evidence complete.
5. DONE — repository gate passes: ruff, format, mypy strict, 123 tests.
6. DONE — operator explicitly approved HG-2 for constrained S2 entry on 2026-07-10 (D-036).

## Explicit non-authorizations

D-036 authorizes only constrained S2 architecture, sourced research, offline backtesting,
scoring, validation, research-console work, and eventual demo preparation. It does not
approve a strategy; B2 remains `INCOMPLETE_NOT_APPROVABLE` and rejected for paper. No
synthetic wallet, paper/demo/testnet venue connection, credential, order-routing path,
live trade, or real-money capability is authorized. AI cannot approve or trade.
