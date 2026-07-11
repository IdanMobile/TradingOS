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
- Acceptance: all 16 blueprint gates evidenced or blocker recorded per SSOT rules. Complexity: L. Dependencies: T-006-01, T-003-03. Status: **DONE 2026-07-10 — COMPLETE WITH CONSTRAINTS.** Exact B1–B4 signal parity, recursive analysis, precision/failure behavior, hyperopt retention, dry-run, determinism, fee audit, and artifact export are evidenced. Native lookahead forced-state behavior and slippage remain explicit WARN/capability gaps in `FREQTRADE_LANE_REPORT.md`.

## T-006-03 NautilusTrader lane
- Same contract as T-006-02 with Nautilus-specific probes (bar backtest, fee/fill/latency config, catalog export, Binance-adapter surface). Requirement: REQ-016. Complexity: L. Status: **DONE 2026-07-07** for bounded matrix evidence; full-history expansion and latency-model exercise remain explicit follow-ups in the lane notes.

## T-006-04 LEAN lane
- Same contract; LEAN-specific probes (local Docker engine, crypto baseline, fill/brokerage models, local-vs-cloud boundary per RG-02 findings). Requirement: REQ-017. Complexity: L. Status: **DONE 2026-07-11 FOR BOUNDED LOCAL DOCKER EVIDENCE** — B1-B4 x `{F0/S0,F1/S1}` run1 all completed through local Docker with custom data and no cloud/account path; B1 F0/S0 run2 matched run1 fills exactly. Full-range parity remains a throughput/scope expansion question. Evidence: `artifacts/bakeoff/lean/STATUS.md`.

## T-006-05 Hummingbot lane
- Same contract; Hummingbot-specific probes (V2 controller config, Dashboard/API backtest path, bot lifecycle, artifact extraction). Requirement: REQ-018. Complexity: L. Status: **DONE FOR BOUNDED CAPABILITY / FULL-HISTORY THROUGHPUT BLOCKED** — Bounded BTCUSDT 30-day B1-B4 x `{F0/S0,F1/S1}` x `{run1,run2}` evidence is complete, normalized, fee-audited, and deterministic; Docker timeout cleanup now stops named containers and writes timeout manifests. Full-history B2 F1/S1, B3/B4, and full-history determinism remain a throughput track; the chunking/throughput design is complete in `specs/HUMMINGBOT_FULL_HISTORY_CHUNKING_DESIGN_V1.md` (30-day warm-up-prefixed windows, seam-audited stitching, per-window timeouts) with an explicit operator rerun-decision framing — execution stays unscheduled while no candidate has positive bounded evidence. Evidence: `artifacts/reports/HUMMINGBOT_PRODUCTIONIZATION_STEP_2026_07_11.md`, `artifacts/bakeoff/hummingbot/BLOCKER_REPORT.md`, and `artifacts/reports/HUMMINGBOT_FULL_HISTORY_TIMEOUT_2026_07_11.md`.

## T-006-06 vectorbt accelerator probe (separate, not a peer)
- Purpose: research-accelerator fit behind anti-overfit controls. Requirement: REQ-019. Precondition: T-001-01 (license).
- Actions: run B2–B4 sweeps; measure throughput; verify all-trial retention pathway; document multiple-testing hazard controls.
- Acceptance: accelerator verdict with evidence. Complexity: M. Status: **DONE 2026-07-10** — B2/B3/B4 ran 66 declared trials over 577,803 bars; all 66 retained in Parquet and the append-only experiment ledger; binding overfit controls recorded; selected as research accelerator only, never execution/approval authority.

## T-006-07 Cross-engine parity analysis (WS4)
- Purpose: semantic diagnosis of every divergence. Requirement: REQ-020 (EG-2 input).
- Actions: SKILL_ENGINE_PARITY_AUDITOR process over all completed lanes on B1–B4; fee recomputation audit; divergence classification.
- Outputs: parity reports per engine pair. Acceptance: zero UNEXPLAINED residuals for PASS; else itemized. Complexity: L. Dependencies: ≥2 lanes done. Status: **DONE 2026-07-10 FOR AVAILABLE LANES** — three Freqtrade/Hummingbot contexts have zero unexplained residuals; B1 timing and B2 execution/order-state/data-gap divergences are retained. Nautilus/LEAN bounded scope and Hummingbot runtime-blocked coverage remain explicit.

## T-006-08 Bake-off report + role recommendations
- Purpose: `artifacts/reports/ENGINE_BAKEOFF_REPORT.md` (EG-2). Requirement: REQ-021.
- Actions: assemble matrix scores, blockers, role-fit recommendations (select-primary/specialized/fallback/reject per engine) with evidence links.
- Human approval: feeds HG-2, not standalone. Complexity: M. Dependencies: T-006-02..07. Status: **DONE 2026-07-10 WITH RECORDED BLOCKED LANES** — role recommendations and constraints are evidence-backed; this is an HG-2 input, not approval.
