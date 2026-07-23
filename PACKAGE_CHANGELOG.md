# Package Changelog

## v8.137 — 2026-07-23 — Canonical timeframe contract verification

- Made dataset spacing and missing-interval helpers derive durations from the canonical
  `Timeframe` contract and added synthetic coverage for all six supported values: 1m, 5m, 15m,
  1h, 4h, and 1d. The frozen bake-off dataset population remains unchanged.
- Added fixture-backed evaluator checks that retime the existing micro price paths across all six
  frames and verify transition ordinal/side invariance, emitted timeframe identity, close-time
  causality, and the one-hour-only calendar boundary. Added bounded synthetic paper checks for
  closed-bar evaluation and fail-closed kline-gap behavior on every canonical frame.
- Added a pure causal lower-to-higher close-time alignment helper with representative 1m→5m,
  5m→1h, 15m→4h, and 1h→1d coverage plus invalid-pair and unclosed-higher-bar refusal checks.
  These are implementation-contract tests only: retiming one price path is not evidence of
  strategy edge, statistical validity, promotion readiness, or live-trading authority.

## v8.136 — 2026-07-23 — Portable root-installer ancestor mode check

- Corrected the external intake helper installer's fail-closed ancestor validation for macOS BSD
  `stat`: `%u:%g:%Lp` is now compared with the exact numeric `0:0:755` contract. The previous
  `%u:%g:%OLp` output was numeric (`0:0:755`) but was incorrectly compared with the symbolic
  string `0:0:drwxr-xr-x`, so the reviewed ceremony safely stopped at `/Library` even when that
  ancestor was a valid root-owned, wheel-group, non-symlink directory with mode `0755`.
- The stopped ceremony published no helper directory and created no trust, history, checkpoint,
  or other state. Symlink and directory checks remain mandatory and unchanged; this repair does
  not loosen the fixed path, ownership, confinement, digest, or atomic-publication guards.
- Advanced the deterministic intake setup bundle `VERSION` from 1 to 2 so any future operator
  ceremony must use a newly reviewed bundle and installer digest containing this portability
  repair. Added static regression coverage for the BSD numeric format and exact expected value,
  rejection of the former symbolic mismatch, and the v2 bundle requirement. No production bundle
  was built and no privileged path, helper, or state was touched by this source-only change.

## v8.135 — 2026-07-23 — Repair-plan CLI path normalization

- Fixed the one-time repair CLI boundary to accept both the repository-relative plan path emitted
  for operator use and its equivalent absolute path inside the fixed
  `data/normalized_multi/repair_plans` directory. Relative paths are converted lexically from the
  current repository working directory without resolving through symlinks, then pass through the
  same fixed-directory, real-parent, single-link regular-file, canonical-content, and
  content-addressed filename checks as absolute paths.
- Added regression coverage for the real relative and absolute loading forms plus traversal,
  final-component symlink, wrong-directory, symlink-parent, and wrong-digest filename refusal.
  The prior failed production apply stopped before lock, network, journal, staging, or data
  mutation. This source/test repair performs no plan generation, apply, recovery, network access,
  normalized-data mutation, research action, or execution-authority change.

## v8.134 — 2026-07-23 — Read-only TradingView navigation and bounded integrity reconciliation

- `src/tios/services/dashboard_ui/dashboard.html`: added a read-only link to TradingView's full
  BTCUSDT chart plus governed buttons from the embedded-chart context to the existing OS metrics
  and OS strategies views. The UI explicitly explains that the embedded selector is
  indicator-only and continues to classify TradingView as external visual context, not OS
  evidence. No account, credential, signal ingestion, strategy import, or order surface was added.
- `tests/test_dashboard.py`: pinned the external chart URL, embedded-selector limitation, governed
  internal-view hooks, and their navigation wiring. The focused dashboard tests and final
  `make check` release gate passed.
- Included the existing nonmanifest
  `docs/supervisor/TRADINGVIEW_STRATEGY_INDICATOR_PATTERN_CATALOG_PLAN_2026-07-23.md` as an optional
  proposed roadmap artifact. It authorizes no implementation or research run, preserves closed
  family and multiplicity rules, and retains execution authority `NONE`.
- `DECISION_LOG.md`: added D-116, recording the operator's exact one-time exception. Under that
  exception, `PACKAGE_INTEGRITY_MANIFEST.md` advances to v8.134 and changes only its package-version
  line, both existing duplicate dashboard rows, both existing duplicate dashboard-test rows, and
  the existing decision-log row. No row was added or removed; the exception is exhausted by this
  reconciliation. No immutable policy, threshold, prospective/holdout/sealed evidence, runtime,
  data, intake, strategy, campaign, venue, order, live, or real-money authority changed.

## v8.133 — 2026-07-23 — Fail-closed full-demo readiness inspection

- Added one deterministic, read-only full-demo readiness command that authenticates the
  dashboard, orchestrator, jobs worker, and demo lane using the resolved executable, complete
  allowlisted argv, and exact resolved repository working directory. Process-table, CWD, and
  future root-owned authority probes use concurrent, deadline-aware bounded stdout/stderr
  collection; timeout, overflow, ambiguous metadata, unknown CWD, executable mismatch, argv-tail
  spoofing, and unapproved dashboard arguments fail closed, with process groups killed and reaped.
- Operational JSON and JSONL evidence is read through descriptor-anchored, no-follow traversal of
  every fixed path component with regular-file/link-count and byte limits. Dashboard liveness uses
  only the static shell and a bounded fixed negative API-schema probe whose handlers perform no
  project projection reads; demo safety is reconstructed locally from bounded heartbeat, state,
  and retained demo-order reconciliation evidence. No default dashboard walkthrough is approved
  until its prospective/holdout read audit closes.
- The report distinguishes `READY`, operational `AUTHORITY_GATED`, and unsafe or incomplete
  `DEGRADED`. `AUTHORITY_GATED` exits zero only when every operational check passes and external
  intake activation is safely incomplete; it never implies decision admission, strategy
  promotion, execution authority, or real-money readiness. The runbook permits retained
  historical/operational evidence while explicitly excluding preregistered prospective and sealed
  holdout outcomes, and forbids `START`, `STOP`, `RUN_ONCE`, campaigns, or repair during the demo.
- Added 29 focused tests covering normal, oversized, timed-out, and descendant-held subprocess
  pipes; executable/argv spoofing and wrong-CWD rejection for all services; exact safe dashboard
  argv; descriptor and ancestor symlink refusal; dashboard route confinement; authority gating;
  quality/evidence degradation; demo safety; and read-only behavior. No authority was created or
  granted, no order was placed/cancelled/modified, and no preregistered prospective or sealed
  outcome was read. The checker does read the bounded retained demo order ledger solely to
  corroborate current fake-money exposure and disaster-stop coverage.

## v8.132 — 2026-07-22 — One-time normalized refresh repair capability

- Added an offline, deterministic repair planner for the pre-v8.131 daily-refresh open-candle
  defect. It verifies the exact ten content-addressed archived manifests, their schema and table
  population, retained REST filename/content hashes, all 69 current parquet hashes and sizes,
  current manifest/status bytes, and updater/repair source identities. It derives exactly 640
  affected coordinates across 64 refreshable tables (370 daily, 140 hourly, 130 four-hour), with
  576 retained-REST and 64 explicitly manifest-only evidence classifications; the five stale
  tables are excluded. Plans are canonical, content-addressed, fixed-directory artifacts and
  planning performs no network access or dataset mutation.
- Added a plan-bound, fixed-Binance-endpoint apply/recovery implementation. It refuses code,
  state, archive, or raw-evidence drift before network access; accepts only one exact bounded,
  nonredirected row per coordinate; retains response bytes before semantic use; fetches and
  validates all 640 rows before publication; stages only the 64 affected parquets; preserves
  exact row counts, schemas, coverage coordinates, and non-target logical fingerprints; and audits
  all 69 tables. The production CLI exposes no URL or dataset-path override.
- Added journaled before-byte backups, exact before/after hash classification, rollback on every
  pre-receipt failure, unknown-third-hash refusal, deterministic recovery, a receipt-last commit
  marker, and zero-network success idempotency. Committed-state verification resolves the exact
  69-entry audit population and refuses current parquet, manifest, status, receipt, or audit drift.
  Recovery holds the same external lock as refresh/apply and authenticates the exact 64-file
  journal envelope, paths, plan-bound before hashes, after hashes, and backup locations before any
  rollback. Focused tests cover exact derivation/evidence counts, corrupt evidence, offline
  planning, strict files/paths, query responses, all-fetch-before-publish ordering, exact
  replacement, lock sharing, injected publication failure and rollback, committed-state drift,
  missing/extra/duplicate audit and journal entries, complete repeatable recovery, receipt
  idempotency, unknown recovery state, and CLI confinement. No plan, network fetch, live dataset
  repair, prospective/holdout outcome read, research action, or execution authority was performed
  by this source/test release.

## v8.131 — 2026-07-22 — Closed-bar daily refresh correctness

- Changed the refresh boundary to one run-wide UTC cutoff, removes any pre-existing row whose
  canonical close is later than that cutoff, and admits only REST rows whose Binance close time is
  at or before it. Exact decoded REST pages are retained before filtering, so excluded in-progress
  rows remain auditable without entering normalized data.
- Refetches the final retained open timestamp on every file and explicitly prefers the fresh,
  closed REST row over its existing duplicate. Status now separates genuinely added rows from
  actually changed overlap rows; identical overlaps neither increment revisions nor rewrite the
  parquet. Forward pagination must advance and is bounded.
- Added a dataset-keyed nonblocking process lock outside the repository plus same-directory atomic
  publication for each changed parquet, current status, immutable status archive, current manifest,
  and content-addressed manifest archive. Replace is the in-process commit boundary; post-replace
  directory-fsync failure is reported as degraded crash durability and never as a false rollback.
  Artifacts are individually atomic; the multi-file run is not represented as one transaction.
- New manifests bind immutable content-addressed status bytes and carry added, changed-revision,
  and excluded-open counts, so later status replacement does not invalidate that lineage binding.
- Made normalized snapshot coverage explicitly `null` for an empty table, allowing an all-open
  input file to publish zero rows and a truthful current manifest instead of failing after status.
  Versioned open-time cursor and cutoff metadata are embedded in the same atomic parquet
  publication, so a status failure or later-file failure cannot strand an empty artifact. Status
  retains a redundant cursor: conflicts fail closed for empty recovery, while a nonempty parquet
  authenticates its cursor against its last committed row and safely supersedes stale status from
  a partial multi-file run. Operational schema metadata is stripped from logical candle-content
  hashing to preserve prior hash semantics. Embedded cursors must be canonical milliseconds no
  later than their embedded cutoff; equality is accepted and sub-milliseconds are floored exactly.
- Added focused tests for open-current exclusion with raw retention, exact cutoff inclusion,
  finalized and identical overlap behavior, explicit counts, advancing pagination,
  nonadvancing/fetch failure data preservation, replace/fsync/snapshot/archive/current-manifest
  failure states, external singleton locking, empty-table snapshotting/recovery across status and
  later-file crashes, corrupted/missing/conflicting embedded cursor refusal, and immutable status
  lineage. This source/test edit ran no live refresh or one-time data repair and did not alter
  existing generated dataset dirt.

## v8.130 — 2026-07-22 — Operating-plan and handoff reconciliation

- Reconciled the autonomous operations plan with commits `30884dc` and `c320ec2`: external-trust
  setup and pending activation-authority source contracts are implemented and independently
  reviewed, while external activation remains incomplete and every represented authority remains
  `NONE`.
- Updated the session handoff to the v8.129 implementation track with `c320ec2` as its
  pre-documentation-reconciliation baseline, retained the protected v8.127 / D-115 SSOT boundary,
  recorded the **1,525 passed / 29 deselected** release gate and live service observations, and
  preserved the reviewed bundle/installer digests.
- Recorded the exact remaining sequence: operator root installation, read-only verification,
  genuine independent-reviewer enrollment, separately reviewed trust/policy/genesis/history/
  checkpoint/time publication, canonical activation receipt production and
  `ACTIVE_NO_DECISIONS` snapshot validation, retention of an independently signed review record
  binding installed hashes/state/receipt, fixed-path typed evidence resolution/current-receipt
  consumption, operator-authorized integrity freeze, and only then Phase 3 followed by Phase 4.
  Source preparation does not satisfy or bypass any gate.
- This is a documentation-only reconciliation. It edits no immutable, protected, or
  manifest-listed file, changes no research protocol or outcome evidence, and grants no intake,
  strategy, campaign, venue, order, live, or real-money authority.

## v8.129 — 2026-07-22 — Pending-only activation-authority source contracts

- Added strict canonical `AuthorityGenesis`, domain-separated access/data/operator evidence,
  generic monotonic-head, and activation-status contracts. Receipts are closed to
  `ACTIVE_NO_DECISIONS` or explicit `BLOCKED`, bind exact genesis/head/policy/trust digests, and
  retain `execution_authority=NONE`. Cross-record validation accepts only an active receipt,
  requires the exact `INTAKE-ACTIVATION-AUTHORITY` genesis stream, exact supplied bindings, the
  ordered genesis/head/receipt/observation time chain, and an unexpired receipt; it performs no
  persistence or admission.
- Added a deterministic content-addressed activation **source** bundle, canonical policy, and a
  bounded native Swift syntax validator. The reserved `activate.sh` surface is planning/status
  only; activate/init/install commands are absent and fail closed. No source here uses `sudo`,
  creates root state, signs evidence, mutates history, admits a decision, or reaches a strategy,
  campaign, venue, order, live, or real-money path.
- Documented the future trusted-time model: root-owned OS wall clock plus a persisted
  nondecreasing last observation, with refusal on rollback, excessive unexplained forward jumps,
  expiry, unsafe state, or ambiguity. A malicious root/operator is explicitly outside this local
  threat model and requires separate external transparency or hardware-backed assurance.
- Added negative contract, domain-substitution, monotonicity, binding, expiry, command-surface,
  blocked-receipt, stream/time inversion, deterministic-bundle, symlink/hardlink, private-output,
  metacharacter-path JSON, bounded-input, differential token grammar, canonical Swift/Python, and
  status/blocker tests. The builder revalidates source/copy bytes and types around copying and
  verifies no-clobber publication in caller-owned `0700` output, while explicitly excluding root
  and malicious same-user races from its guarantees. This release installs, initializes,
  activates, and authorizes nothing. All new implementation and test paths plus this changelog are
  nonmanifest; no immutable or manifest-listed file changed.

## v8.128 — 2026-07-22 — External intake trust setup source only

- Added strict, immutable, exact-key external trust contracts for reviewer public credentials,
  trust snapshots, typed evidence envelopes, append-only history bindings, monotonic checkpoints,
  and assessment receipts. Canonical UTF-8 JSON and distinct signing domains reject duplicate
  keys, unknown fields, floats/non-finite numbers, control characters, and substitutions. The
  receipt vocabulary stops at `VERIFIED_PENDING_EXTERNAL_ACTIVATION` or explicit failure/block
  states and always retains `execution_authority=NONE`.
- Added an auditable native Swift signature-verifier source and deterministic content-addressed
  directory-bundle builder. The staged root-owned installer compiles only re-hashed staged source
  with fixed `/usr/bin/swiftc` and atomically publishes a complete fixed helper directory under
  `/Library/PrivilegedHelperTools`. The helper has only read-only status and cryptographic
  decision-signature verification via fixed `/usr/bin/ssh-keygen`; success is explicitly
  `SIGNATURE_VERIFIED_SEMANTICS_UNVERIFIED`, not a semantic assessment or activation state.
- Added public-only reviewer enrollment guidance/example plus focused contract, Python/Swift
  canonical-vector, compiler, source-surface, bundle determinism, staging-digest, drift, and
  refusal tests. Production/enrollment code generates, prints, and stores no private key.
  Behavioral verification creates only ephemeral unencrypted test keys inside a temporary test
  directory; they are never retained or used outside the isolated test.
- This release adds setup source only. Nothing was installed, initialized, enrolled, signed,
  activated, or granted intake, strategy, campaign, venue, order, live, or real-money authority.
  All new implementation/test paths and this changelog are nonmanifest; no immutable or
  manifest-listed file was changed.

## v8.127 — 2026-07-22 — Operator-authorized integrity and current-state reconciliation

