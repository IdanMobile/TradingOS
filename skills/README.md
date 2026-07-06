# Agent Skills — Trading Intelligence OS

Status: Approved planning baseline v1
Date: 2026-07-06

A skill is a reusable, versioned task procedure for AI agents: trigger conditions, process, quality gates, prohibited behavior. Skills bind to roles in `docs/ai/AGENT_ROLES.md`; roles bind to agent configurations in the registry. Skills are specifications here — implementation (as prompts/skill files for the chosen agent runtime) happens in S1/S2 when each is first needed.

## Design rule

A skill exists only if the task (a) recurs, (b) has a checkable output contract, and (c) fails in known ways a procedure can prevent. Skills were merged aggressively; a skill per tool/framework was rejected as premature.

## Accepted skills

| Skill file | Role | First needed | Purpose |
|---|---|---|---|
| `SKILL_ECOSYSTEM_SCOUT.md` | R1 | S0 (ongoing) | discover prior art for a capability gap |
| `SKILL_SOURCE_VERIFIER.md` | R2 | S0 (ongoing) | verify claims/versions/licenses/changelogs against primary sources; freshness audits |
| `SKILL_STRATEGY_SOURCE_INGESTOR.md` | R3 | S1 WS7 | source→license→canonical-spec extraction for any source class (paper/Pine/Freqtrade/LEAN/Hummingbot/prose) |
| `SKILL_CANONICAL_SPEC_VALIDATOR.md` | R3/R9 | S1 WS7 | validate canonical strategy specs: completeness, ambiguity honesty, schema |
| `SKILL_BACKTEST_RED_TEAM.md` | R4 | S1 WS6 | attack backtests/validation packages incl. leakage hypotheses |
| `SKILL_DATA_QUALITY_AUDITOR.md` | R4 | S1 WS2 | audit dataset freezes against the quality-gate spec |
| `SKILL_ENGINE_PARITY_AUDITOR.md` | R4 | S1 WS4 | diagnose cross-engine divergences semantically (incl. fee/slippage config audit) |
| `SKILL_VALIDATION_STATS_SPECIALIST.md` | R4/R7 | S1 WS6 (G10) | PBO/DSR method implementation review against primary literature |
| `SKILL_BENCHMARK_RUNNER.md` | R8 | S1 WS8 | execute frozen AI benchmark tasks under leakage controls; score with calibrated judges |
| `SKILL_RESEARCH_ASSET_SYNTHESIZER.md` | R5 | S1/S2 | multi-source synthesis into RA records with contradictions preserved |
| `SKILL_ONTOLOGY_CURATOR.md` | R6 | S2 | concept extraction/curation with venue-context preservation |
| `SKILL_ARCHITECTURE_GUARDIAN.md` | R9 | S1 (from WS1) | diff/dependency review against AD + module law (incl. boundary audit) |
| `SKILL_SECURITY_REVIEWER.md` | R9 | S1 (from WS1) | secret handling, dependency risk, ingested-code sandbox policy, prompt-injection surface |

## Rejected / merged skill candidates (with reasons)

| Candidate (from mandate list) | Decision | Reason |
|---|---|---|
| Official Documentation Verifier, Citation Verifier, API Changelog Watcher, Documentation Freshness Auditor, Exchange Capability Verifier | Merged → SOURCE_VERIFIER | identical process (primary-source check + record + reverify trigger); separate skills would share 90% of their spec |
| Pine / Freqtrade / LEAN / Hummingbot extractors, Academic Strategy Reproducer, Strategy Source Ingestor | Merged → STRATEGY_SOURCE_INGESTOR | one lifecycle (ingestion workflow V1) with per-source-class appendices; split later only if the 10-item seed batch shows the procedures genuinely diverge (EG-5 evidence) |
| Leakage Auditor | Merged → BACKTEST_RED_TEAM (dedicated section) | leakage is the red team's sharpest attack, not a separate workflow |
| Fee/Slippage Auditor | Merged → ENGINE_PARITY_AUDITOR + validation gate G5 | cost-config verification is a step inside parity and validation, not a standalone recurring task |
| Open-Source Project Auditor | Merged → ECOSYSTEM_SCOUT (depth mode) + SOURCE_VERIFIER | audit = scout finding + verifier check |
| PBO/DSR Validation Specialist | Kept (VALIDATION_STATS_SPECIALIST) | genuinely specialized: math must be checked against primary papers |
| Model Benchmark Runner / Agent Benchmark Runner | Merged → BENCHMARK_RUNNER | same harness, same controls; "model vs agent" is a parameter (mode A vs B) |
| Ontology Extractor / Dictionary Curator | Merged → ONTOLOGY_CURATOR | extraction and curation share the ambiguity-preservation core |
| Dependency Boundary Auditor | Merged → ARCHITECTURE_GUARDIAN | dependency law is one section of the architecture review |
| Backtest Red Team | Kept | distinct adversarial posture |

## Common spec sections (every skill file)

Purpose · Trigger conditions · Inputs · Tools · Process · Outputs (contract) · Prohibited behavior · Quality gates · Evidence requirements · When NOT to use · Model suitability & cost sensitivity.

## Versioning

Skill specs are versioned files; a change that alters outputs requires a version bump and a note in `PACKAGE_CHANGELOG.md`. Benchmark results reference the skill version used.
