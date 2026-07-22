# Session handoff — 2026-07-22

Scope: durable operational handoff only. This record grants no live or real-money authority, makes no profitability claim, and does not authorize reading any prospective, holdout, or sealed outcome.

## Verified facts

- Package version: **v8.126**. Current `HEAD`: **`4e95478`**.
- This session's completed slices, in dependency order:
  - demo stop hardening: `460bce6`, `b997237`;
  - fail-closed promotion package: `8877554`;
  - Phase 2b external-gated intake-decision scaffold: `39b423e`;
  - atomic job-quarantine capability and schema-v4 migration coverage: `f4e06dd`, `377e3f6`;
  - live legacy-job quarantine: `5f62763`;
  - closed-family research-execution retirement: `4e95478`.
- Final local gate: `make check` passed with **1,467 passed / 29 deselected**.
- Live local services at handoff:
  - dashboard: screen `42597.tios-dashboard`, PID `42631`, read-only HTTP on `8765`;
  - orchestrator: PID `29803`;
  - demo lane: screen `10477.tios-demo-lane`, PID `10496`, `real_money=false`, stop confirmed;
  - jobs worker: screen `82104.tios-jobs-worker`, PID `82110`, idle with no child process.
- Jobs DB: schema **4**, SHA-256 prefix **`394df…`**; retained history is four `SUCCEEDED`, one `CANCELLED`, and zero active jobs. Quarantine audit SHA-256 prefix: **`279bb…`**.
- The normalized-data update was verified. Its immutable manifest is `data/normalized_multi/manifests/normalized_multi_manifest_62353a5fadcbb812f1780ce75815e1bbbe5d3863cb8f0aca61a1056ff6f999d0.json`. Runtime and data dirt are intentionally unstaged and must remain distinct from source/governance work.
- Phase status:
  - **Phase 1:** local operating substrate implemented; current services are supervised screen processes, not an operator-approved LaunchAgent installation.
  - **Phase 2:** fail-closed candidate intake ledger implemented; it cannot represent `ADMIT`.
  - **Phase 2b:** typed semantic-assessment scaffold implemented; it can reach only externally blocked pending states with authority `NONE`.
  - **Phases 3 and 4:** blocked. Do not build or run them yet.
  - **Phase 5:** generic fail-closed validation/promotion evidence package implemented; incomplete evidence remains ineligible, and this package cannot substitute for Phase 2b intake authority or independent review.

## Operator decisions and blockers

1. **Phase 2b external activation is operator-controlled.** Phases 3–4 remain blocked until an operator-approved change provides a fixed external verifier outside repository-writer control, authoritative append-only decision history with an externally retained monotonic checkpoint, a typed independent evidence resolver, trusted time plus credential/revocation/trust evidence, a genuinely independent reviewer and credential lifecycle, frozen interfaces/integrity rows/changelog evidence, and independent security review.
2. **`PROJECT_STATE.md` is materially stale** on the demo process/stop state and package version. It is manifest-listed, and correct regeneration would also edit `PACKAGE_INTEGRITY_MANIFEST.md`; that manifest is currently in `IMMUTABLE_PATHS`. An operator-controlled integrity update or explicit policy change is therefore required. Do not hand-edit either file or evade the integrity workflow.
3. The operator must decide whether to retain the current screen-based services or move the repository out of the macOS TCC-protected Downloads location and explicitly approve/install the rendered LaunchAgents.
4. The operator owns disposition of the verified normalized-data update. Do not mix it with source changes or silently stage it.

## Agent-executable next actions

1. Preserve and observe the current services through read-only health/state checks. Do not restart the demo lane automatically, create orders, or grant paper/live authority.
2. Keep legacy/closed-family research jobs quarantined and retired. Do not enqueue replacements or use caller-selected verifiers, repository fakes, generic workspace decisions, or missing history to cross the intake boundary.
3. Keep Phases 3–4 parked until every Phase 2b external-activation requirement above has operator approval and independently reviewed evidence. Phase 5 may only evaluate already-lawful retained evidence; it cannot unblock intake.
4. Continue bounded maintenance that does not cross an authority gate: service health observation, scheduled public-data refreshes, integrity-preserving diagnostics, and tests. Keep generated runtime/data changes unstaged unless the operator selects their disposition.
5. After operator authority is supplied, the first lawful governance action is the controlled integrity regeneration/update for `PROJECT_STATE.md` and `PACKAGE_INTEGRITY_MANIFEST.md`; separately, the first lawful Phase 2b action is to specify and independently review the external verifier/history/checkpoint/resolver/reviewer composition. Only after that activation is frozen may Phase 3 begin.

## Future date gates

- **2026-10-04:** recurring T-001-06 registry sweep is due; routine T-000-01/03/04 upkeep continues.
- **2027-01-14:** earliest lawful boundary for the one permitted sealed-holdout evaluation. Do not inspect it before this date; reaching the date does not itself authorize evaluation.
- **2027-01-17:** earliest scheduled MVRV prospective review. Review only under the retained protocol; do not inspect outcomes early.
- **2027-01-21:** earliest scheduled CFTC prospective review. Review only under the retained protocol; do not inspect outcomes early.

No changelog edit or version bump belongs to this handoff.