- `DECISION_LOG.md`: added unique D-115, recording the one-time manifest-edit exception and its
  strict scope, while retaining `PACKAGE_INTEGRITY_MANIFEST.md` in `IMMUTABLE_PATHS`. D-115 also
  selects a root-owned-outside-repository trust boundary for the installed external verifier/
  helper, private keys and trust credentials, authoritative append-only decision history, and
  monotonic checkpoint. Repository source/setup and public metadata remain permissible in-repo.
  Independent reviewer setup and the remaining activation evidence are still pending; no
  admission, promotion, production venue, live-order, or real-money authority is created.
- `PROJECT_STATE.md`: reconciled the package/date/current status and OPEN ITEMS. The dashboard,
  orchestrator, protected `real_money=false` demo lane, and jobs worker are alive; legacy
  closed-family research jobs are quarantined and their execution surface is retired. Phases 1,
  2, 2b, and 5 are implemented within their fail-closed scopes; Phases 3 and 4 remain blocked on
  actual external activation evidence and independent review. Removed the stale urgent
  demo-stopped/unprotected wording.
- `handoffs/SESSION_HANDOFF_2026_07_22.md`: reconciled the durable handoff to v8.127/D-115,
  current service and phase state, the root-owned trust selection, and the remaining blockers.
- `PACKAGE_INTEGRITY_MANIFEST.md`: under the explicit D-115 one-time exception and its narrow
  operator-authorized extension, changed only the package-version line, the existing
  `PROJECT_STATE.md` and `DECISION_LOG.md` hash rows, and the malformed existing
  `src/tios/services/observations/__init__.py` row. That source file was unchanged; its stored
  digest had one extra trailing `f`, causing the former strict regex verifier to silently skip the
  row. No rows or immutable paths were added or removed; all **453 table rows / 438 unique paths**
  were reverified, including duplicate path occurrences.
- `tests/test_package_integrity_manifest_shape.py` (new, not manifest-listed): broadly parses every
  Markdown Path/SHA row, requires every digest to be exactly 64 lowercase hexadecimal characters,
  proves the strict verifier sees the same total row count, and verifies every referenced file
  hash without deduplicating rows. This closes the malformed-row silent-skip gap.
- Verification: focused decision-ID and package-integrity checks passed; the final `make check`
  post-repair invocation passed with **1,468 passed / 29 deselected**, plus ruff, format, mypy-strict, secret
  scan, and package integrity.

## v8.126 — 2026-07-22 — Closed-family legacy execution guard

- `src/tios/services/jobs/runner.py` and `scripts/run_research_lab_v0.py`: enforce one fixed
  D-079/D-112 closure reason before the legacy `RESEARCH_LAB_V0` worker handler, command
  construction, subprocess creation, hashing, evaluation, or output creation. Injected retained
  queue rows terminate as `CANCELLED` without retry; historical artifact verification remains
  readable.
- `scripts/run_job_worker.py`: remove the retired enqueue surface while preserving queue history,
  status, cancellation, and worker commands.
- `tests/test_jobs.py` and `tests/test_research_lab_v0.py`: cover the terminal worker guard,
  independent direct-entry guard, absent CLI launch surface, and retained historical artifact
  compatibility. These source and test paths are not manifest-listed, so no manifest rehash is
  required.

## v8.125 — 2026-07-22 — Fixed-purpose legacy research-jobs quarantine capability

- `src/tios/services/jobs/store.py`: added a byte-read-only, content-hashed plan and an atomic
  apply API for quarantining only the reviewed
  `s2-production-offline-research-lab-v0-every-6h-v1` schedule and its exact queued
  `RESEARCH_LAB_V0` job IDs. The operation validates v2/v3 schema agreement and fixed schedule
  metadata, refuses drift, extra research schedules, running jobs, or stale plan/ID approvals,
  migrates v2 and disables the schedule in one transaction, preserves terminal evidence and
  unrelated work, and migrates the jobs database to schema v4, whose numbered migration creates
  the exact durable single-row audit-outbox schema. The exact canonical audit bytes and a
  digest-derived temporary filename are stored in that outbox in the same transaction. Normal
  initialization upgrades v2/v3 to v4 transactionally; the read-only projection continues to
  support the explicit reviewed set v2/v3/v4. The plan SHA binds SQLite-type-tagged full-row
  fingerprints for every research
  job and schedule, explicit terminal evidence, and full aggregate digests for all non-target
  jobs and schedules, so same-ID or non-target material changes invalidate stale approval. Audit
  publication uses descriptor-anchored, no-symlink directory traversal, a unique fsynced temporary
  file, atomic no-replace publication, inode/link/content verification, and directory fsync. A
  post-commit crash leaves the outbox repairable after restart. Repair recovers both deterministic
  link windows (exact temp before link, or exact final+temp hardlinks before temp unlink) while
  refusing corrupted or mismatched orphans. Publication acknowledgement is retained in the
  database, and `ALREADY_QUARANTINED` verifies or repairs pending publication instead of masking
  it. Existing v4 databases are accepted only when their complete persistent `sqlite_master`
  object signature matches the numbered migrations (including expected autoindexes and the exact
  jobs-identity trigger); unexpected triggers, views, indexes, or modified definitions fail
  closed. The durable audit retains historical post-quarantine full-table digests as apply
  evidence and checks them immediately after outbox insertion. It separately retains immutable
  post-quarantine research-job fingerprints and the disabled target-schedule fingerprint for
  restart repair and later verification. Publication acknowledgement compares the current full
  jobs/schedules digests immediately before and after its local update, catching trigger side
  effects without incorrectly freezing unrelated jobs or schedules that legitimately evolve
  between apply and repair.
- `scripts/quarantine_legacy_research_lab_v0.py` (new): fixed `plan`/`apply` operator interface;
  plus a fixed `repair-audit` action requiring the exact audit and plan digests. It intentionally
  exposes no database path, job type, schedule, payload, SQL, command, or artifact-path selector.
  This release adds the capability only; it does **not** apply it to the live jobs database.
- `tests/test_legacy_jobs_quarantine.py` (new): temp-database coverage for v2/v3, migration
  rollback, read-only planning, exact fresh/retry cancellation, evidence preservation, refusal
  cases, full-state plan invalidation, races, idempotency, durable crash/restart audit repair,
  partial-file collisions, deterministic pre-link and post-link crash recovery, corrupted orphan
  collisions, parent swaps/symlinks, final symlinks/hardlinks, SQLite TEXT/BLOB distinction, and
  malicious outbox INSERT/UPDATE triggers plus unexpected views/indexes, and the constrained CLI
  surface. Liveness regressions verify that pending/published audits tolerate legitimate
  non-research job and schedule evolution while quarantined research or target-schedule mutations
  still refuse repair. `tests/test_jobs.py` also verifies migration/concurrent-init v4;
  `src/tios/services/jobs/projection.py` preserves explicit v2/v3/v4 read-only compatibility.
- None of the five implementation/test paths is listed in `PACKAGE_INTEGRITY_MANIFEST.md`, so no
  manifest row was changed.

## v8.124 — 2026-07-21 — New-family pre-registration go/no-go resolved NO-GO (D-114)

- `DECISION_LOG.md`: D-114 records the delegated pre-registration go/no-go for
  `docs/supervisor/NEW_FAMILY_SCOUTING_2026-07-21.md`'s shortlist. An evidence review found the
  scouting doc's top candidate (cointegrated stat-arb baskets) already refuted by
  `artifacts/validation/stat_arb_pro/STAT_ARB_PRO.json` (2026-07-12: Engle-Granger-gated
  stat-arb, 5/10 pairs cointegrated in-sample incl. ETH/BTC and BNB/BTC, all top OOS configs
  negative, DSR 0.0039 vs 0.95, root cause "cointegration decay" — invariant to basket
  cardinality) and its second candidate (cross-sectional altcoin momentum) weakened by the
  project's own recorded result (DSR 0.9456 at 28 pairs degrading to 0.9091 at 34) plus the
  SUP-009 survivorship gap. Outcome: **no new family pre-registration this cycle; no
  search/trial-budget slot spent.** The operator retains a governance override to pre-register a
  multivariate Johansen-basket variant notwithstanding this evidence, though it is recorded as
  recommended against.
- `docs/supervisor/NEW_FAMILY_SCOUTING_2026-07-21.md`: dated ADDENDUM appended (original content
  unchanged) noting the missed refutation/weakening above and pointing to D-114 for the
  authoritative outcome.
- `PROJECT_STATE.md`: OPEN ITEMS — the awaiting-decision line for pre-registration go/no-go
  replaced with the D-114 resolved outcome under "Resolved this cycle".
- `PACKAGE_INTEGRITY_MANIFEST.md`: rehashed listed rows for `DECISION_LOG.md` and
  `PROJECT_STATE.md`; version line bumped to v8.124. The scouting doc and changelog are not
  manifest-listed.

## v8.123 — 2026-07-21 — Evaluator differential test, orchestrator dashboard view, demo disaster-stop, scouting doc, operator decisions (D-113)

- `scripts/run_evaluator_differential_test.py` (new), `tests/test_evaluator_differential.py`
  (new): cross-checks the campaign evaluator (`score_trade_significance` +
  `run_first_budgeted_campaign.py::evaluate`) against an independent from-spec implementation
  on synthetic data with hand-derivable ground truth — the D-112 audit's residual
  single-implementation-risk follow-up. Result recorded at
  `artifacts/validation/EVALUATOR_DIFFERENTIAL_TEST_2026_07_21.json`: **verdict AGREEMENT**
  (vectorbt cross-check skipped, not importable in this env). Closes the D-112 remediation
  plan's "Pending, not blocking" differential-test item; no threshold or verdict changes.
- `docs/supervisor/NEW_FAMILY_SCOUTING_2026-07-21.md` (new): hypothesis-only survey of
  community strategy libraries for new strategy families. Top-3 shortlist: cointegrated
  stat-arb baskets, cross-sectional altcoin momentum, cross-sectional funding carry. Ideas
  only — no evidence, no pre-registration; `research/SOURCE_REGISTRY.md` gained the
  corresponding scouting sources.
- `scripts/demo_eth_lane.py`, `tests/test_demo_disaster_stop.py` (new),
  `tests/test_demo_eth_lane.py`: demo-lane −15% disaster-stop (`DEMO_DISASTER_STOP_PCT`)
  backed by a Bybit V5 venue-resting stop order, so the stop survives even if the lane
  process is down. Approved and implemented under D-113.
- `src/tios/services/dashboard_api/orchestrator_view.py`: `JOURNAL_TAIL` raised 20 → 100
  (~25h of 15-min cycles) for a more useful operator history view.
  `src/tios/services/dashboard_ui/dashboard.html`, `tests/test_dashboard.py`: orchestrator
  dashboard view enhanced to match, with new/updated test coverage.
- `DECISION_LOG.md`: D-113 records five operator decisions from the 2026-07-21 (evening)
  session — security-test sign-off approved, new-family scouting approved as
  hypothesis-sourcing only, demo-lane disaster-stop approved, v8.119–v8.122 tree commit
  (`0b183ea`) approved, and four items (operator attestation, D-099 review, SUP-009, SUP-006a)
  deferred.
- `artifacts/driver/parked_items.jsonl`: the `test_live_unreachable.py` stale-security-test
  parked item is closed — operator sign-off obtained 2026-07-21 (D-113).
- `PROJECT_STATE.md`: OPEN ITEMS updated — security sign-off resolved, scouting's
  awaiting-decision line replaced with the pre-registration go/no-go, demo-lane stop moved
  to implemented/awaiting lane-restart verification, differential-test item removed from
  Pending. Header bumped to v8.123.
- `docs/supervisor/STATISTICAL_REMEDIATION_PLAN_D112_2026-07-21.md`: the two `[OPERATOR]`
  follow-ups and the differential-test `[PENDING]` item marked `[DONE]` with their outcomes.
- `PACKAGE_INTEGRITY_MANIFEST.md`: rehashed listed rows for `dashboard.html` (×2),
  `test_dashboard.py` (×2), `DECISION_LOG.md`, and `PROJECT_STATE.md`; version line bumped to
  v8.123. `orchestrator_view.py`, `research/SOURCE_REGISTRY.md`, the D-112 remediation plan
  doc, and `parked_items.jsonl` are not manifest-listed, so no rehash needed for those.

## v8.122 — 2026-07-21 — TODO-page session-prompt copy button

- `src/tios/services/dashboard_ui/dashboard.html`: added a "Copy session prompt" button to the
  TODO/tasks page (`#todos` title-row), a `SESSION_KICKOFF_PROMPT` constant, and a
  `copySessionPrompt()` handler (navigator.clipboard.writeText, with a
  document.execCommand('copy') hidden-textarea fallback) that flips the button text to
  "Copied ✓" for ~2s. The prompt text is a generic, version-agnostic orchestrator
  session-kickoff pointing the reader at `PROJECT_STATE.md` as the live authority — no
  hardcoded version numbers or dates, so it never goes stale. No new dependency, no server
  restart required (static asset served from the existing dashboard HTML).
- `tests/test_dashboard.py`: added `test_todos_page_has_copy_session_prompt_button`, asserting
  the button markup and stable prompt substrings (structural property, not the whole blob).
