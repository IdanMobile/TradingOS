# Initiative 06 — Engine Bake-off (S1, WS3+WS4) — CRITICAL PATH

Requirement source: `specs/ENGINE_BAKEOFF_BLUEPRINT_V1.md`. Skills: R7 + SKILL_ENGINE_PARITY_AUDITOR. Engine lanes are parallelizable (disjoint artifact dirs). No winner is assumed; role-fit scoring only (D-012).

## T-006-01 EngineAdapter port + NormalizedResult
- Purpose: the parity boundary (type catalog §4, converter C3). Requirement: REQ-014.
- Actions: implement port, NormalizedResult model, capability-report model; golden tests on synthetic engine output.
- Acceptance: normalization goldens; fee recomputation check utility works. Complexity: M. Dependencies: T-005-01, T-004-04. Status: **DONE 2026-07-06** (core_types/engine.py port + parity/fees.py; mandatory grid encoded; goldens green).

## T-006-02 Freqtrade lane
- Purpose: full test matrix + Freqtrade-specific probes (lookahead-analysis, recursive-analysis, bounded hyperopt with all-trial retention, dry-run capability check, artifact export). Requirement: REQ-015.
- Integration rule: subprocess/CLI only (GPL boundary, AD-02).
- Outputs: `artifacts/bakeoff/freqtrade/**` (manifest, trades, equity, metrics, logs, env manifest, divergence notes) + matrix scores.
- Acceptance: all 16 blueprint gates evidenced or blocker recorded per SSOT rules. Complexity: L. Dependencies: T-006-01, T-003-03. Status: **IN PROGRESS 2026-07-06** — done: installability, data ingestion, determinism (byte-identical rerun), fee modeling (audit PASS), artifact export (canonical parquet + manifests), slippage CapabilityGap documented. Remaining: lookahead/recursive-analysis, bounded hyperopt w/ all-trial retention, dry-run probe, signal parity vs micro goldens, precision/failure probes.

## T-006-03 NautilusTrader lane
- Same contract as T-006-02 with Nautilus-specific probes (bar backtest, fee/fill/latency config, catalog export, Binance-adapter surface). Requirement: REQ-016. Complexity: L. Status: TODO.

## T-006-04 LEAN lane
- Same contract; LEAN-specific probes (local Docker engine, crypto baseline, fill/brokerage models, local-vs-cloud boundary per RG-02 findings). Requirement: REQ-017. Complexity: L. Status: TODO.

## T-006-05 Hummingbot lane
- Same contract; Hummingbot-specific probes (V2 controller config, Dashboard/API backtest path, bot lifecycle, artifact extraction). Requirement: REQ-018. Complexity: L. Status: TODO.

## T-006-06 vectorbt accelerator probe (separate, not a peer)
- Purpose: research-accelerator fit behind anti-overfit controls. Requirement: REQ-019. Precondition: T-001-01 (license).
- Actions: run B2–B4 sweeps; measure throughput; verify all-trial retention pathway; document multiple-testing hazard controls.
- Acceptance: accelerator verdict with evidence. Complexity: M. Status: **IN PROGRESS 2026-07-06** — license verified (CG-10); B2 sweep ran: 34 combos × 577,803 bars in 15.0s (1.31M bar-combos/s), all trials retained (artifacts/bakeoff/vectorbt/). Remaining: B3/B4 sweeps, retention-pathway wiring into experiment ledger, hazard-controls doc, verdict.

## T-006-07 Cross-engine parity analysis (WS4)
- Purpose: semantic diagnosis of every divergence. Requirement: REQ-020 (EG-2 input).
- Actions: SKILL_ENGINE_PARITY_AUDITOR process over all completed lanes on B1–B4; fee recomputation audit; divergence classification.
- Outputs: parity reports per engine pair. Acceptance: zero UNEXPLAINED residuals for PASS; else itemized. Complexity: L. Dependencies: ≥2 lanes done. Status: TODO.

## T-006-08 Bake-off report + role recommendations
- Purpose: `artifacts/reports/ENGINE_BAKEOFF_REPORT.md` (EG-2). Requirement: REQ-021.
- Actions: assemble matrix scores, blockers, role-fit recommendations (select-primary/specialized/fallback/reject per engine) with evidence links.
- Human approval: feeds HG-2, not standalone. Complexity: M. Dependencies: T-006-02..07. Status: TODO.
