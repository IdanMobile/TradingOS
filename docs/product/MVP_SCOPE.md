# MVP Scope — Trading Intelligence OS

Status: Approved planning baseline v1 (derived strictly from `TRADING_OS_NORTH_STAR.md`, `specs/CRYPTO_SPOT_MVP_VERTICAL_SLICE_V1.md`, and the decision log; no new scope invented)
Date: 2026-07-06
Owner: Operator (single-person)
Supersedes: nothing — this consolidates scope already approved across package files into one canonical statement.

## 1. Exact user

One person: the operator (project owner, Israel-based, trading with personal capital later, technical enough to run local tooling). There are no other users, no multi-tenancy, no external customers in the MVP. Every UX and infrastructure decision must be justified against a single-operator workload.

## 2. Exact problem

The operator cannot currently distinguish a real, durable, executable trading edge from historical coincidence, leakage, unrealistic costs, or overfitting — and cannot afford to rediscover the same research repeatedly. The MVP must produce **trustworthy accept/reject evidence for strategy candidates** and preserve all research as reusable assets.

## 3. Exact market

- Market family: **Crypto Spot only.**
- Venue for data: Binance public Spot data (Tier 0). No live venue is approved.
- Live trading: **out of MVP entirely.** Paper/dry-run is the MVP ceiling.

## 4. Exact supported instruments

- BTCUSDT
- ETHUSDT

No other instruments in MVP. Adding an instrument is a scope change requiring a decision-log entry.

## 5. Exact timeframes

- 5m, 15m, 1h

## 6. Exact workflows (MVP must support end-to-end)

1. **Freeze canonical dataset** — download, normalize, quality-check, hash, register (DS-CRYPTO-SPOT-BAKEOFF-V1).
2. **Ingest an external strategy** — source record → license record → canonical spec → ambiguities → reproduction status (10-item seed batch).
3. **Run a backtest experiment** — strategy version × dataset × engine × parameters × fee/slippage scenario, with full provenance and all trials retained.
4. **Validate a strategy** — execute gates G1–G12 of `specs/BACKTESTING_VALIDATION_BLUEPRINT_V1.md` (V1 subset: G1–G9 + G11 mandatory; G10 method-candidate; G12 paper-forward when paper lane exists).
5. **Record an evidence decision** — accept/reject/defer per strategy × instrument × timeframe with linked artifacts.
6. **Run an AI benchmark task** — frozen fixture → agent configuration → scored result with cost/latency/provenance (execution optional if no credentials; harness mandatory).
7. **Inspect evidence** — read-only dashboard listing datasets, runs, strategies, engine comparisons, validation status, evidence links.
8. **Write a learning** — evidence-linked memory record with supporting/contradicting experiment IDs.

## 7. Exact dashboard pages (MVP)

Read-only evidence surface only (SSOT WS9). Six views:

1. Datasets (ID, hashes, coverage, quality status)
2. Runs/Experiments (provenance, params, metrics, artifacts)
3. Strategies (canonical specs, versions, reproduction status)
4. Engine comparison (bake-off matrix + parity findings)
5. Validation status (gates passed/failed per strategy-context)
6. Evidence links (decision records → artifacts)

The 27-page product IA in the North Star §9 is the long-term target, **not** MVP. Building any write-path UI, approvals UI, live-trading UI, or AI command center UI in MVP is out of scope.

## 8. Exact out-of-scope (MVP)

- real-money/live trading; live exchange credentials; withdrawal-enabled keys
- crypto perpetual futures, leverage, funding; US stocks/ETFs
- paid data (Tardis/Databento/CoinAPI/Kaiko purchases)
- mass strategy scraping; automated ingestion beyond the 10-item manual batch
- autonomous AI in any trade path (AI involvement classes E/F)
- portfolio optimizer; full risk engine (risk gates exist as validation rules only)
- full ontology ingestion (dictionary seeding limited to concepts actually touched by MVP artifacts)
- production deployment, cloud infrastructure, multi-user auth
- final architecture lock prior to prototype evidence

## 9. Exact success criteria

MVP passes when all `specs/CRYPTO_SPOT_MVP_VERTICAL_SLICE_V1.md` exit criteria hold, i.e.:

1. Frozen dataset regenerates to identical hashes on two independent runs.
2. ≥2 first-tier engines complete all four baselines on the canonical dataset; all 4 candidates have executable evidence or reproducible blocker records.
3. Cross-engine semantic differences are diagnosed (not just numeric deltas).
4. Lineage prototype returns one of the four allowed decisions with artifacts.
5. 10-item seed batch complete with per-item required outputs.
6. Validation blueprint exercised on ≥1 baseline with the mandatory fee/slippage grid.
7. Evidence visible in the read-only surface.
8. `decisions/PROTOTYPE_EVIDENCE_DECISION.md` exists with per-capability reuse decisions and evidence links.
9. Zero real-money capability exists anywhere in the codebase.

## 10. Exact failure criteria

The MVP has failed (triggering re-planning, not silent continuation) if any of:

- the canonical dataset cannot be made reproducible from official public sources;
- no engine can produce deterministic, artifact-exportable baseline runs;
- lineage prototype concludes `ALTERNATIVE_REQUIRED` with no viable alternative identified;
- validation gates cannot distinguish the deliberately-weak baselines from noise (e.g., a zero-cost-only-profitable baseline passes);
- evidence artifacts cannot be traced end-to-end (dataset→run→validation→decision).

## 11. Market sequence (unchanged)

Crypto Spot → Crypto Perpetual Futures → US Stocks/ETFs. Re-validated 2026-07-06 against the package; no evidence emerged to change it. See `docs/architecture/AD.md` §AK for the expansion path.

## 12. Traceability

Every requirement here maps to rows in `docs/traceability/TRACEABILITY_MATRIX.md` (REQ-001…) and to tasks in `TODO.md`.
