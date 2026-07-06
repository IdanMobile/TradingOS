# Planning Handoff Simulation — 2026-07-06

Result: **PASS after fixes** (fixes applied during this pass; listed below).
Premise: a fresh coding agent receives only the repository/package (v8) and the single instruction `Read and execute handoffs/START_HERE_SINGLE_CODING_AGENT_PROMPT.md`. No chat history. This extends `handoffs/HANDOFF_SIMULATION_AUDIT_V1.md` (v7) to the new planning layer.

## Simulated flow

1. **First read** — agent finds the SSOT via PACKAGE_README / instruction. PASS.
2. **SSOT resolution** — SSOT §0 precedence now includes planning authorities (slot 5) and TODO layer (slot 6) with the explicit rule that TODO never expands scope and AD maturity labels bind. No competing controller found: TODO.md, PROGRAM_PLAN, AD all declare subordination in their headers. PASS.
3. **Integrity self-check** — manifest regenerated for v8 with planning inputs listed; verification script logic documented in manifest. The v7 input/output contract (expected-generated-artifacts list) is preserved unchanged. PASS.
4. **Mandatory read order** — extended (items 20–27) to cover scope, program, architecture, catalogs, test plan, TODO, and refreshed research with its as-of date. Order is deliberate: original controls first, planning layer second. PASS.
5. **Pre-code intake** — unchanged hard gate; SSOT §4 now names T-003-01 as the first task, which *is* the intake gate — no ambiguity about what comes first. PASS.
6. **First task selection** — SSOT §4 stage pointer → TODO.md execution order → `todos/03_repository_foundation.md` T-003-01. Deterministic. PASS.
7. **Task execution** — tasks carry actions/outputs/acceptance/failure conditions; anti-vagueness rule; module boundaries and test gates referenced. Spot-checked T-004-02 (µs boundary reachable from task → Amendment A1 → D-029 → registry evidence). PASS.
8. **Testing** — TEST_MASTER_PLAN local gate defined before any implementation task depends on it (T-003-04 precedes all engine/data work in the order). PASS.
9. **Failure handling** — SSOT §9 stop conditions + PROGRAM_PLAN §5 stop/change rules + per-task failure conditions + AD §AD fallbacks. Simulated failure (Binance data unreachable): T-004-01 failure condition → SSOT WS2 stop rule → open-item record. Coherent. PASS.
10. **State update** — SSOT §8 + T-000-01/02/03 make upkeep a tracked obligation, including manifest regeneration after controlled edits (the v8 trap that would otherwise break integrity checks). PASS.
11. **Next-task determination** — TODO.md order + PROGRAM_PLAN dependency graph agree (checked pairwise). PASS.
12. **Handoff mid-phase** — a successor agent re-reading the SSOT + PROJECT_STATE + TODO statuses + artifacts can reconstruct: what's approved (decision log), what's provisional (AD §AL), what's done (task acceptance evidence), what's next (first TODO task not DONE in stage order), what's forbidden (SSOT §3/§9, MVP_SCOPE §8). The §2 SSOT Progress Rule checklist from the mandate was walked item-by-item: all answerable from repository files alone. PASS.
13. **Resumption by a different agent after partial S1** — simulated: dataset frozen, Freqtrade lane half-done. Successor finds: artifacts + manifests (WS1 tree), task statuses, engine env manifests, decision log untouched (no premature selections possible — maturity labels). PASS.

## Ambiguities found and fixed during simulation

- F-P1: SSOT precedence had no slot for the planning docs → could have read as competing controllers. Fixed: precedence slots 5–6 + subordination headers in each planning doc (D-030).
- F-P2: "First task" was implicit (intake gate described but not named as a task). Fixed: SSOT §4 names T-003-01; PROJECT_STATE repeats it.
- F-P3: Duplicate decision IDs (D-022/D-023 reused) would confuse any agent following references. Fixed: renumbered D-027/D-028 (D-031); uniqueness check added to local-gate requirements (REQ-032).
- F-P4: Manifest would go stale the moment state files change → fresh agent would see FAIL rows and halt wrongly. Fixed: manifest regenerated at v8; T-000-02 makes regeneration a standing task; manifest header documents the rule.
- F-P5: Dataset spec silently predated the Binance µs change → a compliant agent would have produced a subtly wrong normalizer. Fixed: Amendment A1 in the spec itself (not only in research notes), per D-029.
- F-P6: traceability used ad-hoc suffixed IDs (D-022a) → normalized to canonical IDs.

## Residual risks (unchanged in kind from v7 audit)

External drift (APIs, models, versions) — mitigated by reverify triggers, not eliminated. Agent disobedience — mitigated by gates/evidence requirements, not eliminated. Local-machine unknowns — resolved only at intake/inspection.

## Conclusion

A fresh coding agent with only this repository can determine the project's what/why/approved/provisional/done/next/forbidden without chat history, and can execute S1 end-to-end under the existing SSOT. Planning handoff: **PASS**.
