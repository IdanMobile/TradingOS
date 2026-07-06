# Red Team Plan Review — 2026-07-06

Posture: attack the planning system itself. Each attack gets a verdict: DEFENDED (plan already handles it), FIXED (plan changed during this review), ACCEPTED RISK (explicit, owned), or EXPOSED (unresolved — must be zero at completion).

## Attacks

### A1. Unnecessary complexity / premature abstraction
Attack: 18 modules + 7 converters + registries for a single operator is over-engineering.
Verdict: **DEFENDED with one FIX.** Modules are boundaries (files/folders), not services; MVP builds thin versions only; jobs/events are DB tables, not brokers; graph DBs, vector DBs, TSDBs, Temporal, workers all rejected with evidence (AD-04/08/10). FIX applied: application count collapsed to one CLI + one read-only dashboard (AD §G) after this attack.

### A2. Microservices creep
Verdict: **DEFENDED.** No second process until S3 paper lane; event architecture explicitly reconsidered only then (AD §R).

### A3. Excessive custom code
Attack: Evidence Registry / Approval Engine / RA registry could be spreadsheets.
Verdict: **ACCEPTED RISK, bounded.** These are the North-Star differentiator (§15) and passed the Custom Build Gate (no existing tool owns cross-engine evidence + contextual approval semantics — REG re-check 2026-07-06). Bound: S1 builds only the *thin* versions (Test C jsonl/SQLite scale); expansion requires S2 evidence.

### A4. Vendor lock-in
Verdict: **DEFENDED.** Replaceability is an executable lineage-prototype gate; domain stores public refs only; engines behind ports with exit strategies; UI is a projection. Residual: MLflow becoming both lineage AND eval backbone concentrates dependency — ACCEPTED RISK with named fallbacks (Aim/ClearML; Inspect for eval) in REG §2/§7.

### A5. Hidden AI assumptions
Attack: plan quietly assumes AI agents are competent at extraction/critique.
Verdict: **DEFENDED.** WS8 exists precisely to measure this; roles carry benchmark suites; harness works credential-less; no routing claim may precede benchmark evidence (AGENT_ROLES final rule).

### A6. Weak backtesting / data leakage / survivorship / multiple testing
Verdict: **DEFENDED at design level; execution is the real test.** G4 leaky-fixture discipline ("a gate that never failed a fixture is not a gate" — TMP rule), all-trial retention, G10 method-candidate honesty (not claiming PBO/DSR before validation — RG-07). Survivorship: instruments are majors (BTC/ETH) chosen for infrastructure proof, not universe claims; any universe-selection strategy later must add a survivorship gate — recorded in initiative 20 design notes.

### A7. Poor reproducibility
Verdict: **DEFENDED.** Double-regeneration dataset proof, content-addressed runs, environment manifests, golden discipline. Residual: engine-internal nondeterminism unknown until WS3 — that's what the determinism gate measures.

### A8. Live safety
Verdict: **DEFENDED (by absence).** No live code paths exist; live-state-unreachable is a *test*; human gates non-delegable; withdrawal-enabled keys never requestable (intake gate).

### A9. Exchange dependency
Attack: everything leans on Binance public data; Binance is regulatorily gray for the operator.
Verdict: **ACCEPTED RISK, mitigated.** Data source ≠ trading venue (D-024 separation); dataset is frozen/reproducible so a source loss doesn't destroy evidence; venue matrix keeps 4 candidates with OKX/Kraken paths; Israel-fit verification is a named human gate (RG-05/HG-4).

### A10. Strategy ingestion risk (malicious code, licenses)
Verdict: **DEFENDED.** Ingested code never runs in-process (T-018-02 containment + test); license-class gating blocks unclear reuse; prompt-injection rule (external content = data). Residual: Pine/community licensing ambiguity — handled per-item in seed batch with license records.

### A11. Prompt injection
Verdict: **DEFENDED at policy level; EXPOSED→FIXED at test level.** FIX: added containment/injection checks to SKILL_SECURITY_REVIEWER process and T-018-02 acceptance (ingested sample attempting instruction-injection must not alter agent behavior in test).

### A12. Data licensing
Verdict: **DEFENDED.** Binance public data used as source with manifests (payloads re-downloadable, not redistributed); FIBO MIT for concepts; Investopedia-class scraping banned (AD-09); every SRC carries license record.

### A13. Model drift / stale research
Verdict: **DEFENDED.** Longitudinal benchmark mode; per-provider deprecation watch; registry 90-day expiry; Sonnet-5 intro-pricing end date recorded; freshness states on RAs.

### A14. Expensive infrastructure
Verdict: **DEFENDED.** Zero cloud, zero paid data, zero paid tools required for S1; AI spend optional and credential-gated; cost intelligence is a first-class domain.

### A15. Impossible maintenance burden (single operator)
Attack: the deepest threat. 21 initiatives, 13 skills, 5 engines, registries — one human cannot sustain this.
Verdict: **ACCEPTED RISK, structurally bounded.** Bounds: (1) S1 exit criteria require only 2 engines working; losers get deleted at S2 (T-002-02 mothball rule); (2) every registry has an owner-skill and an expiry sweep instead of manual curation; (3) reports are generated projections; (4) the stop rule (PROGRAM_PLAN §5) legitimizes shrinking scope; (5) dashboard MVP is one Streamlit file. Standing instruction to future planners: when in doubt, cut breadth, keep gates.

### A16. Weak UX
Verdict: **ACCEPTED for S1 (evidence surface only, by design); S2 console has an IA direction + anti-CRUD-framework decision (AD-07) to avoid a messy console.**

### A17. The plan itself rots
Attack: 20+ new documents will drift from reality like all documentation.
Verdict: **FIXED.** Drift defenses added during this review: docs carry Date + reverify triggers; SOURCE_VERIFIER sweep task (T-001-06); Architecture Guardian drift audit; decision-ID uniqueness in local gate; manifest regeneration task (T-000-02). Reports/state generated where possible.

### A18. Benchmark theater
Attack: AI benchmarks measure fixture performance, not real value.
Verdict: **DEFENDED.** Downstream-value scoring (funnel to validated strategies) is a separate score family; controlled fixtures are only one mode; economic-attribution caution inherited from KTD-Fin evidence (D-021).

### A19. Evidence theater
Attack: gates can pass on paper while proving nothing (e.g., G1 tolerance set loose, parity "explained" glibly).
Verdict: **FIXED.** Added to TMP/skills during review: every gate needs a must-FAIL fixture; parity PASS requires zero UNEXPLAINED residuals; fee totals recomputed, not read from engine claims.

## Exit state

EXPOSED count: **0**. ACCEPTED RISKS: A3, A4(residual), A9, A15, A16 — each owned and bounded above. FIXES applied: A1 (app collapse), A11 (injection tests), A17 (drift defenses), A19 (must-fail fixtures, parity strictness).