- `PACKAGE_INTEGRITY_MANIFEST.md`: rehashed both listed rows for
  `src/tios/services/dashboard_ui/dashboard.html` and `tests/test_dashboard.py` (each appears
  twice, in the "Required handoff inputs — operational core" and "Managed observation
  implementation freeze (added v8.100)" sections) per the D-030 regeneration rule; version
  line bumped to "v8.122 TODO-page session-prompt copy button (2026-07-21)".

## v8.121 — 2026-07-21 — Documentation consolidation: one current entry point

- `PROJECT_STATE.md` was content-stale (predated D-107..D-112) despite being the repo's
  declared current-state authority. Rewrote it to the true 2026-07-21 state: 24/7
  orchestrator running (restarted after D-112 close-out found it stopped), all 7 searchable
  strategy families searched with 0 passes (4 FAIL, 3 INSUFFICIENT_ACTIVITY), the CFTC
  PASS-ELIGIBLE retracted under D-112, corrected trade-level scoring in force, two
  prospective observation lanes (MVRV, CFTC) live and automated, demo lane armed, gate green
  at 1146 tests. Added a new "OPEN ITEMS — the only live task list" section consolidating
  every open item (operator decisions, parked SUP-009/SUP-006/D-099 blockers, pending
  differential-testing work, structurally gated tasks) with one-line status + pointer to its
  detailed home, replacing the previous scatter across `MISSING_AND_OPEN_ITEMS.md`,
  the remediation plan, and `parked_items.jsonl`.
- `MISSING_AND_OPEN_ITEMS.md`: re-verified SUP-009/SUP-006 against `DECISION_LOG.md`
  D-107..D-112 (both remain genuinely open; no decision in that range closes either — D-108
  only adds the forward-looking mechanism, it does not recover the historical gaps).
  Cross-linked both to their `artifacts/driver/parked_items.jsonl` phases. Added a header
  line pointing back to `PROJECT_STATE.md` as the consolidated entry point.
- Archived two self-labeled quarantined/historical `docs/program/` documents into
  `docs/archive/` per the existing convention (git mv + one row each in
  `docs/archive/README.md`'s table, "File | Was | Superseded by"): `AGENT_NOTES_TO_OPERATOR.md`
  (2026-07-12 session note, already self-labeled superseded by the 2026-07-13 supervisor
  correction) and `DEMO_LANE_PLAN.md` (pre-D-046 design note, already self-labeled
  QUARANTINED). Neither is manifest-listed, so no manifest change from the move itself.
  Updated `docs/archive/README.md`'s "live authorities" declaration to
  `DECISION_LOG.md` (through D-112), `PROJECT_STATE.md` (2026-07-21), `TODO.md` + `todos/`,
  and `AD.md` for architecture; the parallel session's existing archive rows are untouched.
- The 2026-07-13 `docs/supervisor/` trio (`SUPERVISORY_BASELINE`, `IMPROVEMENT_PLAN`,
  `FINAL_SUPERVISORY_REPORT`) is manifest-listed and stale but not archived — each now
  carries a one-line banner: "> SUPERSEDED (2026-07-21): see docs/supervisor/*_2026-07-21.md
  and PROJECT_STATE.md." Their `PACKAGE_INTEGRITY_MANIFEST.md` rows were rehashed in the
  same change per the D-030 regeneration rule.
- `PACKAGE_README.md` (non-manifest-listed): the stale "ready for constrained coding-agent
  prototype execution" orientation line now points at `PROJECT_STATE.md` as the live
  current-state entry point.
- `PACKAGE_INTEGRITY_MANIFEST.md`: rehashed rows for `PROJECT_STATE.md`,
  `MISSING_AND_OPEN_ITEMS.md`, and the three 07-13 supervisor docs (the only manifest-listed
  files edited this change); version line bumped to "v8.121 documentation consolidation
  (2026-07-21). Supersedes v8.120 hashes." Full manifest sweep verified zero other mismatches.
  The four `docs/supervisor/*_2026-07-21.md` planning-thread documents, `handoffs/
  SESSION_HANDOFF_2026_07_21.md`, and `artifacts/driver/parked_items.jsonl` were read for
  content and integrated by reference only — not edited, not manifest-listed.

## v8.120 — 2026-07-21 — Methodology audit: trade-level significance fix; CFTC PASS-ELIGIBLE retracted (D-112)

- An independent Opus red-team audit of the validation scoring core, confirmed by a bit-for-bit
  verification recompute, found the DSR verdict on `src/tios/validation/campaign.py::run_campaign`
  was computed on a `sample_count` (total validation bars) inconsistent with the series it scored
  (in-position bars only). For FAM-CFTC-POSITIONING-V1 the recorded PASS-ELIGIBLE (DSR 0.9996,
  z 3.3208) rested on 169 in-position bars of 7,630 (2.21%) and exactly one completed validation
  trade; under the corrected trade-level count it is INSUFFICIENT_ACTIVITY, not a pass. Reproduced
  train 0.024257871728695 and validation 0.077151674981046 exactly.
- Fixed `campaign.py`: significance is now built on per-completed-trade returns with
  `sample_count == len(trade returns)`, enforced by a fail-closed invariant in the new shared
  `score_trade_significance()` helper (F1/F2); a pre-registered `min_validation_trades` floor
  (default 10) yields a distinct `INSUFFICIENT_ACTIVITY` outcome rather than a claimed DSR, and
  `n<2` never attempts a Sharpe (F5); `pbo_max` is removed from the campaign thresholds/schema and
  the module docstring records that PBO is not computed on this path — a declared-but-unenforced
  control is worse than an honestly absent one (F3a); `independent_trials` now routes through
  `implied_independent_trials`, haircutting the still-hierarchy-wide trial count for cross-trial
  correlation (F3b); the dead nested-fold scoring (`walk_forward_folds`/`fold_scores`, never fed
  anything) is deleted (F4); and the DSR-path Sharpe uses sample variance ÷n-1, consistent with
  `sharpe_variance_from_trials` (F6). Evaluators now return a `TrialScore` (score + trade returns
  + aligned bar returns); a bare-float return remains accepted as a legacy opaque-score path.
- Updated the six affected evaluators to expose trade returns:
  `scripts/run_family_campaigns_v3.py` (period-z, hourly-z, funding),
  `scripts/run_family_campaigns_v2.py` (taker, mvrv), and
  `scripts/run_first_budgeted_campaign.py` (vol-contraction). Descriptive per-bar Sharpe (used for
  train selection) is unchanged, so frozen selections reproduce bit-for-bit.
- Added `scripts/rescore_frozen_campaigns.py`: replays ONLY the seven recorded frozen selections on
  their original train/validation windows under the corrected scoring — no `preregister`/`record_trial`,
  no ledger writes, no holdout access, no parameter search. Correction artifacts written to
  `artifacts/validation/campaigns/corrections/<PREREG-id>_corrected.json`. Result: CFTC
  PASS-ELIGIBLE → **RETRACTED (INSUFFICIENT_ACTIVITY, 1 trade)**; the six others stand as
  FAIL/INSUFFICIENT_ACTIVITY (TX FAIL z −2.36, cross-venue FAIL DSR 0.48, taker FAIL z −2.35, MVRV
  FAIL DSR 0.46, funding INSUFFICIENT 0 trades, vol-contraction INSUFFICIENT 7 trades). No family
  flips toward a pass. Vol-contraction's `normalized_multi` input has drifted under a parallel
  session; re-scored on committed (HEAD) data with the non-reproduction recorded transparently, the
  FAIL (z −14.2) being invariant to the drift.
- Regression tests added to `tests/test_campaign.py`: the sample-count invariant fails closed when
  count and series length diverge (the F1 shape); zero/one-trade validation is INSUFFICIENT_ACTIVITY
  and never claims a DSR; the correlation haircut shrinks the effective trial count below the raw
  hierarchy count. Structural properties only, no pinned floats/IDs.
- `D-112` recorded in `DECISION_LOG.md` with the findings, verification numbers, the formal
  retraction, the corrected methodology, and the note that both prospective lanes continue unchanged
  (their 2027 first reviews must apply the corrected statistics; the CFTC lane is now
  hypothesis-generating, not confirmation).
- `src/tios/validation/multiple_testing.py` needed no change: its `sharpe_variance_from_trials` is
  already sample variance (÷n-1) and `implied_independent_trials` already existed — the fix was to
  wire them correctly from the caller.
- Integrity check: none of this session's changed files (`campaign.py`, the three campaign scripts,
  the new re-score script, `tests/test_campaign.py`, this changelog, the decision log, the handoff)
  are listed in `PACKAGE_INTEGRITY_MANIFEST.md` — verified by grep. No rehash required. No
  trial-ledger writes; holdout unread.
- Correction: `DECISION_LOG.md` **is** a manifest-listed file (required handoff inputs — operational
  core). The D-112 entry above was appended to it after that check, so its recorded SHA-256 in
  `PACKAGE_INTEGRITY_MANIFEST.md` went stale, tripping `make check`'s package-integrity gate. Per the
  D-030 regeneration rule (logged, changelog-recorded edit → regenerate the manifest in the same
  change, don't fork the file), `PACKAGE_INTEGRITY_MANIFEST.md` row for `DECISION_LOG.md` was
  recomputed and the "Package version" line bumped to v8.120; no other manifest-listed file
  mismatched its recorded hash.
- Documented both of today's changes in `docs/architecture/AD.md`: a note in §S on why the
  v8.119 prospective observers run from the orchestrator rather than the network-isolated `jobs`
  module, two new decision-register rows (AD-16, AD-17), and a new §AM section with a mermaid
  diagram covering the prospective-observation flow and the corrected trade-level validation
  path. `docs/architecture/AD.md` **is** a manifest-listed file (planning-system handoff inputs);
  per the same D-030 regeneration rule, its `PACKAGE_INTEGRITY_MANIFEST.md` row was recomputed
  in this change. No other manifest-listed file was touched by this edit.

## v8.119 — 2026-07-21 — CFTC prospective observer built; both lanes wired into orchestrator

- Built `scripts/run_prospective_cftc_observer.py`, the CFTC weekly prospective fetcher
  flagged NOT_YET_BUILT in v8.118 (Socrata dataset `6dca-aqww`, BTC/CME code 133741,
  keyless). Live-run verified exit 0; first row recorded in
  `artifacts/prospective/CFTC-POSITIONING-V1/observations.jsonl` (report 2026-07-07,
  z +1.94, FLAT; `prospective=false` since this report predates the prereg freeze date —
  the first prospective report, 2026-07-14, becomes available 2026-07-22T00:00Z per the
  spec's 8-day availability lag). `research/PROSPECTIVE_CFTC_POSITIONING_V1.yaml`
  `observation_protocol.observer_status` updated NOT_YET_BUILT → BUILT.
- Wired both prospective lanes (MVRV daily + CFTC weekly) into
  `src/tios/ops/orchestrator.py` via a new `observe_prospective_observers()` step: runs
  each observer script via subprocess at most once per UTC day per lane (marker file
  `artifacts/prospective/<lane>/.last_orchestrated_utc_day`); a failing, timed-out, or
  missing script produces an ACT observation without halting the cycle. Wired into
  `observe()`/`run_cycle()` with defaults, so `scripts/run_orchestrator.py --loop` picks
  it up unchanged. `tests/test_orchestrator.py` gained 6 structural tests (16 pass in that
  file). Closes open items 1 and 2 from `handoffs/SESSION_HANDOFF_2026_07_21.md`.
- A jobs-runner route for the CFTC fetch was considered and rejected: the jobs runner is
  network-isolated by design, and the fetch needs a live outbound call to Socrata.
- Integrity check: none of this session's changed files (the new observer script, the
  YAML spec, the orchestrator module, the orchestrator test file, this changelog) are
  listed in `PACKAGE_INTEGRITY_MANIFEST.md` — verified by grep. No rehash required.

## v8.118 — 2026-07-21 — Campaigns #4–#7 + prospective lanes (D-111)

- Ran the four remaining pre-registered budgeted campaigns (`scripts/run_family_campaigns_v3.py`)
  on frozen in-repo data, each availability lag enforced at data-join time. TX activity: FAIL
  (overfit signature). Cross-venue premium: FAIL (negative in-sample). Funding pressure: FAIL
  (largest in-sample score, zero validation trades — regime-mined artifact). CFTC positioning:
  first PASS-ELIGIBLE — DSR 0.9996 vs 0.95 after deflating against 216 hierarchy trials
  (train +0.024, validation +0.077, LOW side 26w/z1.5/168h hold). No authority created.
- Opened two D-103-style prospective observation lanes with boundaries frozen today:
  MVRV dislocation (prereg + live observer, first honest row recorded from public
  CoinMetrics data) and CFTC positioning (prereg; weekly fetcher flagged NOT_YET_BUILT,
  no evidence lost before the next report's availability date).
- Hierarchy ledger: 234 trials across 7 admitted families. The in-repo searchable family
  backlog is exhausted; forward paths are prospective evidence, lawful holdout reads after
  2027-01-14, or new families backed by new data.
- Manifest regeneration also picked up hash drift from a parallel session's edits
  (`scripts/verify_*.py` data verifiers, `src/tios/trading_domain/__init__.py`) that had
  missed their regeneration step; fixed per the D-030 rule rather than forked.

## v8.117 — 2026-07-21 — Campaigns #2 and #3 (D-110)

- Ran two further pre-registered budgeted campaigns on frozen in-repo data. Taker imbalance:
  decisive FAIL (best-of-36 negative even in-sample). MVRV dislocation: FAIL at the 0.95 DSR
  threshold but the first promising negative — validation (+0.055) exceeded training
  (+0.045), no overfitting signature, DSR 0.76 after deflating against 108 hierarchy-wide
  trials. Both families closed without rescue per frozen stop rules.
- MVRV publication lag enforced structurally: hourly rows carry only the daily value already
  released under the spec's D+3 availability rule.
- Hierarchy ledger: 108 trials across 3 admitted families; every future campaign deflates
  against all of them.

## v8.116 — 2026-07-21 — Completable-task closeout

- T-017-05 DONE: AI cost-intelligence view at Operations → Data health (`/api/v1/ai-costs`)
  — totals and per-model runs/calls/cost from the real ledger, blocked configs surfaced,
  zero-call rows excluded from spend, no credential read.
- T-015-03: divergence summary projected into the demo-lane payload and card, with an
  explicit staleness flag when fills postdate the last report.
- T-015-04: measurement-mode kill-switch drill executed on the live lane (engage → orders
  blocked → clear → clean resume; position and order count unchanged). Evidence:
  `artifacts/trading_domain/demo_lane/DRILL_2026_07_21.json`. Full paper drills stay S3.
- T-018-04: delta security review of the new surface (real-provider callers, selective .env
  loading, projections, drill) — no new findings; still honestly non-independent.

## v8.115 — 2026-07-21 — T-011-05 first real AI benchmark runs (Mode A)

- Built the real-provider layer (raw urllib, dependency-free, provider-neutral): Anthropic
  Messages API + OpenAI Chat Completions, identical frozen prompt and schema instruction per
  task (Mode A), pinned pricing recorded per record, bounded retry on 429/500/529, and a
  one-probe quota abort so a dead account fails once instead of 54 times.
- Ran the frozen 27-fixture corpus, 2 samples per configuration: claude-opus-4-8 (100%
  schema-valid, 70.4% output stability, $0.27) and claude-haiku-4-5 (100% schema-valid,
  55.6% stability, $0.049 — 5.5x cheaper, 42% faster, measurably less stable). openai:gpt-4o
  recorded as honestly BLOCKED: key authenticates, account quota exhausted. Total $0.32.
- T-011-05 DONE (variance per AD-11; judge evaluators still PENDING_HUMAN_REVIEW). T-017-05
  cost ledger now LIVE with real rows; the dashboard cost view remains open.

## v8.114 — 2026-07-21 — T-015-03 measurement mode: first divergence evidence

- Built the D-104 step-3 divergence report: each lane fill vs the frozen backtest's
  next-bar-open expectation, signed adverse-positive, with timing lag and fee drag.
  Public kline GET only; no credential. First measured fill: -1.45 bps price divergence
  (favorable), 958s lag after bar close, 10 bps fee — inside the F1/S1 cost envelope.
- T-015-03 marked MEASUREMENT MODE ACTIVE; full paper-lane divergence stays DEFERRED-S3.

## v8.113 — 2026-07-20 — Demo wallet redesign: time windows and positions

- Rebuilt the demo screen to wallet-app conventions: header (venue logo, account type,
  wallet value with as-of), a Performance block with 1D/1W/1M/All tabs (net realised P/L
  in $ and % of spent, positions opened/closed, win rate, volume, fees), and a Positions
  table (coin, entry/exit, TP steps, SL steps, strategy, timeframe, expected vs actual
  hold, spent, P/L in $ and %). Order history collapses below as the audit trail.
- Positions are derived from fills, never stored, so they cannot disagree with the ledger.
  Window P/L counts realised results only, attributed to the close window — unrealised
  P/L stays on the open position so window numbers do not drift with price.
- Expected trade time is measured, not guessed: median 65-bar hold over 259 historical
  trades of this rule. TP/SL render as step lists (currently none) so laddered strategies
  fit without restructuring.

## v8.112 — 2026-07-20 — Demo lane money, rules, and account panel

- Demo lane now reports money: per-order spent/received taken from reconciled venue wallet
  deltas, wallet totals, average cost, position value, and realised/unrealised P&L in USD
  and percent. An unmarked position reports null rather than zero so open risk is not
  understated as flat.
- Lane captures a wallet snapshot and mark price every cycle (not only on fills) and
  publishes live Donchian/volume rule levels; the dashboard still holds no credential.
- Reorganised the demo screen into Account (Bybit logo, UNIFIED, DEMO), Position & money,
  Exit rules & risk, and Activity. Stop loss and take profit are stated as explicitly NONE
  with the rule-driven exit band shown in their place — the spec sets both to null.
- Fixed a fragile test fake: FakeVenue balances were a canned call-indexed sequence, so any
  change in wallet-query count silently zeroed the reconciliation delta. Now modelled as
  state mutated by fills.

## v8.111 — 2026-07-20 — Open-work view and first budgeted campaign (D-109)

- Added `GET /api/v1/open-work` and an Overview "Open work" card merging the task registry,
  the parked ledger, and orchestrator escalations, classified by who can act:
  requires_operator / agent_executable / blocked_external / recurring. The registry alone
  reported zero open tasks while the live work sat in the parked ledger.
- Ran the first campaign end to end through the substrate on 48,614 real BTCUSDT 1h bars.
  `FAM-VOL-CONTRACTION-BREAKOUT-V1` rejected: train Sharpe +0.0411, validation -0.0807,
  DSR 0.000 against a hierarchy-wide 36-trial noise threshold. Holdout never touched.
- Marked two parked items resolved; tightened open-work operator classification so a cause
  that merely mentions the operator no longer routes to them.

## v8.110 — 2026-07-20 — Plan-doc archive and index reconciliation

- Archived finished plans and superseded handoffs to `docs/archive/` (EXECUTION_PLAN.md,
  three CONTINUE handoffs, HANDOFF_SIMULATION_AUDIT_V1.md) with an index README; live
  authorities are DECISION_LOG.md and PROJECT_STATE.md.
- Reconciled TODO.md's execution-order section and RESEARCH_BACKLOG.md's status header to
  the D-107/D-108 state; `todos/NN_*.md` retained unchanged as the dashboard-parsed task
  registry. Fixed the two stale pointers in README-dev.md and PACKAGE_README.md.
- Includes the D-108 changes from this cycle: hierarchy-wide family budget (family
  admission delegated to the orchestrator) and the split gate (`make check` ~1:30 code-only
  at schema 3, `make check-full` backs `make required`).

## v8.108 — 2026-07-20 — Autonomous orchestration substrate (D-107)

- Added a global trial budget with mandatory pre-registration; declared trial counts are now
  verified against a persistent ledger instead of trusted, and unregistered searches cannot be
  scored. Wired into strategy eligibility as a fail-closed blocker.
- Added an expiring operator attestation carrying the ten human-only facts, enforced by
  predicate; it holds no credentials and never escalates a demo scope into live authority.
- Added self-modification bounds: branch, gate, auto-revert, and an immutable-path guard that
  runs before the gate. `Makefile` is immutable to the orchestrator because it defines the gate.
- Wired D-100's evidence-producer map to a driver that walks it, with verifiers allowlisted to
  project scripts, path-traversal rejected, and declared prohibitions withholding all dispatch.
- Added the 24/7 orchestrator (`make orchestrator`) and a read-only Operations → Orchestrator
  dashboard view. It halts on escalation, holds no credential, and places no order.
- Closed SUP-008 structurally (holdout leakage now impossible, not merely forbidden), SUP-010
  for coverage (all 20 canonical specs hold immutable version identities), and the achievable
  half of SUP-007 (artifact staleness detection; all six G10 artifacts verify CURRENT).
- Fixed two pre-existing gate failures inherited from the previous session's uncommitted work:
  ruff/mypy errors in the signal pollers, and two stale tests encoding realities that D-104
  had already changed. The security assertion was replaced with a stronger, mutation-tested one.
- Regenerated controlled-file hashes for twelve drifted paths; package integrity was already
  failing on arrival for `skills/README.md` and `todos/15_paper_trading.md`.
- No credential, venue, order, paper, demo, or live authority is created. The sealed holdout
  remains sealed.

## v8.107 — 2026-07-14 — Web-console ETH signal check

- Added a one-click ETH signal verification card to the default web-console Overview page.
- Reused the fixed offline verifier through a GET-only, fail-closed dashboard endpoint; the result
  remains historical reproduction evidence with independent risk `BLOCK`.
- Kept venue connection and execution authority at `NONE`, with paper/live orders disabled.

## v8.106 — 2026-07-14 — Prospective ETH volume-breakout strategy slice

- Froze one exact ETHUSDT Spot 1h volume-confirmed Donchian StrategyVersion behind a new future
  boundary; all exposed historical performance remains discovery evidence only.
- Added current-inclusive base-volume threshold support to the canonical evaluator and reproduced
  the old screen's exact 511 signal transitions over the pinned 48,154-bar dataset.
- Added a deterministic data-to-`SignalEvent`-to-independent-`BLOCK` verifier. Orders, paper/live,
  venues, credentials, promotion, and execution authority remain disabled.
- Added the human-readable `make eth-signal` console command; machine-readable JSON remains the
  verifier default when called directly.

## v8.105 — 2026-07-14 — Prospective association/overlay campaign freeze

- Froze exactly three prospective association trials with a sole 6H primary endpoint,
  deterministic matched controls, exact inference/materiality rules, temporal robustness, and no
  secondary-horizon or extra-time rescue.
- Separated association support from economic overlay validation. The child overlay cannot run
  without a separately validated exact alpha StrategyVersion and must retain missed opportunity.
- Added an executable preflight that verifies frozen hashes and observation progress while reading
  zero label files and computing zero warm-up metrics. Current status is `WAITING`; authority is
  `NONE`.

## v8.104 — 2026-07-14 — Deterministic prospective risk-signal slice

- Added a dedicated order-inert risk-state signal type; it cannot impersonate a strategy-bound
  signal, grant eligibility, connect a venue, or create paper/live orders.
- Connected the latest verified public checkpoint to the typed signal and independent blocking
  risk decision, with fail-closed semantic/authority checks and read-only dashboard visibility.
- Added a fixed offline verifier and end-to-end drift tests. This proves TradingOS plumbing, not
  alpha; the current signal remains `FLAT`, risk remains `BLOCK`, and authority remains `NONE`.

## v8.103 — 2026-07-14 — Prospective signal evidence-producer map

- Mapped every current signal-eligibility blocker to an owning producer, verifier, earliest lawful
  time, release condition, and affected gate/dimension.
- Corrected the read-only projection: 8,640 warm-up windows are samples, not campaign trials; the
  current campaign trial population is undeclared.
- Froze that a risk signal is not alpha and cannot support a bot without a separately validated
  StrategyVersion. Warm-up analysis and every execution capability remain blocked.

## v8.102 — 2026-07-14 — Deterministic strategy eligibility contract

- Refreshed official-platform validation research and added QuantConnect leaderboard scoring plus
  Darwinex calibration, risk normalization, and allocation-rating evidence.
- Added fail-closed metric, scorecard, and promotion eligibility evaluation with no blended score.
- Corrected the risk precondition's G10 omission; promotion now requires exact evidence-backed
  G1-G11 and all independent reviews. The prospective signal remains warm-up blocked.

## v8.101 — 2026-07-14 — Managed observation adoption

- Adopted the active D-095 public observer into the frozen TradingOS observation service without
  restarting it or changing existing evidence.
- Retained the content-addressed 8,640-checkpoint intent and first three consecutive long-run
  checkpoints; managed verification reported fresh, continuous, blocker-free collection.
- Preserved public-read-only transport and zero credential, venue, order, paper/live, or execution
  authority. This remains warm-up evidence collection, not validated alpha.

## v8.100 — 2026-07-14 — Managed observation implementation freeze

- Added the TradingOS observation service, fixed future launcher, canonical content-addressed run
  intents, and strict heartbeat/checkpoint/continuity projection.
- Added read-only status/dashboard visibility with no process-control API and no change to the
  offline JobStore worker or sandbox.
- Passed static gates and 104 focused architecture/dashboard/safety/prospective tests; froze exact
  code/test hashes before adopting the active run. Authority remains `NONE`.

## v8.99 — 2026-07-14 — Managed prospective-observation contract

- Rejected forcing a 30-day public WebSocket process into the offline, network-sandboxed,
  24-hour-bounded jobs worker.
- Froze a separate TradingOS observation service with immutable run intent, fixed command,
  heartbeat/continuity projection, stale detection, and read-only dashboard visibility.
- Authorized explicit adoption of the active frozen run without restart or history rewrite. No
  credential, account, order, paper/demo/live, score, promotion, or execution authority exists.

## v8.98 — 2026-07-13 — V5 two-window public proof

- From clean freeze `474fc0c`, finalized exactly two consecutive schema-5 checkpoints in one
  process, connection epoch, and continuity epoch with no failure.
- Both checkpoints remain `FLAT/WARMUP_BLOCK` with independent `BLOCK`; the longest retained chain
  is 2/8,640 and all nine source sessions reconstruct offline.
- Retained two newly causal 1h labels individually without aggregation or interpretation; four of
  18 rows are available and 14 remain unavailable. Kept mutable heartbeat state out of Git while
  preserving immutable checkpoint evidence. Made the status fixture tolerate the existing local
  runtime directory; observer code is unchanged. Authority remains `NONE`.

## v8.97 — 2026-07-13 — Checkpoint observer V5 freeze

- Implemented finite schema-5 per-window checkpoints on one public read-only WebSocket, atomic
  operational heartbeats, bounded reconnect/reset behavior, and overlap-proven planned rotation.
- Added offline tests for two consecutive checkpoints, mid-window disconnect preservation,
  continuity reset, planned rotation, reconstruction, and authority drift; all pass.
- Froze the exact code and test hashes before the first bounded two-window public proof. No label
  analysis, score, bot, credential, order, paper/demo/live state, or execution authority exists.

## v8.96 — 2026-07-13 — Persistent checkpoint operations contract

- Rejected a simple process loop because intentional reconnects can never build the consecutive
  baseline and Binance documents a 24-hour COIN-M connection lifetime.
- Froze atomic per-window checkpoints, 30-second heartbeats, bounded reconnect/reset semantics,
  and overlap-proven connection rotation before implementation.
- Kept runs finite, labels separate, warm-up analysis prohibited, and every venue/order/authority
  state disabled.

## v8.95 — 2026-07-13 — Second causal 1h label and V4 window

- Retained another successful schema-4 complete window with `source_failure=null`, `FLAT`, and
  independent `BLOCK`.
- Retained exact bytes for the second causally available 1h label; the 12-row snapshot contains
  two available labels and ten unavailable rows.
- Kept all labels unaggregated and unanalysed. Four complete windows remain isolated; no score,
  promotion, venue connection, order, or authority exists.

## v8.94 — 2026-07-13 — Observer V4 complete-window proof

- Retained a successful schema-4 `[20:00Z,20:05Z)` source session with
  `source_failure=null`, zero events, `FLAT/WARMUP_BLOCK`, and independent `BLOCK`.
- Retained a nine-row causal label schedule: one prior 1h label available, eight unavailable.
- Recorded that three total complete windows remain isolated and the longest consecutive chain is
  still one. No analysis, score, promotion, venue connection, order, or authority exists.

## v8.93 — 2026-07-13 — First causally available prospective label

- From clean V4 freeze commit `e8805cc`, retained exact 1m Spot entry/exit bytes after the frozen
  1h availability boundary and reconstructed the gross arithmetic label.
- Kept five later labels `NOT_AVAILABLE` with no request; all three snapshots verify offline.
- Corrected the regression fixture to order snapshots by embedded evaluation time, not hash name.
- Classified the single outcome as retain-only warm-up evidence. No aggregation, interpretation,
  score, promotion, venue connection, order, or authority exists.

## v8.92 — 2026-07-13 — Live schema diagnosis and observer V4 freeze

- V3 retained the exact rejected live message and proved the parser/fixture incorrectly expected
  top-level `st`; the actual force-order message publishes `o.st`.
- Corrected the exact schema path, versioned new sessions as schema 4, and preserved the V3 failure
  as immutable known pre-fix evidence.
- Both failed sessions retain zero windows. Signal, labels, scoring, promotion, venue connection,
  orders, and execution authority remain unchanged.

## v8.91 — 2026-07-13 — Fail-closed continuity evidence and observer V3 freeze

- Retained a 26m49s source session that ended `FAILED_LiquidationStressError`; correctly admitted
  zero windows and emitted `FLAT/SOURCE_WINDOW_INCOMPLETE/BLOCK`.
- Recorded the V2 diagnostic gap: the exact cause is unknown because error text and the rejected
  public message were not preserved.
- Froze V3 exact failure evidence and offline reconstruction before another capture. Signal,
  labels, scoring, promotion, venue connection, and authority remain unchanged.

## v8.90 — 2026-07-13 — Second complete prospective window

- Retained `[19:05Z,19:10Z)` as a second valid zero-event `FLAT/WARMUP_BLOCK/BLOCK` window.
- Recorded that the two complete windows are nonconsecutive, so the longest warm-up chain remains
  one rather than overstating total observations as baseline progress.
- After verifier V2 froze, retained six causal `NOT_AVAILABLE` label rows and verified both label
  snapshots. No Spot outcome, score, promotion, venue connection, or authority exists.

## v8.89 — 2026-07-13 — Append-only label verifier V2 freeze

- Recorded a fail-closed refresh attempt that wrote no artifact and exposed no future outcome.
- Corrected snapshot reconstruction to use only complete windows closed by that snapshot's own
  evaluation time, so later append-only source evidence cannot invalidate prior evidence.
- Added a regression test while preserving every frozen label, warm-up, eligibility, and authority
  rule. The corrected evaluator refresh remains unrun until after this commit.

## v8.88 — 2026-07-13 — First causal label schedule

- Ran the evaluator from clean D-084 freeze commit `a09d308` at `19:00:07Z`.
- Retained three explicit `NOT_AVAILABLE` rows because no frozen horizon was yet causal; made no
  Spot kline request and retained no price or return.
- Verified the content-addressed snapshot offline. Analysis, scoring, promotion, credentials,
  venue connection, paper/live orders, and execution authority remain disabled.

## v8.87 — 2026-07-13 — Prospective causal label freeze

- Froze Binance Spot BTCUSDT one-minute entry and 1h/6h/24h exit timestamps before evaluation;
  every request is prohibited until its exact exit candle has completed.
- Added content-addressed exact-response retention and offline reconstruction for session links,
  timing, prices, returns, eligibility, and authority.
- Focused tests reject wrong candle timestamps, early future labels, and rehashed paper-order drift.
  Warm-up analysis, scoring, promotion, venue connection, and execution authority remain disabled.

## v8.86 — 2026-07-13 — First complete prospective signal window

- Ran exactly one complete-window session from frozen observer commit `eaf2604`.
- Retained continuous coverage of `[18:45Z,18:50Z)`, zero published snapshots, a valid complete
  USD 0 observation, `SIG-54b9c184a05a3a037df6495d`, `FLAT`, and `WARMUP_BLOCK`.
- Reconstructed both retained sessions offline. Independent risk remains `BLOCK`; metric,
  scorecard, promotion, paper/live orders, credentials, and execution authority remain absent.

## v8.85 — 2026-07-13 — Complete-window prospective observer V2 freeze

- Added an operational-only observer amendment without changing the frozen signal rule.
- Added exact WebSocket coverage bounds, fully enclosed UTC five-minute window assembly, valid
  zero-event windows, consecutive-baseline enforcement, and offline reconstruction.
- Verified the retained V1 session and deliberate byte/rehashed-authority drift failures.
- Authorized one post-commit complete-window public observation only; scoring, credentials,
  orders, paper/demo/live state, promotion, and execution authority remain absent.

## v8.84 — 2026-07-13 — First prospective risk-signal session

- Ran the first bounded public BTCUSD_PERP observation only after the D-080 implementation was
  committed at `2e385a8`.
- Retained exact exchange-info bytes and a content-addressed 30-second session with zero published
  snapshots, deterministic `SIG-495ecfb03d8003161565ea47`, and `FLAT/BLOCK` disposition.
- Verified source/session hashes, frozen-commit binding, no credentials, no account/venue session,
  and disabled paper/live orders. No metric, scorecard, promotion, or execution authority exists.

## v8.83 — 2026-07-13 — Prospective liquidation-stress signal freeze

- Used D-079's prospective-evidence path without reopening historical performance.
- Froze one BTCUSD_PERP public forced-order snapshot risk signal: five-minute UTC windows, 30-day
  complete warm-up, prior nearest-rank 99th-percentile gross threshold, and 80% directional share.
- Added strict source parsing, duplicate handling, classification, a bounded keyless WebSocket
  observer, content-addressed writes, and causal/fail-closed tests.
- Every signal is `FLAT` and independently action-blocked while promotion is false. Observation,
  paper/demo/live state, credentials, orders, venue authority, and execution remain absent.

## v8.82 — 2026-07-13 — Public-signal research boundary NO_GO

- Added the ninth source-only three-family dossier without computing candidate performance.
- Rejected exchange-flow labels (authenticated/proprietary PiT dependency), forced-liquidation
  stress (throttled 472-day stale official archive), and CME curve/roll (entitled historical data
  and derivative capital-model dependency).
- D-079 stops autonomous public-signal mining after the cumulative negative campaigns rather than
  expanding the hidden family-search burden. Reopen requires new exogenous evidence, approved
  authoritative data access, or genuinely prospective preregistered observations.
- No Task-2 build, bot, venue, credential, order, paper/demo/live state, human gate, sealed holdout,
  promotion, or execution authority was activated.

## v8.81 — 2026-07-13

- Completed the cross-venue premium campaign from clean commit `2cb84c8` with the hashed
  development-selection barrier and complete four-role parity intact.
- Rejected the family: development and both OOS segments lost, zero of six periods was positive,
  stress lost 96.50%, one-bar delay lost 72.99%, and DSR was 0.00000395.
- Closed the exact context without rescue; execution authority remains `NONE`.

## v8.80 — 2026-07-13

- Added the cross-venue premium canonical family and 12 immutable StrategyVersion identities.
- Added independent Decimal, vectorbt, Freqtrade-environment, and Nautilus-environment roles with
  causal timing/gap/polarity/cost goldens.
- Froze the six-cost, six-period G1-G11 campaign behind a hashed development-selection barrier;
  the campaign remains unrun and execution authority remains `NONE`.

## v8.79 — 2026-07-13

- Froze 382 exact public Coinbase documentation/product/candle responses with complete request and
  response provenance; no key or authenticated endpoint was used.
- Deterministically normalized 45,193 quote-adjusted cross-venue observations with six explicit
  gaps and 45,192 strict-later Binance-open mappings, without computing future returns.
- Added byte-identical rebuild, offline verification, and deliberate raw/logical/mapping drift
  tests; retained execution authority `NONE`.

## v8.78 — 2026-07-13

- Compared three new mechanisms from primary sources without computing local family performance.
- Admitted only the quote-normalized Coinbase/Binance BTC premium to exact data packaging and
  froze its 12-trial roster, causal boundary, quote conversion, gaps, and no-rescue rules.
- Rejected U.S. Spot Bitcoin ETP flow and USDt peg stress for this cycle; retained execution
  authority `NONE` and every sealed-holdout/human-gate boundary.

## v8.77 — 2026-07-13

- Completed taker-imbalance V2 from clean commit `eba18df` with the hashed selection barrier intact.
- Rejected the family: all primary/OOS/stress/delay economics lost, full drawdown was 90.37%, only
  one of seven periods was positive, DSR was 0.0000208, and two nonselected trials had vectorbt
  parity residuals.
- Closed the context without rescue; execution authority remains `NONE`.

## v8.76 — 2026-07-13

- Closed taker-imbalance V1 pre-selection after its exact reference implementation remained
  CPU-bound; no result, selection, OOS segment, or strategy verdict was created.
- Froze V2 with only prefix-moment computation and cost-independent event caching; V1 strategy,
  statistical, and safety terms are inherited by hash.
- Retained execution authority `NONE` and all no-live/no-holdout boundaries.

## v8.75 — 2026-07-13

- Froze 12 Spot taker-imbalance StrategyVersions and exact completed-hour-to-next-open pulse
  semantics.
- Added canonical, independent Decimal, vectorbt, Freqtrade-environment, and Nautilus-environment
  roles plus causal micro-goldens.
- Added a hashed development-selection barrier before all OOS evaluation and retained execution
  authority `NONE`; the complete campaign remains unrun.
- Made the dashboard future-timestamp fixture collection-delay-proof after the expanded offline
  verifier suite exposed its ten-minute boundary race; production clock semantics are unchanged.

## v8.74 — 2026-07-13

- Froze the dedicated BTCUSDT Spot taker-imbalance data identity from retained official-checksum
  archives and canonical normalized data.
- Verified 72,225 rows, 72,221 valid features, four quarantined rows, 25 gaps, and 72,220 strict
  post-close mappings with deliberate drift tests.
- Retained execution authority `NONE`; no imbalance-conditioned return was computed.

## v8.73 — 2026-07-13

- Compared exactly three new source-backed mechanisms after the CFTC rejection.
- Admitted completed-hour Binance Spot taker imbalance only; rejected perpetual OI and macro
  liquidity for bounded point-in-time/method feasibility.
- Preregistered 12 trials, strict post-close fills, six-hour pulses, splits, gates, selection
  barrier, and no-rescue rules without computing local family performance.

## v8.72 — 2026-07-13

- Completed the frozen CFTC positioning campaign from clean commit `b3bc024` with the hashed
  development-selection barrier intact and exact four-role parity.
- Rejected the family at G11: validation -2.50%, insufficient sample, 63.35% drawdown,
  four-of-seven positive periods, benchmark-Sharpe failure, PBO 0.5578, and DSR 0.3493.
- Closed the exact context without rescue; execution authority remains `NONE`.

## v8.71 — 2026-07-13

- Froze 12 CFTC-positioning StrategyVersions and exact report-to-Spot pulse semantics.
- Added independent Decimal, vectorbt, Freqtrade-environment, and Nautilus-environment roles.
- Added causal goldens and a hashed development-selection barrier before all OOS evaluation.
- Retained execution authority `NONE`; the complete campaign remains unrun.

## v8.70 — 2026-07-13

- Froze exact filtered CFTC Legacy Futures Only bytes, metadata, schedules, and exception evidence.
- Added 33 official-checksum Binance BTCUSDT 1h archives covering 2018-04 through 2020-12.
- Verified 431 CFTC rows, 30 release exceptions, 72,225 Spot bars, 25 gaps, and 428 causal mappings.
- Retained execution authority `NONE`; no conditioned return, derivative, bot, venue, credential,
  order, or holdout was activated.

## v8.69 — 2026-07-13

- Compared regulated futures positioning, blockspace fee pressure, and dormant-supply reactivation
  without computing local family performance.
- Admitted only CFTC full-size CME Bitcoin positioning to exact data packaging.
- Made actual CFTC publication exceptions a blocking causal-data requirement.
- Retained execution authority `NONE`; no derivative, bot, venue, credential, order, or holdout
  was activated.

## v8.68 — 2026-07-13

- Recorded the completed Bitcoin MVRV campaign and independent G11 rejection.
- Preserved the selection barrier and four-role parity evidence.
- Closed the exact MVRV pulse family without rescue.
- Retained execution authority `NONE`; no bot, venue, credential, order, or holdout was activated.

## v8.67 — 2026-07-13

- Froze the canonical 12-trial Bitcoin MVRV campaign before scoring.
- Added exact Decimal, vectorbt, Freqtrade-environment, and Nautilus-environment roles.
- Added a hashed development-selection barrier that blocks validation/reserve access.
- Retained execution authority `NONE`; no bot, venue, credential, order, or holdout was activated.

## v8.66 — 2026-07-13

- Compared MVRV dislocation, U.S. financial conditions, and public attention from current sources.
- Admitted only BTC MVRV and froze the official no-key metric/catalog snapshot before scoring.
- Added offline byte, schema, metric, positivity, density, lag, and Spot-mapping verification.
- Retained execution authority `NONE`; no bot, venue, credential, order, or holdout was activated.

## v8.65 — 2026-07-13

- Recorded the completed Bitcoin transaction-activity campaign and G11 rejection.
- Preserved the development selection barrier and four-role parity evidence.
- Closed the exact HIGH/LOW transaction-count pulse family without rescue.
- Retained execution authority `NONE`; no bot, venue, credential, order, or holdout was activated.

## v8.64 — 2026-07-13

- Froze the 12-trial Bitcoin transaction-activity canonical campaign before scoring.
- Added strict two-day-lag, consecutive-window, non-extending pulse, and gap semantics.
- Added independent Decimal, vectorbt, Freqtrade-environment, and Nautilus-environment roles.
- Added a hashed development-selection barrier that blocks validation/reserve access.
- Retained execution authority `NONE`; no bot, venue, credential, order, or holdout was activated.

## v4 — 2026-07-05
- Added Phase 3 Execution Readiness Report.
- Added Crypto Spot Venue & Data Matrix V1.
- Added Experiment Lineage Executable Prototype Spec V1.
- Added Strategy Ingestion & Reproduction Workflow V1.
- Added Frozen AI & Agent Benchmark Suite V1.
- Added venue technical-shortlist vs operator-eligibility hard gate.
- Added tiered market-data acquisition policy.
- Added MLflow + DVC prototype hypothesis and acceptance gates.
- Added manual strategy-ingestion seed-batch rule.
- Updated project state, decision log, research backlog, missing items, and source registry.

## v3 — 2026-07-05
- Replaced Cursor-specific terminology with generic `coding agent` terminology.
- Added Engine Bake-Off Blueprint V1.
- Added Phase 2 Targeted Discovery Report.
- Added Existing Strategy Registry V0.
- Added AI & Agent Evaluation Blueprint V1.
- Added Experiment Lineage Blueprint V1.
- Updated project state, decision log, research backlog, missing items, source registry.
- Explicitly kept live exchange unresolved pending Israel/operator-fit verification.

## v2
- Added Phase 1 ecosystem discovery, initial reuse matrix, source registry.

## v1
- Established North Star and continuity package.

## v5 — 2026-07-05

Transitioned package from preparation to constrained coding-agent readiness.

Added:
- `research/ecosystem_discovery/PHASE_4_HANDOFF_READINESS_REPORT.md`
- `specs/CANONICAL_BAKEOFF_DATASET_V1.md`
- `specs/FEE_AND_SLIPPAGE_ASSUMPTION_PACKAGE_V1.md`
- `specs/BACKTESTING_VALIDATION_BLUEPRINT_V1.md`
- `specs/CRYPTO_SPOT_MVP_VERTICAL_SLICE_V1.md`
- `specs/STRATEGY_SEED_BATCH_V1.md`
- `decisions/CODING_AGENT_READINESS_GATE_V1.md`
- `handoffs/START_HERE_SINGLE_CODING_AGENT_PROMPT.md`

Updated:
- `PROJECT_STATE.md`
- `DECISION_LOG.md`
- `RESEARCH_BACKLOG.md`
- `MISSING_AND_OPEN_ITEMS.md`

Key outcome:
- PASS for constrained coding-agent prototype execution.
- Still no approval for full product build, final production architecture, or real-money trading.

## v6 — SSOT + Pre-Code Environment Intake

- Promoted `handoffs/START_HERE_SINGLE_CODING_AGENT_PROMPT.md` to explicit single operational SSOT.
- Added strict precedence/conflict-resolution hierarchy.
- Added `specs/ENVIRONMENT_AND_CREDENTIALS_INTAKE_GATE_V1.md`.
- Added hard no-code-before-intake gate.
- Added per-item `Configure now / Add later / Do not use / Not sure` choices.
- Added secret-handling rules and `.env.example` workflow.
- Updated project state, readiness gate, and decision log.


## v7 — Handoff simulation hardening

- Simulated a fresh coding agent starting with zero conversation context.
- Added explicit package integrity and input/output contract to the SSOT.
- Added `PACKAGE_INTEGRITY_MANIFEST.md`.
- Added `handoffs/HANDOFF_SIMULATION_AUDIT_V1.md`.
- Corrected ambiguous fee/slippage spec path in `DECISION_LOG.md`.
- Added explicit pre-code mutation boundary.
- Clarified that missing future reports/decision outputs are expected generated artifacts, not broken package inputs.

## v8 — 2026-07-06 — Planning system (principal-architecture mandate)

Added (planning/architecture/task/audit layer; no product code):
- `docs/architecture/AD.md`, `docs/architecture/MODULE_CATALOG.md`, `docs/architecture/TYPE_AND_CONTRACT_CATALOG.md`
- `docs/program/PROGRAM_PLAN.md`, `docs/product/MVP_SCOPE.md`, `docs/testing/TEST_MASTER_PLAN.md`
- `docs/traceability/TRACEABILITY_MATRIX.md`, `docs/ai/AGENT_ROLES.md`
- `skills/README.md` + 13 skill specifications
- `TODO.md` + `todos/00…20` (21 initiative files, REQ-traced)
- `research/EXISTING_CAPABILITY_REGISTRY.md` (full freshness re-verification dated 2026-07-06)
- `research/RESEARCH_GAP_MATRIX.md` (9 gaps closed, 16 open with owners/triggers)
- `audits/ARCHITECTURE_COMPLETENESS_AUDIT.md`, `audits/TODO_COMPLETENESS_AUDIT.md`, `audits/RED_TEAM_PLAN_REVIEW.md`, `audits/PLANNING_HANDOFF_SIMULATION.md`

Updated:
- `handoffs/START_HERE_SINGLE_CODING_AGENT_PROMPT.md` — precedence slots for planning authorities + TODO layer; extended mandatory read order; stage/first-initiative pointer (T-003-01). Still the single controller.
- `DECISION_LOG.md` — duplicate IDs renumbered (D-027/D-028); new D-029…D-032.
- `specs/CANONICAL_BAKEOFF_DATASET_V1.md` — Amendment A1 (Binance µs timestamps from 2025-01-01 files).
- `PROJECT_STATE.md`, `MISSING_AND_OPEN_ITEMS.md`, `RESEARCH_BACKLOG.md`, `PACKAGE_README.md`.
- `PACKAGE_INTEGRITY_MANIFEST.md` — hashes regenerated; planning artifacts added as required inputs.

Key outcomes:
- Planning phase complete; S1 prototype execution remains the authorized next phase; first task T-003-01 (intake gate).
- Evidence-refresh corrections: vectorbt OSS active again; Backtrader/backtesting.py rejected; Databento reclassified; OKX↑/Coinbase↓ in connectivity ranking (live gates unchanged); MLflow/DVC hypothesis strengthened (DVC now under lakeFS stewardship); AI benchmarking must multi-sample (no provider determinism).
- Still NO approval for full product build, final architecture lock (PROVISIONAL items enumerated), or real-money trading.

## v8.1 — 2026-07-06 — S1 execution: initiative 03 complete

- HG-1 intake gate PASSED (interactive; AI provider keys deferred; MLflow/DVC fully local; zero secrets anywhere). Report: `artifacts/reports/PRE_CODE_ENVIRONMENT_INTAKE_REPORT.md`.
- Initiative 03 DONE (T-003-01..05): git repo initialized; AD §F tree + module skeletons; idempotent bootstrap; one-command local gate (`make check`) with architecture dependency-law test, decision-ID uniqueness, secret scan — proven failable; per-engine isolated envs built and smoke-tested (freqtrade 2026.6, nautilus_trader 1.230.0, vectorbt 1.1.0, lean CLI 1.0.227, hummingbot 2.15.0 by digest); security review #1 PASS with all 6 findings fixed.
- T-001-01/RG-03 closed: vectorbt 1.1.0 license = Apache 2.0 + Commons Clause (verified from dist-info; `engines/vectorbt/LICENSE_CAPTURED.txt`). RG-04 closed via per-engine isolation. Gap matrix rows CG-10/CG-11.
- Controlled edits (manifest regenerated, 5 hashes): PROJECT_STATE.md, registry, gap matrix, todos/01, todos/03.

## v8.2 — 2026-07-06 — S1 execution: initiatives 04, 05 complete; 06 started; 18 partial

- Initiative 04 DONE (EG-1): DS-CRYPTO-SPOT-BAKEOFF-V1 frozen — 396 raw files checksum-verified, 1.64M normalized rows, Amendment A1 boundary goldens, quality PASS (all checks proven failable), double-regeneration identical hashes, independent audit PASS_WITH_NOTES (zero discrepancies).
- Initiative 05 DONE: canonical spec model/validator (property-tested), immutable SV, baselines B1–B4 + double-derived micro goldens.
- Initiative 06: T-006-01 DONE (EngineAdapter port, NormalizedResult, capability gaps, mandatory fee/slippage grid, fee audit utility).
- Initiative 18: T-018-01/03 DONE (secret hygiene, license audit w/ planted-AGPL proof).
- Controlled edits: PROJECT_STATE, todos/04/05/06/18 — manifest regenerated.

## v8.3 — 2026-07-06 — S1: Freqtrade matrix + vectorbt probe evidence

- Freqtrade lane: B1–B4 × {F0/S0, F1/S1} all OK on frozen dataset; normalization to canonical decimal parquet; fee/PnL audit PASS everywhere; determinism byte-identical; lookahead flag root-caused (execution-state artifact, numeric proof); slippage CapabilityGap recorded; stake-model semantic note for parity.
- vectorbt probe: 1.31M bar-combos/s, all trials retained.
- Controlled edits: PROJECT_STATE, todos/06 — manifest regenerated.

## v8.4 — 2026-07-07 — Governance re-check (gov-02): decision-ID gate coverage fix

- `make check` re-verified green (63 tests, ruff, mypy-strict).
- Found and fixed a real gap: D-027/D-028 used `##` headings, so `tests/test_decision_ids.py`'s uniqueness regex (`### D-NNN`) silently skipped them. Normalized both to `###` (D-033); all 32 decision IDs now covered.
- Confirmed no invented decision-category labels in `DECISION_LOG.md`; confirmed PROJECT_STATE.md matches latest closed work; confirmed no stop-condition triggers worked around.
- Controlled edits: DECISION_LOG.md (D-033 + heading fix), PROJECT_STATE.md.
## v8.5 — 2026-07-10 — S1 executable evidence and HG-2 review packet

- Executed and selected the local MLflow+DVC lineage composition; retained restore,
  compare, strategy trace, mock-only AI trace, and thin domain-link evidence.
- Closed available engine parity with explained B1/B2 divergences; closed the
  Freqtrade lane with constraints and vectorbt with 66/66 retained ledgered trials.
- Kept the real Trading OS dashboard live and added explicit HG-2 readiness while
  preserving `INCOMPLETE_NOT_APPROVABLE` strategy validation and no-order boundaries.
- Added the S1 stage-exit review, D-035, and regenerated all changed controlled-input
  SHA-256 entries in `PACKAGE_INTEGRITY_MANIFEST.md`.
- Closed the S1 contextual approval, independent risk-precondition, and ingested-code
  containment tasks; Security Review #2 passes and the local gate now has 123 tests.

## v8.6 — 2026-07-10 — S2-0 governance reconciliation

- Recorded the operator's explicit HG-2 approval as D-036 and opened constrained S2
  architecture, autonomous research/test-lab, sourced-research, offline backtesting,
  retained-trial scoring, validation, and research-console work.
- Made `docs/program/S2_AUTONOMOUS_RESEARCH_LAB_PLAN.md` the active S2 execution plan
  under the existing SSOT hierarchy.
- Preserved B2 as `INCOMPLETE_NOT_APPROVABLE` and rejected for paper; no strategy,
  synthetic wallet, paper/demo/testnet venue connection, credentials, order routing,
  live trading, real money, or AI approval/trading authority was granted.
- Reconciled the prototype decision, S1 stage exit/readiness reports, project state,
  operational handoff, program/architecture task states, and execution plan. The
  integrity manifest was intentionally not edited in this reconciliation.

## v8.7 — 2026-07-10 — S2 architecture-lock governance reconciliation

- Added unique D-037 for the evidence-backed S2 architecture lock: modular monolith;
  SQLite operational state with measured PostgreSQL triggers; Parquet/DuckDB analytics;
  MLflow+DVC behind ports; and bounded scheduling only after real idempotent reuse.
- Closed T-002-01..04 against their revised, evidence-backed acceptance criteria and
  recorded engine roles. Hummingbot/LEAN deferred adapters and normalized artifacts are
  retained as evidence-only/deferred assets rather than deleting historical evidence.
- Activated only bounded S2 initiatives 13, 14, 17, and 19; full ontology initiative 12
  remains deferred. Folded former product wave 7 into the S2 console/product slice.
- Removed stale HG-2/S1-current and resolved-open-item wording while preserving B2/G4/G10
  strategy-validation gaps, engine gaps, and all paper/demo/live human gates.
- Kept the execution boundary read-only and inert. No real `LAB-*` batch, enabled
  scheduler, S2 completion, strategy approval, paper/demo connection, or live capability
  is claimed. The integrity manifest and all source/test files were intentionally left
  untouched by this reconciliation.

## v8.8 — 2026-07-10 — S2 Research Lab automation dashboard

- Finished the paused jobs/dashboard integration: read-only `build_jobs_projection(root)`,
  dashboard Automation view, and focused jobs/dashboard tests.
- Verified the real retained LAB-702 batch and persisted queue state: 2 succeeded
  `RESEARCH_LAB_V0` jobs, latest reused unchanged artifacts, recurring six-hour schedule
  next due `2026-07-11T00:00:00+00:00`, no failed/cancelled jobs.
- Ran full quality gates: Ruff, format check, strict mypy, 282 tests, and
  `make required` including `pip-audit` with no known vulnerabilities.
- Browser-tested the live dashboard at 375/768/1024/1440 px across Overview, Research
  Lab, Automation, and Market Monitor; market evidence loaded from frozen candles plus
  retained backtest fills. The page remains read-only with no POST, credential, venue,
  order, paper/demo/live, or real-money control.
- Tightened the Automation projection after independent review: retained job errors are
  redacted by default, including unlabeled secret-looking failure text.
- Refreshed the Research Lab score assessment from retained validation evidence,
  producing `LAB-799f7d81843d15aaf3b161036a4cd543ac37a709cb1e2ecc72a161f7348488fa`.
  The new batch remains `UNVALIDATED` / `NOT_ELIGIBLE`, but distinguishes negative
  completed evidence (economic, drawdown, walk-forward, robustness, baseline
  superiority) from still-blocked multiple-testing and cross-engine reproduction.
- Enqueued and executed `s2-production-offline-research-lab-v0-cycle-003`; the local
  worker reused LAB-799 and retained a third succeeded `RESEARCH_LAB_V0` job without
  enabling any paper/demo/live or order capability.

## v8.9 — 2026-07-11 — S2 decision follow-through and dashboard governance

- Added Workspace human-decision recording for gated/recurring tasks:
  `artifacts/human_decisions/workspace_decisions.jsonl` records operator choices for
  future coding agents, while all trading/job/order controls remain absent.
- Completed the authorized official-source venue recheck and S3 design-only expansion
  slices: `VENUE_ISRAEL_SOURCE_RECHECK_2026_07_11.md` and
  `FUTURE_MARKET_EXPANSION_DESIGN_REVIEW_2026_07_11.md`.
- Rechecked AI cost telemetry credentials after the operator decision; no provider
  keys are visible, so `T-017-05` remains credential-blocked with evidence in
  `AI_COST_TELEMETRY_CREDENTIAL_RECHECK_2026_07_11.md`.
- Tightened dashboard freshness and API boundaries: core data auto-refreshes,
  Market Monitor refreshes while visible, `/api/v1/*` is the only active API, and
  legacy `/api/*` paths return `410`.
- Regenerated all changed controlled-input SHA-256 entries in
  `PACKAGE_INTEGRITY_MANIFEST.md`; manifest verification passes.

## v8.10 — 2026-07-11 — Full AD/docs/TODO/env audit pass

- Added four audit reports: `AD_IMPLEMENTATION_GAP_AUDIT_2026_07_11.md`,
  `OPEN_TASKS_AND_DOCS_AUDIT_2026_07_11.md`, `ENV_AND_CREDENTIALS_AUDIT_2026_07_11.md`,
  `WORKSPACE_TODO_API_SYNC_2026_07_11.md`.
- Added `TIOS_AI_MODE`/`TIOS_AI_PROVIDER` (names/comments only) to `.env.example`;
  verified `.env` git-ignore and zero secrets.
- Recorded the dashboard workspace-decision POST route vs AD §AI/type-catalog GET-only
  contract mismatch as a Current Implementation Gap note in AD §AI and new task
  **T-002-05 (DECISION REQUIRED)** in `todos/02_architecture_foundation.md`. Desired
  architecture was not changed; no defect was normalized into AD.
- Updated `PROJECT_STATE.md` and `MISSING_AND_OPEN_ITEMS.md`; regenerated
  `PACKAGE_INTEGRITY_MANIFEST.md` hashes for the controlled files edited in this pass.

## v8.11 — 2026-07-11 — D-038 API clarification and authorized S2 cycle

- Recorded D-038: the operator-approved clarification keeping
  `POST /api/v1/workspace-actions/decision` as the single audited, operator-driven,
  loopback, allowlist-validated, append-only write exception; AD §AI and
  `TYPE_AND_CONTRACT_CATALOG.md` §7 updated; T-002-05 marked DONE; gap note removed.
- Ran the authorized offline S2 Research Lab v0 cycle: idempotent reuse of LAB-f99d
  (66 trials, no winner, execution_authority=NONE); executed the due six-hour
  scheduled job via the local worker (succeeded, result_reused=true).
- Updated `PROJECT_STATE.md`, `MISSING_AND_OPEN_ITEMS.md`, `DECISION_LOG.md`,
  `todos/02_architecture_foundation.md`; regenerated integrity manifest hashes.

## v8.12 — 2026-07-11 — Operator access prep checklist

- Added `OPERATOR_ACCESS_PREP_CHECKLIST_2026_07_11.md` so future agents have one
  source for exchange and market-data account preparation without re-asking the
  same setup questions before every platform task.
- Reserved commented, inactive `.env.example` names for later Binance Spot Testnet,
  OKX Demo, Kraken, Coinbase CDP, CoinAPI, Kaiko, Tardis.dev, and Databento gates.
- Preserved all S2 boundaries: no credentials requested, no connections enabled, no
  paper/demo/testnet activation, no order routing, no live trading, and no real-money
  capability.
- Updated `PROJECT_STATE.md` and `MISSING_AND_OPEN_ITEMS.md`; regenerated integrity
  manifest hashes for controlled files.

## v8.12 — 2026-07-11 — Production G10 candidate integration (T-009-04 / RG-07)

- Added candidate-specific G10: `engines/vectorbt/g10_returns.py` (per-trial slice
  returns, subprocess-isolated) and `scripts/run_g10_candidate.py` (PBO/CSCV + DSR via
  the validated methods, exact parity check against the retained LAB Parquet, and an
  independent second implementation with ≤1e-9/≤1e-6 agreement).
- Retained `artifacts/validation/G10_CANDIDATE_EVIDENCE_2026_07_11.json`: all families
  FAIL (B2 PBO 0.8685, DSR≈0). B2 package gate G10 is now FAIL (was NOT_RUN);
  `multiple_testing_selection_bias_control` is FAIL (was BLOCKED) in refreshed batch
  `LAB-73ebd3a3bb3e4086b2408552559e77a26d1334ae9cc789c4459beadc27b6844a`.
- Updated validation package builder, lab score mapping, retained method-candidate and
  validation-status artifacts, tests (`tests/test_g10_candidate.py` added), RG-07 row,
  T-009-04 status, PROJECT_STATE, and MISSING_AND_OPEN_ITEMS. No strategy approved;
  no execution path enabled.

## v8.13 — 2026-07-11 — Cross-engine reproduction dimension closed

- Added three-way B2 reproduction: engine-independent core derivation,
  `engines/vectorbt/repro_b2.py` (exact signal match, one explained float tie), and a
  dedicated single-pair BTCUSDT full-history Freqtrade backtest
  (`artifacts/validation/repro/`, 66,385 trades, all exit_signal, 99.904% exact
  fill↔signal reconciliation; residuals quantified as decimal128→float64 indicator
  arithmetic). Verdict PASS_WITH_SCOPE_NOTE — fill/P&L parity NOT claimed.
- `scripts/run_cross_engine_reproduction.py` + `tests/test_cross_engine_reproduction.py`;
  lab dimension now binds to the evidence artifact (added to lab input hashes).
- Batch `LAB-c9578b6b45cdbf1f3c2f6ba1320f993f6f149fb83d17905e9070bc07079c7aea`
  retains zero BLOCKED score dimensions; candidate remains rejected; no winner,
  no execution authority. Updated state/docs/tests; manifest regenerated.

## v8.14 — 2026-07-11 — Chunking design, session handoff

- Added `specs/HUMMINGBOT_FULL_HISTORY_CHUNKING_DESIGN_V1.md` (30-day warm-up-prefixed
  windows, seam-audited stitching, per-window timeouts, operator rerun framing);
  T-006-05 throughput track now references it.
- Added `handoffs/CONTINUE_S2_2026-07-11_VALIDATION_DIMENSIONS_COMPLETE.md` — full
  continuation handoff: completed work, verification state, batch-pin mechanics,
  prioritized remaining work, and exact next action (operator research-direction
  decision). PROJECT_STATE "Exact next action" updated to match.

## v8.15 — 2026-07-11 — Seeds 03/07 reproduced; seed cycle widened to 4 candidates

- Added `fixtures/micro/bars_long.csv` (32 bars, designed dip/rally around a 20-bar
  Bollinger warm-up) and two reproduction spot-checks in
  `tests/test_strategy_seed_reproduction.py` (BB population-std + Wilder RSI,
  double-derived expected bars). Seeds 03 (STRAT-FT1-sample-strategy) and 07
  (STRAT-PINE1-bb-strategy) are REPRODUCED; registry and status docs updated.
- Extended `scripts/run_seed_research_cycle_v0.py` with PINE1 (BB window/std sweep)
  and FT1 (RSI window/threshold sweep) candidates:
  `SEEDCYCLE-9a2bc401…` retains 34 trials across 4 candidates, all ≈ −100% on the
  proxy, no winner, no execution authority. Dashboard seed-cycle pin updated.

## v8.16 — 2026-07-11 — Seed 04 reproduced (true EMA); seed cycle at 5 candidates

- Added true recursive EMA (SMA seed, talib convention) to the reproduction tests
  and the seed cycle; seed 04 (STRAT-FT2-ema-cross) is REPRODUCED — the flagged
  EMA-approximation deferral is closed. Registry and status doc updated.
- `SEEDCYCLE-25fc2ebb…` retains 43 trials across 5 reproduced candidates, all
  ≈ −100% on the proxy, no winner, no execution authority. Only agent-closable
  seeds remaining: none (05/08 await a human tri-state decision; 06/09/10 are
  not applicable).

## v8.17 — 2026-07-11 — External bot/signal source architecture

- Updated AD §U to explicitly include exchange-hosted bot marketplaces, copy-trading
  records, online signal feeds, public leaderboards, and third-party bot platforms as
  core future Research Lab source classes.
- Updated `AGENT_ROLES.md` and `STRATEGY_SEED_BATCH_V1.md` so future strategy
  extraction handles bot/copy/signal sources as hypothesis/replay inputs with
  platform terms, timestamp semantics, parameter visibility, and bias risks.
- Preserved the execution boundary: external bots/signals may inspire or replay
  candidates, but cannot directly copy trades, control the wallet, or bypass
  validation, paper/demo, risk/security, and human gates.

## v8.18 — 2026-07-11 — D-040 multi-grid seed A/B retained

- Recorded the AI-delegated D-040 offline research decision: extend the five
  reproduced seed candidates across BTCUSDT/ETHUSDT x 5m/15m/1h.
- Retained `SEEDCYCLE-9b1652…` with 258 trials, no winner, and
  `execution_authority=NONE`; `uv run python scripts/run_seed_research_cycle_v0.py`
  reuses the completed cycle.
- Added `SEED_CYCLE_MULTI_GRID_REPORT_2026_07_11.md`; lower-frequency contexts
  produced positive proxy rows led by QC2 Donchian ETHUSDT 1h window=40, but no
  candidate is validated or eligible.
- Updated project state, open items, strategy registry, and continuation handoff;
  next offline work is validation evidence for the top positive proxy contexts.

## v8.19 — 2026-07-11 — Seed positive-context validation probe

- Added `scripts/run_seed_candidate_validation_probe.py` and retained
  `artifacts/validation/seed_candidates/SEED_VALIDATION_PROBE_2026_07_11.json`.
- The probe covers the top three D-040 positive proxy contexts with chronological
  thirds, fee stress, buy-and-hold comparison, and parameter-neighborhood evidence.
- QC2 Donchian ETHUSDT 1h window=40 survives the first probe but is parameter-fragile
  and still lacks production G10, cross-engine reproduction, paper/demo divergence,
  and red-team evidence; all contexts remain `UNVALIDATED` / `NOT_ELIGIBLE`.
- Added focused tests for the retained probe artifact and updated state/open-items/
  handoff records. No execution capability was enabled.

## v8.20 — 2026-07-11 — Seed-context G10 failure retained

- Added `scripts/run_seed_candidate_g10.py` and retained
  `artifacts/validation/seed_candidates/SEED_G10_QC2_ETHUSDT_1H_2026_07_11.json`.
- The strongest D-040 seed context, QC2 ETHUSDT 1h window=40, fails G10: PBO 0.2614
  but DSR 0.7564 below the 0.95 rule. Independent recomputation agrees.
- Updated the multi-grid report, project state, open items, and continuation handoff;
  no strategy is validated or eligible.

## v8.21 — 2026-07-11 — External source-intake seed retained

- Widened `ResearchSourceRegistry` beyond primary papers to accept read-only,
  DOI-optional platform sources for exchange bot marketplaces, copy-trading
  leaderboards, online signal feeds, and third-party bot platforms.
- Added four hypothesis-only source records: Binance Trading Bots, Binance Copy
  Trading, TradingView Ideas, and 3Commas DCA Bot. All remain non-reproduced,
  non-eligible, and carry no credential, copy, venue, order, paper/demo/live, or
  real-money authority.
- Added `EXTERNAL_SOURCE_INTAKE_PLANS_V1.yaml` plus a typed validator and dashboard
  read-model counts for 4 offline capture/replay plans. Each plan must carry the full
  S2 prohibition set before it can be retained.
- Added `scripts/build_external_source_intake_snapshots.py` and retained the first
  metadata-only source-intake artifacts under `artifacts/source_intake/`.
- Added `EXTERNAL_SOURCE_PUBLIC_CAPTURE_V1.yaml` and filled first lawful public-source
  metadata fields for the four source snapshots without fetching content at runtime or
  enabling any credential/copy/order path.
- Added `EXTERNAL_REPLAY_HYPOTHESES_V1.yaml` plus typed validation for four source-linked
  replay hypotheses; all are non-eligible and `execution_authority=NONE`, with Binance
  copy trading deliberately marked non-reconstructable until historical actions exist.
- Dashboard source projection now includes replay-hypothesis counts.
- Added the first canonical non-executing external replay candidate under
  `strategies/external/3commas-dca-config/`; it validates with ambiguities but remains
  `SPECIFIED_NOT_REPRODUCED`, `UNVALIDATED`, and `execution_authority=NONE`.
- Dashboard strategy projection now includes the external replay candidate without
  marking it valid or eligible.
- Retained `artifacts/reports/EXTERNAL_SOURCE_INTAKE_SEED_2026_07_11.md` and reran
  the offline lab as
  `LAB-f04ef5d705e0de4d3fff5fe83ada90b2d91223dc89cfa35364c5fd8439ca3121`; no
  winner was selected and `execution_authority=NONE` remains binding.

## v8.22 — 2026-07-11 — External DCA local replay retained

- Added `scripts/run_external_dca_replay.py`, a local-only replay runner for the
  3Commas-style DCA hypothesis. It reads frozen candle Parquet files and writes
  evidence artifacts only; it has no account, credential, paper/demo/live, venue, or
  order-routing path.
- Retained
  `artifacts/external_replay/3commas_dca/EXTDCA-9ed0a866cc1ddb5f7f4e7a94b5c5e48b/`
  with 6 BTCUSDT/ETHUSDT x 5m/15m/1h trials and 43,738 local simulated events.
- Updated the external DCA replay candidate status to `LOCAL_REPLAY_RETAINED` while
  keeping `UNVALIDATED`, `promotion_eligible=false`, and `execution_authority=NONE`.
- Added focused replay tests and retained-artifact boundary tests; no strategy is
  validated or eligible.

## v8.23 — 2026-07-11 — Inert trading-domain dashboard surface

- Added a structured `/api/v1/dashboard` `trading_domain` projection for the S2
  product rails: order intents/states, accounts, positions, portfolio, risk decisions,
  demo wallet, and paper/live capability status.
- Added a dedicated dashboard view, "Trading Domain", that shows the future
  demo-wallet/paper rails as read-only and explicitly absent/disabled in S2.
- Pinned the contract in tests: `execution_authority=NONE`, no venue connection,
  no order endpoint, no credential access, no synthetic wallet mutation, and no
  demo/paper/live orders.
- Browser smoke passed at 375, 768, 1024, and 1440 px with no console/page errors
  or horizontal overflow.

## v8.24 — 2026-07-11 — Local registry and artifact search surface

- Added `GET /api/v1/search`, a read-only dashboard API projection over bounded
  concepts, ResearchAsset records, ResearchSource records, seed/external strategies,
  and retained Markdown reports.
- Added the dashboard Search view with local result counts, evidence paths, snippets,
  and explicit no-write/no-execution boundary text.
- Pinned focused tests for the search builder, HTTP schema/error contract, UI strings,
  and disabled writes, credentials, venue connection, order endpoint, and execution
  authority.
- Updated state/open-items/type-catalog/TODO records to mark the roadmap's bounded
  registry/report search slice complete without adding any trading capability.

## v8.25 — 2026-07-11 — Read-only comparison evidence surface

- Added `/api/v1/dashboard` `comparisons`, a local projection over retained lab
  scorecards, validation gates, production G10 evidence, seed validation probes,
  seed-context G10, cross-engine scope notes, and local evidence refs.
- Added the dashboard "Comparisons" view with candidate dimension matrix, validation
  gate table, G10 table, seed-context table, cross-engine scope notes, and artifact
  refs.
- Pinned focused tests that no winner is selected, no promotion candidate exists,
  `execution_authority=NONE`, and approval/job/credential/venue/paper/live/order
  controls remain disabled or absent.
- Updated state/open-items/TODO records to mark the bounded S2 comparison UI slice
  complete without running new strategy operations.

## v8.26 — 2026-07-11 — Demo-wallet readiness projection

- Added a design-only `trading_domain.demo_wallet_design` projection to
  `/api/v1/dashboard` with ledger, synthetic capital, mutation API, order route,
  venue connection, and execution authority all absent/disabled/NONE.
- Extended the Trading Domain dashboard view with "Demo wallet readiness" and
  "Demo wallet invariants" sections that show required future gates, allowed
  isolated-simulation scope, and must-never-include guardrails.
- Pinned focused tests that the future demo-wallet rail remains S2 design-only and
  cannot create wallet state, venue/order routing, credentials, or real-money paths.

## v8.27 — 2026-07-11 — Agent-executable completion audit

- Added `artifacts/reports/AGENT_EXECUTABLE_COMPLETION_AUDIT_2026_07_11.md` to record
  the current post-v8.26 inventory: 0 actionable open tasks, 7 gated tasks, and 4
  recurring tasks from the live workspace status API.
- Updated `PROJECT_STATE.md` and `MISSING_AND_OPEN_ITEMS.md` so the exact next action
  points to credential/S3/HG/human gates instead of implying more open S2 platform
  product work.
- Reaffirmed that no strategy is validated or promotion-eligible, `execution_authority`
  remains `NONE`, and no demo/paper/live/venue/order/credential path is enabled.

## v8.28 — 2026-07-11 — S3/S4 gate-readiness surface

- Added a read-only `trading_domain.stage_gate_readiness` projection distinguishing
  S3 paper/demo readiness from S4 live readiness.
- Added Trading Domain UI cards for "S3 paper/demo readiness" and "S4 live readiness"
  showing satisfied design evidence, blocked predicates, and next human actions.
- Pinned focused tests that both stages remain `NOT_READY`, `BLOCKED_BY_GATES`, and
  `execution_authority=NONE`; no activation, credential, venue, paper/demo/live, or
  order route was added.

## v8.29 — 2026-07-11 — Standalone stage-gates API

- Added `GET /api/v1/stage-gates`, a standalone read-only machine contract for S3/S4
  readiness. It mirrors the Trading Domain gate chain without exposing any transition
  or activation command.
- Updated the type-catalog API contract to include stage-gate readiness and explicitly
  prohibit stage-gate transitions plus demo/paper/live controls.
- Added focused tests for the builder and HTTP schema: writes disabled, credentials
  absent, order endpoint absent, S3/S4 both `NOT_READY`.

## v8.30 — 2026-07-11 — TradingView public-strategy intake lane

- Added `SRC-TRADINGVIEW-PUBLIC-STRATEGIES`,
  `INTAKE-TRADINGVIEW-PUBLIC-STRATEGIES`, and
  `RPH-TRADINGVIEW-PUBLIC-STRATEGY-TESTER` so open-source Pine strategies and
  TradingView Strategy Tester summaries are first-class research inputs.
- Captured required Strategy Tester fields: symbol, timeframe, date range, capital,
  commission/slippage, net profit, drawdown, trade count, win rate, and profit factor.
- Pinned the boundary that protected/invite-only scripts are excluded, TradingView
  results are external comparison evidence only, local OS reproduction is required,
  and `execution_authority=NONE` remains unchanged.

## v8.31 — 2026-07-11 — TradingView candidate selection batch

- Selected and retained eight public/open-source TradingView strategy candidates for
  offline reproduction under
  `artifacts/source_intake/tradingview_public_strategies/selected_candidates_2026_07_11.json`.
- Added read-only dashboard/search projection for the selected batch so candidate IDs,
  families, URLs, and tester-capture status are visible locally.
- Added tests pinning that the batch is metadata-only, not approval eligible, has
  `execution_authority=NONE`, requires Strategy Tester/source-hash capture, and does
  not enable paper/demo/live/order behavior.

## v8.32 — 2026-07-11 — TradingView prose-derived replay evidence

- Added `scripts/run_tradingview_public_strategy_replay.py`, an offline-only replay
  runner for the two TradingView candidates whose public pages expose enough rule
  detail for a first prose-derived local hypothesis.
- Retained the first replay under
  `artifacts/external_replay/tradingview_public_strategies/TVPINE-9f7d3fc15ece2785a4296e9eb3b15548/`
  with 2 candidates, 6 frozen datasets, 12 trials, and 57,046 local events.
- Projected the latest TradingView replay through the dashboard research-sources read
  model and tests. The scorecard remains `UNVALIDATED`, `NOT_ELIGIBLE`, no winner,
  `execution_authority=NONE`, no venue/account/credential, and no paper/demo/live or
  order route.

## v8.33 — 2026-07-11 — S3/S4 inert control-plane contracts

- Added immutable S3/S4 readiness contracts to `tios.trading_domain`:
  `StageGateReadinessRecord`, `StageGateRequirement`, `PaperLaneProposal`, and
  `PaperDivergenceReport`, and `LiveReadinessProposal`.
- Added tests proving the contracts validate prerequisite evidence and proposal shape
  while keeping `execution_authority=NONE`, venue connection `NONE`, paper/live orders
  disabled, venue demo/testnet proposals rejected before a later credential gate, and
  backtest-versus-paper divergence classified without activating a paper lane.
- Updated the dashboard read model, AD, and type catalog to project the contracts as
  `MODELED_INERT` with zero active paper/live records or controls.

## v8.34 — 2026-07-11 — S3/S4 retained readiness artifact

- Added `scripts/build_s3_s4_readiness_artifacts.py` to materialize deterministic,
  probe-only S3/S4 control-plane readiness evidence.
- Retained `artifacts/reports/S3_S4_CONTROL_PLANE_READINESS_2026_07_11.json` and
  `.md`, validating representative S3 gate, S4 gate, paper-lane, divergence, and
  live-readiness probe records while keeping all active record counts at zero.
- Projected the retained report through `/api/v1/dashboard`; execution authority,
  venue connection, paper orders, and live orders remain disabled/NONE.

## v8.35 — 2026-07-11 — S3/S4 operational-drill contracts

- Added `OperationalDrillRecord` contracts for future feed-loss, stale-data,
  engine-crash, manual kill-switch, and credential-revocation drills.
- Extended the retained S3/S4 readiness artifact with PASS/BLOCKED operational-drill
  probes while keeping active drill records at zero and all execution capabilities
  disabled.
- Projected operational drills in the Trading Domain read model as `MODELED_INERT`.

## v8.36 — 2026-07-11 — Synthetic demo-ledger contracts

- Added `SyntheticLedgerSnapshot` and `SyntheticLedgerEntry` contracts for future
  mock-money demo/paper wallet accounting.
- Extended the retained S3/S4 readiness artifact with a synthetic ledger probe:
  initial mock capital, fee debit, final mock balance, `synthetic=true`, and
  `real_money=false`.
- Projected the synthetic demo ledger in the Trading Domain read model as
  `MODELED_INERT`; active synthetic-ledger count remains zero and no wallet/order
  activation path exists.

## v8.37 — 2026-07-11 — Synthetic paper-fill policy contracts

- Added `SyntheticPaperFillPolicy` plus bounded price-source and fee-model enums for
  future deterministic local demo/paper fill assumptions.
- Extended the retained S3/S4 readiness artifact with a synthetic paper-fill-policy
  probe covering midpoint pricing, fixed bps fees, slippage bps, and fill-latency
  ceiling.
- Projected the synthetic paper-fill policy in the Trading Domain read model as
  `MODELED_INERT`; active paper-fill-policy count remains zero and no fill engine,
  wallet mutation, venue route, or order capability exists.

## v8.38 — 2026-07-11 — Synthetic account and portfolio contracts

- Added `SyntheticAccountSnapshot` and `SyntheticPortfolioSnapshot` contracts for
  future mock-money demo account and portfolio projections linked to a synthetic
  ledger.
- Extended the retained S3/S4 readiness artifact with probe account/portfolio
  snapshots while keeping active synthetic-account and synthetic-portfolio counts at
  zero.
- Projected the synthetic account and portfolio read model as `MODELED_INERT`; no
  active balances, wallet mutation, venue route, paper/demo/live order, or real-money
  capability exists.

## v8.39 — 2026-07-11 — Synthetic runtime-risk policy contracts

- Added `SyntheticRuntimeRiskPolicy` and `KillSwitchMode` for future paper/demo
  runtime limits covering capital-at-risk, position notional, daily loss, drawdown,
  and kill-switch requirements.
- Extended the retained S3/S4 readiness artifact with a synthetic runtime-risk-policy
  probe while keeping active runtime-risk-policy count at zero.
- Projected the synthetic runtime risk policy in the Trading Domain read model as
  `MODELED_INERT`; no active risk engine, wallet mutation, venue route, paper/demo/live
  order, or real-money capability exists.

## v8.40 — 2026-07-11 — Restricted credential boundary contracts

- Added `RestrictedCredentialPolicy` and `CredentialPermission` for future S4
  credential-scope records without secret material.
- Extended the retained S3/S4 readiness artifact with a restricted credential-policy
  probe that forbids funds movement and keeps credential material absent.
- Projected the restricted credential policy in the Trading Domain read model as
  `MODELED_INERT`; active credential-policy count remains zero and no venue connection,
  order route, live order, or real-money capability exists.

## v8.41 — 2026-07-11 — Paper operations runbook contracts

- Added `PaperOperationsRunbook` and `PaperRunbookInterventionMode` for future S3
  paper/demo operational discipline.
- Extended the retained S3/S4 readiness artifact with a paper operations runbook probe
  covering heartbeat interval, heartbeat timeout, log retention, manual intervention,
  and runtime-risk-policy linkage.
- Projected the paper operations runbook in the Trading Domain read model as
  `MODELED_INERT`; active runbook count remains zero and no venue route, order
  capability, or execution authority exists.

## v8.42 — 2026-07-11 — Paper operations event-log contracts

- Added `PaperOperationsEventRecord`, `PaperOperationsEventKind`, and
  `PaperOperationsEventSeverity` for future S3 paper/demo operational evidence rows.
- Extended the retained S3/S4 readiness artifact with a heartbeat event probe linked
  to the paper operations runbook probe.
- Projected the paper operations event log in the Trading Domain read model as
  `MODELED_INERT`; active event count remains zero and no venue route, order
  capability, or execution authority exists.

## v8.43 — 2026-07-11 — Paper stability report contracts

- Added `PaperStabilityReport` and `PaperStabilityStatus` for future S3 exit stability
  evidence across observation windows, uptime, incidents, missed heartbeats, and
  linked divergence/runbook/risk records.
- Extended the retained S3/S4 readiness artifact with a blocked paper-stability probe
  explaining that no active paper lane has run a stability window.
- Projected the paper stability report in the Trading Domain read model as
  `MODELED_INERT`; active report count remains zero and no venue route, order
  capability, or execution authority exists.

## v8.44 — 2026-07-11 — Limited live risk-package contracts

- Added `LimitedLiveRiskPackage` and `LimitedLiveRiskPackageStatus` for future S4
  risk packaging across paper stability, credential boundaries, operations runbook,
  runtime risk policy, capital-at-risk, order-notional limit, daily-loss limit, and
  kill-switch mode.
- Extended the retained S3/S4 readiness artifact with a blocked limited-live-risk
  package probe explaining that S3 paper stability evidence is incomplete.
- Projected the limited live risk package in the Trading Domain read model as
  `MODELED_INERT`; active package count remains zero and no venue route, order
  capability, or execution authority exists.

## v8.47 — 2026-07-11 — Synthetic portfolio-risk policy contracts

- Added `SyntheticPortfolioRiskPolicy` for future S3 demo/paper portfolio caps:
  symbol concentration, correlated exposure, strategy budget, and open-position count.
- Extended the retained S3/S4 readiness artifact with a portfolio-risk policy probe.
- Projected the portfolio-risk policy in the Trading Domain read model as
  `MODELED_INERT`; active policy count remains zero and no risk engine, wallet
  mutation, venue route, order capability, or execution authority exists.

## v8.46 — 2026-07-11 — Live operations event-log contracts

- Added `LiveOperationsEventRecord`, `LiveOperationsEventKind`, and
  `LiveOperationsEventSeverity` for future S4 operational evidence.
- Extended the retained S3/S4 readiness artifact with a live operations heartbeat
  probe linked to the live operations runbook and limited-live risk package.
- Projected the live operations event log in the Trading Domain read model as
  `MODELED_INERT`; active live event count remains zero and no credential access,
  venue route, order capability, or execution authority exists.

## v8.45 — 2026-07-11 — Live operations runbook contracts

- Added `LiveOperationsRunbook` and `LiveRunbookEscalationMode` for future S4
  operational discipline.
- Extended the retained S3/S4 readiness artifact with a live operations runbook probe
  covering heartbeat interval, incident-response target, log retention, escalation mode,
  limited-live-risk-package linkage, and restricted-credential-policy linkage.
- Projected the live operations runbook in the Trading Domain read model as
  `MODELED_INERT`; active runbook count remains zero and no venue route, order
  capability, or execution authority exists.

## v8.48 — 2026-07-12 — Synthetic risk evaluator and fail-closed readiness

- Added explicit synthetic per-strategy budget and market-condition guard contracts.
- Added a pure independent synthetic risk evaluator covering runtime, portfolio,
  strategy, stale-data, spread, venue-health, timestamp, and kill-switch checks.
- Strengthened synthetic ledger snapshots with credit/debit conservation and
  overdraft rejection.
- Prevented paper-stability PASS on an undersized/zero-uptime window, required the
  complete S4 prerequisite chain, and made dashboard readiness projection reject a
  retained artifact whose content hash does not verify.
- Active S3/S4 record counts remain zero; execution authority, venue connection,
  credentials, wallet mutation, and paper/live order capabilities remain absent.

## v8.49 — 2026-07-12 — Synthetic execution and canonical signal reducers

- Added deterministic synthetic fill calculation with adverse slippage, maker/taker
  fees, limit/stop eligibility, and explicit non-fill outcomes.
- Added idempotent append-only mock-ledger initialization/change reducers with
  conservation, time-order, currency-initialization, and overdraft guards.
- Added fee-aware long-only spot position projection and ledger-backed synthetic
  account/portfolio equity reconciliation.
- Added canonical RuleTree and signal evaluation for the unambiguous seed indicator
  vocabulary. Donchian now follows its reproduced prior-high/low contract;
  unresolved Supertrend semantics fail closed.
- Dashboard read models expose these services as `AVAILABLE_OFFLINE_INERT`; no active
  synthetic state, order route, credential, venue connection, or execution authority
  exists.

## v8.50 — 2026-07-12 — Computed stability, live evidence resolution, and incidents

- Added signed-money P&L so losing positions can be represented without allowing
  negative balances, fees, notionals, or risk limits.
- Added deterministic divergence-report assembly and heartbeat/incident-derived
  paper-stability evaluation.
- Added cross-record limited-live readiness validation for paper stability,
  credential caps, runbook/runtime references, manual kill switches, risk limits,
  and all required drills.
- Added immutable operational incident open/acknowledge/resolve transitions with
  ownership and post-incident evidence.
- Extended retained readiness and dashboard projections with zero active operational
  incidents. No credential, venue connection, mutation API, order route, or execution
  authority was enabled.

## v8.51 — 2026-07-12 — Gated approval history and durable evidence

- Added typed, expiring human-decision records and immutable approval history with
  exact S3/S4 gate predicates; current S2 transitions cannot reach paper/live states.
- Added a confined append-only SQLite synthetic-evidence ledger with canonical hashes,
  idempotency, concurrent-writer serialization, bounded reads, and integrity checks.
- Resolved Supertrend semantics from primary sources: Hummingbot/pandas-ta bullish
  `+1` plus proximity gating and TradingView bullish `-1` are modeled separately.
- Extended readiness/dashboard projections with the available inert evidence ledger
  and zero active evidence events. No execution, credential, venue, wallet mutation,
  scheduler, paper order, or live order capability was enabled.

## v8.52 — 2026-07-13 — Supervisory truth restoration and execution quarantine

- Added the full-system supervisory baseline and dependency-ordered improvement plan;
  reconciled authoritative architecture, program, product, task, and handoff documents.
- Corrected the DSR non-normality denominator against the primary method source and
  regenerated affected offline diagnostics without inheriting any prior PASS claim.
- Marked production G10 `METHOD_BLOCKED` until effective independent trials, complete
  search lineage, and selection-metric alignment are defensible; reclassified the MTF
  one-series statistic as PSR-versus-zero rather than DSR.
- Quarantined every authenticated Bybit demo transport before network access, tightened
  demo origin/environment/permission checks, and made fill/flatten reconciliation fail
  closed. Historical demo activity is retained as an unauthorized governance probe,
  not current connectivity or approval.
- Reclassified funding-carry paper claims as static synthetic cost stress, not empirical
  execution, G12, or validation evidence. No strategy became promotion-eligible.
- Added package-integrity verification to `make check`, standardized demo environment
  names and ignore rules, and regenerated all changed controlled-file hashes below.
- Added future-safe, content-addressed raw/REST provenance plus a deterministic reconstructed
  manifest for the current 69-table normalized-multi snapshot; the 69 small REST source pages
  are included with the deliverable, while historical lineage limits remain explicit.
- Changed future public/signal/universe research runners to train-only parameter selection with
  one frozen context-level holdout evaluation and fail-closed method status.
- Registered the funding-carry hypothesis in the canonical strategy spine as deliberately
  non-executable `VALID_WITH_AMBIGUITIES`, with pinned parameters, failure modes, and gates.
- Aligned G10 candidate selection, both CSCV halves, and DSR on non-annualized per-bar
  Sharpe; retained correlation-derived family-scope effective trials under DSR Appendix 3
  where defined, while keeping the missing upstream hierarchy `METHOD_BLOCKED`.
- Added backward-compatible research-only multi-leg canonical identity with explicit
  long-only evaluator rejection, plus pure Decimal carry accounting fixtures for deployable
  capital, spot/perp basis, funding, fees, isolated margin, missing data, and endpoint shocks.
- Added deterministic open/settle/rehedge/close carry lifecycle reduction with capital
  conservation, strict timestamps, terminal margin breach, and no venue semantics.
- Preregistered the next bounded 66-trial baseline G10 reproduction and added a fail-closed
  provenance envelope for all future substantive strategy-research artifacts.
- Superseded obsolete 2026-07-11 G10 artifacts/continuation instructions and the pre-demo
  2026-07-10 live-unreachability review; the coding-agent SSOT now routes to the supervisor
  plan and requires a fresh formal security review before HG-3/S3.
- Current execution authority and venue connection remain `NONE`; all human S3/S4 gates
  and live-capital prohibitions remain unchanged.
- Added `docs/supervisor/FINAL_SUPERVISORY_REPORT_2026-07-13.md` with the verified
  conclusion, validation results, residual classifications, human decisions, and next phase.

## v8.53 — 2026-07-13 — Preregistered G10 campaign execution contract

- Added a local-only preflight/run/verify wrapper that binds the 66-trial campaign to a
  clean Git commit, exact file hashes, a pinned retained lab, the actual vectorbt environment,
  immutable per-family all-trial inputs/results, and validated provenance sidecars.
- Froze the campaign's exact F1/S0 fee-only cost model, within-family selection scope,
  16-slice/11-tail-bar CSCV policy, and missing upstream family-admission boundary.
- Classified the retained grids as legacy current-close accelerator proxies rather than
  canonical next-open strategy implementations; the campaign remains diagnostic-only.
- Added the missing `pyarrow==24.0.0` dependency to the retained vectorbt environment freeze.
- Executed the frozen campaign from clean commit `7782752`; immutable evidence records B2/B4
  numeric FAIL, B3 `METHOD_BLOCKED`, overall G10 `METHOD_BLOCKED`, and no selected winner.
- Added the controlled human-readable campaign report and retained the local-only rerun
  limitation: the exact hashed dataset and environment are not Git- or DVC-distributed.

## v8.54 — 2026-07-13 — Canonical V2 formal-run freeze

- Added a portable 66-archive Binance BTCUSDT 5m source manifest and an offline-first
  restore command that reproduces the exact 577,803-row Parquet byte hash; public fetching
  is explicit and every archive is SHA-256 pinned.
- Added a separate canonical-rule B2/B3/B4 extractor with 67 frozen trials, persistent B2
  eligibility, population-variance B3, prior-high B4, gap-reset indicators, position-aware
  conflicts, and exact-adjacent next-open fills.
- Added the complete F0/S0 through F2/S3 cost surface, per-trial executed notional and
  turnover, five expanding historical pseudo-OOS folds, plus family and campaign-wide
  PBO/DSR inputs.
- Added a governed formal-run/verify/recompute lifecycle, exact code/data/spec/environment
  pins, primary-source method ledger, and a sealed post-2026-07-14 prospective holdout.
- Disclosed that a pre-freeze implementation smoke touched the full historical dataset;
  therefore V2 is a reproducibility/conformance diagnostic, not unseen evidence. The future
  holdout is the only prospective test. No strategy, venue, order, or execution authority
  was enabled.
- Executed the formal campaign from clean commit `6bac8bf` and retained 13 immutable,
  content-addressed evidence files. A second complete run reproduced the all-trial inputs
  byte-for-byte.
- Recorded the negative result: B2/B4 fail, B3/campaign-wide remain method-blocked on
  retained zero-trade correlations, all active exact controls lose effectively all capital
  at F1/S1, and historical walk-forward does not rescue them. Further B2/B3/B4 grid
  expansion is closed; the future holdout remains sealed.

## v8.55 — 2026-07-13 — Post-V2 family selection V1

- Added the source-backed `FAMILY-SELECT-V1` dossier comparing exactly funding/basis
  carry, long-only Spot cross-sectional momentum, and volatility-managed Spot exposure.
- Recorded D-052 `NO_GO`: every candidate fails at least one non-compensable admission
  gate for point-in-time data, full capital/risk semantics, canonical ownership, or clean
  search lineage. No prior result was inherited and no parameter evaluation ran.
- Kept Task 1 active for a new maximum-three-family source/data-feasibility cycle; Task 2,
  StrategyVersion creation, implementation, bots, venues, orders, and all execution
  authority remain blocked.
- Preserved the V2 prospective holdout seal and all authenticated-transport quarantines.

## v8.56 — 2026-07-13 — UTC-weekday admission and preregistered campaign freeze

- Added official-source platform validation research and the second bounded family dossier.
  D-053 admits UTC-weekday BTCUSDT Spot exposure without observing local family performance;
  stablecoin reversion and halving exposure are rejected.
- Added an exact offline-verifiable 48,154-row BTCUSDT 1h data package, upstream source snapshot,
  raw/archive/logical hashes, drift tests, and explicit UTC/gap semantics.
- Added the calendar canonical family primitive and seven immutable StrategyVersion identities,
  with hand-derived timing, cost, price-invariance, gap-expiry, and fail-closed gap-exit tests.
- Added an independent Decimal ledger, vectorbt accelerator, and the unrun
  `CALENDAR-UTC-G1-G11-V1` campaign with six costs, fixed chronology, clock stresses,
  benchmarks, PBO/DSR, hard gates, exact pins, and no-rescue rules.
- Offline preflight passes. No historical calendar score, sealed V2 holdout, bot, venue,
  credential, order, paper/demo/live state, promotion, or execution authority was accessed.

## v8.57 — 2026-07-13 — UTC-weekday campaign rejection

- Executed the immutable seven-weekday campaign from clean commit `ecdfb3b`; a second complete
  run reproduced the preregistration, Decimal results, and vectorbt results byte-for-byte.
- Selected Wednesday on development data. Reference/vectorbt parity passed and chronological
  segments were positive, but G5/G8/G9/G10 failed: hard stress `-40.74%`, max drawdown
  `-41.29%`, Sharpe below buy-and-hold, PBO `0.7594`, and DSR `0.3012`.
- Recorded the red-team protocol finding that reserve metrics were computed before selection,
  invalidating untouched-reserve status even though selection consumed development only. Also
  retained the missing Freqtrade/Nautilus conformance gap.
- D-054 closes the exact context without rescue. No bot, venue, credential, order, paper/demo/live
  state, human gate, promotion, or execution authority was activated.

## v8.58 — 2026-07-13 — Funding-pressure family and data freeze

- Added `FAMILY-SELECT-V3`, comparing exactly funding pressure, small-alt lead/lag, and options
  VRP from current sources without computing local family performance.
- D-055 admits only a funding-feature/unlevered-BTCUSDT-Spot long/cash mechanism; it creates no
  perpetual, carry, leverage, margin, short, liquidation, venue, or order dependency.
- Froze all 66 monthly funding archives, 6,021 exact-millisecond observations, and the existing
  48,154-row Spot package behind content hashes and strict next-open semantics.
- Added an offline verifier and deliberate byte, schema, and timestamp drift tests. Every retained
  funding event has a strictly later expected Spot open. Scoring remains prohibited until the
  canonical campaign is cleanly committed.

## v8.59 — 2026-07-13 — Funding-pressure immutable campaign freeze

- Added a canonical point-in-time funding observation/state projection with exact-millisecond
  availability, complete rolling warm-up, strict threshold equality, next-open, pending-expiry,
  and held-gap-exit semantics.
- Froze 12 content-derived StrategyVersions and independent Decimal, vectorbt, Freqtrade 2026.6,
  and Nautilus 1.230.0 role implementations behind exact environment and code hashes.
- Added a physical two-phase runner: development selection is written and hashed before any
  validation/reserve/full/period evaluation. A deliberate early phase-two call fails closed.
- D-056 freezes all costs, chronology, benchmarks, sample/tail/clock/PBO/DSR gates, and no-rescue
  rules. Offline preflight and focused tests pass; historical family performance remains unseen.

## v8.60 — 2026-07-13 — Funding-pressure V1 operational abort and V2 freeze

- Recorded V1's fail-closed worker import abort after development reference computation began but
  before selection, validation, reserve, full-history, period evaluation, or campaign output.
- Closed V1 without a strategy verdict. No result was inspected or used to alter the roster.
- Added V2 as a content-hash inheritance overlay whose only change bootstraps the repository root
  in vectorbt, Freqtrade, and Nautilus worker processes before importing the shared data loader.
- Worker import smoke, offline preflight, safety checks, and selection-barrier tests pass. No bot,
  venue, credential, order, paper/demo/live state, or execution authority was activated.

## v8.61 — 2026-07-13 — Funding-pressure V2 abort and UTC-normalized V3 freeze

- Closed V2 before selection after pandas 3 rejected mixed naive/UTC-aware segment slice bounds.
- Froze V3 with only explicit UTC parsing of the already-frozen segment strings in external
  workers. V1 strategy/statistical terms remain inherited by hash; reserve remains untouched.

## v8.62 — 2026-07-13 — Funding-pressure campaign rejection

- Completed V3 with a verified select-before-reserve artifact and selected contrarian/3/0.0001.
- Rejected the family: zero 2024 trades, two losing reserve trades, DSR 0.8235, and one Nautilus
  trial-parity failure cause G4/G5/G6/G7/G8/G10/G11 failure.
- D-059 closes the context without rescue. No bot, venue, order, paper/demo/live state, human gate,
  promotion, or execution authority was activated.

## v8.63 — 2026-07-13 — Bitcoin transaction-activity family and data freeze

- Added a fourth exactly-three-family source dossier. D-060 rejects stablecoin supply and miner
  recovery, admitting only delayed finalized L1 confirmed-transaction shocks without scoring.
- Froze the official 2,187-observation `n-transactions` response, 2,004 campaign observations,
  exact bytes/logical records, one known source gap, and two-full-day availability lag.
- Added offline verification and deliberate byte, schema, gap, and lag drift tests. All expected
  campaign decisions map to a strictly later retained Spot open.
- Froze a 12-trial activity-side/baseline-window/holding-period pulse roster. No bot, venue,
  credential, order, paper/demo/live state, or authority was activated.
