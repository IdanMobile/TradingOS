# Session handoff — 2026-07-22

Scope: durable operational handoff only. This record grants no live or real-money authority, makes no profitability claim, and does not authorize reading any prospective, holdout, or sealed outcome.

## Verified facts

- Current implementation track: **v8.129**. Its pre-documentation-reconciliation baseline commit
  is **`c320ec2`**; the v8.130 documentation commit will supersede it as `HEAD`. The protected live
  SSOT remains the v8.127 / D-115 reconciliation because no further immutable-state edit has been
  authorized. D-115 records the selected root-owned external trust boundary; neither v8.128 nor
  v8.129 activates it.
- This session's completed slices, in dependency order:
  - demo stop hardening: `460bce6`, `b997237`;
  - fail-closed promotion package: `8877554`;
  - Phase 2b external-gated intake-decision scaffold: `39b423e`;
  - atomic job-quarantine capability and schema-v4 migration coverage: `f4e06dd`, `377e3f6`;
  - live legacy-job quarantine: `5f62763`;
  - closed-family research-execution retirement: `4e95478`;
  - protected current-state reconciliation: `7934eb9`;
  - external intake-trust setup source: `30884dc`;
  - pending-only activation-authority source contracts: `c320ec2`.
- Final implementation-track gate: `make check` passed with **1,525 passed / 29 deselected**.
- Integrity manifest verification covers exactly **453 table rows / 438 unique paths**, including
  duplicate rows. The pre-existing `src/tios/services/observations/__init__.py` digest had one
  extra trailing `f`; D-115's narrow extension removed it without changing the source file. The
  new non-manifest shape regression test prevents malformed Path/SHA rows from being silently
  skipped by the strict verifier.
- Live local services reverified on 2026-07-22:
  - dashboard: screen `42597.tios-dashboard`, PID `42631`, read-only HTTP on `8765`;
  - orchestrator: PID `29803`;
  - demo lane: screen `10477.tios-demo-lane`, PID `10496`, `real_money=false`, stop confirmed;
  - jobs worker: screen `82104.tios-jobs-worker`, PID `82110`, idle with no child process.
- Jobs DB: schema **4**, SHA-256 prefix **`394df…`**; retained history is four `SUCCEEDED`, one `CANCELLED`, and zero active jobs. Quarantine audit SHA-256 prefix: **`279bb…`**.
- The normalized-data update was verified. Its immutable manifest is `data/normalized_multi/manifests/normalized_multi_manifest_62353a5fadcbb812f1780ce75815e1bbbe5d3863cb8f0aca61a1056ff6f999d0.json`. Runtime and data dirt are intentionally unstaged and must remain distinct from source/governance work.
- Phase status:
  - **Phase 1:** local operating substrate implemented; current services are supervised screen processes, not an operator-approved LaunchAgent installation.
  - **Phase 2:** fail-closed candidate intake ledger implemented; it cannot represent `ADMIT`.
  - **Phase 2b:** typed semantic-assessment scaffold plus independently reviewed external-trust
    setup source (`30884dc`) and pending-only activation-authority source contracts (`c320ec2`)
    are implemented. The reviewed bundle is prepared, but nothing is installed or activated;
    every reachable state retains authority `NONE`.
  - **Phases 3 and 4:** blocked. Do not build or run them yet.
  - **Phase 5:** generic fail-closed validation/promotion evidence package implemented; incomplete evidence remains ineligible, and this package cannot substitute for Phase 2b intake authority or independent review.

## Operator decisions and blockers

1. **Phase 2b source/setup is implemented, but external activation is not complete.** The reviewed
   setup bundle exists at
   `/tmp/tios-intake-reviewed-bundles/39c4521585ff689d05d10a8c80206c7d9706095f9f3112918bb7f486bf4b41c0.bundle`.
   Its bundle SHA-256 is
   `39c4521585ff689d05d10a8c80206c7d9706095f9f3112918bb7f486bf4b41c0`; its installer
   SHA-256 is `ee2ef47742b7417e61dc3da426526f9e10ce272807034c360e9bbc8a52c6b410`.
   The fixed helper directory and `/private/var/db/tios-intake` are absent. No independent
   reviewer is enrolled, and no allowed-signers/KRL trust state, authoritative history,
   monotonic checkpoint, trusted-time observation, genesis, activation receipt, or typed evidence
   resolver has been installed. The reviewer private key and authoritative root state must remain
   outside the repository and unavailable to repository-writing agents. Phases 3–4 remain blocked
   until complete activation evidence is frozen and independently reviewed.
2. **The v8.127 integrity reconciliation is complete under D-115's one-time exception.**
   `PACKAGE_INTEGRITY_MANIFEST.md` remains in `IMMUTABLE_PATHS`; the exception made no policy,
   threshold, sealed/holdout/prospective, or other immutable-path change and grants no future
   manifest-edit authority. Its narrow extension repaired only the malformed existing
   `src/tios/services/observations/__init__.py` digest and added regression coverage; the source
   file and every other manifest row were unchanged by that repair.
3. The operator has elected to retain the current screen-based services in Downloads until the
   application is proven. Moving the repository and installing rendered LaunchAgents are deferred;
   this does not affect the separate fixed-path root trust ceremony.
4. The operator owns disposition of the verified normalized-data update. Do not mix it with source changes or silently stage it.

## Agent-executable next actions

1. Preserve and observe the current services through read-only health/state checks. Do not restart the demo lane automatically, create orders, or grant paper/live authority.
2. Keep legacy/closed-family research jobs quarantined and retired. Do not enqueue replacements or use caller-selected verifiers, repository fakes, generic workspace decisions, or missing history to cross the intake boundary.
3. Keep Phases 3–4 parked until every Phase 2b external-activation requirement above has operator approval and independently reviewed evidence. Phase 5 may only evaluate already-lawful retained evidence; it cannot unblock intake.
4. Continue bounded maintenance that does not cross an authority gate: service health observation, scheduled public-data refreshes, integrity-preserving diagnostics, and tests. Keep generated runtime/data changes unstaged unless the operator selects their disposition.
5. Execute the remaining Phase-2b sequence without skipping gates:
   1. the operator runs the reviewed fail-fast ceremony in `ops/intake_trust/README.md` with the
      recorded bundle and installer digests;
   2. verify read-only that the helper is installed at its fixed root-owned path and still reports
      uninitialized/fail-closed state;
   3. a genuinely independent reviewer generates and retains the private key off-host and supplies
      only reviewed public enrollment material;
   4. separately review and execute fixed-path publication of allowed-signers/KRL trust state,
      activation policy, genesis, authoritative history, monotonic checkpoint, and trusted-time
      observation;
   5. produce a canonical activation status receipt and validate the exact
      `ACTIVE_NO_DECISIONS` activation snapshot against that root-owned state;
   6. obtain and retain an independently signed review record binding the installed helper/source
      hashes, fixed root-owned state, and activation receipt;
   7. implement and independently review the fixed-path typed evidence resolver and
      current-receipt consumer against that reviewed state;
   8. obtain explicit operator authority for the required integrity freeze, rehash every affected
      manifest row, and record the same change in the package changelog;
   9. only after the frozen activation evidence passes independent security review, begin Phase 3,
      then Phase 4 after Phase 3's contract/identity bridge passes `make check`.

## Future date gates

- **2026-10-04:** recurring T-001-06 registry sweep is due; routine T-000-01/03/04 upkeep continues.
- **2027-01-14:** earliest lawful boundary for the one permitted sealed-holdout evaluation. Do not inspect it before this date; reaching the date does not itself authorize evaluation.
- **2027-01-17:** earliest scheduled MVRV prospective review. Review only under the retained protocol; do not inspect outcomes early.
- **2027-01-21:** earliest scheduled CFTC prospective review. Review only under the retained protocol; do not inspect outcomes early.

The v8.127 changelog/version reconciliation belongs only to D-115's one-time integrity exception;
it creates no continuing permission to edit the integrity manifest.
