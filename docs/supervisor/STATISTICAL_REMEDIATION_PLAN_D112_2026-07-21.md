# Statistical Remediation Plan — D-112 (2026-07-21)

Status legend: [DONE] complete · [RUNNING] delegated agent executing · [PENDING] queued · [OPERATOR] awaiting operator decision

Owner: session orchestrator (Fable 5, brain-only supervisor mode). All implementation
delegated to subagents per operator directive. This file is the authoritative plan;
DECISION_LOG.md D-112 records the decision, PACKAGE_CHANGELOG.md v8.120 the change.

## Trigger

Operator asked whether the homegrown validation infrastructure might contain a
"wrong divergence" vs community backtesting practice. An independent red-team audit
(Opus architect, read-only, holdout/prospective-outcome firewalled) found six
findings (F1–F6); a bit-for-bit verification recompute confirmed the material one.

## Findings (audit 2026-07-21)

- **F1 (MATERIAL, optimistic)** — `src/tios/validation/campaign.py:192` fed
  `sample_count=len(split.validation)` (total bars) to the DSR while the per-bar
  Sharpe was computed only over in-position bars. Inflation factor
  `1/sqrt(in-position fraction)`.
- **F2 (MATERIAL, optimistic)** — long identical 0.0 mark-bar runs during 168h/672h
  holds; no serial-correlation adjustment; honest n ≈ independent trade count.
- **F3a (MATERIAL, governance)** — `pbo_max: 0.5` pre-registered in every campaign
  but PBO never computed on the recorded path.
- **F3b (MATERIAL, conservative)** — raw hierarchy trial count used with no
  correlation haircut; `implied_independent_trials` unused on the recorded path.
- **F4 (MINOR)** — nested walk-forward folds computed but `fold.test` never scored;
  dead code with `gap_bars=0`.
- **F5 (MATERIAL, design)** — zero-validation-trades campaigns recorded as FAIL with
  no minimum-activity guard (funding campaign's FAIL is hollow).
- **F6 (MINOR)** — population vs sample variance inconsistency between
  `_per_bar_sharpe` and `sharpe_variance_from_trials`.

## Verification (bit-for-bit recompute, scratchpad-only, no ledger writes)

FAM-CFTC-POSITIONING-V1 recorded PASS-ELIGIBLE reproduced exactly (train
0.024257871728695 / validation 0.077151674981046 / DSR 0.999551, hierarchy 216).
Honest recompute: validation split 7,630 bars, evaluator produced 169 returns
(in-position fraction 2.21%), **one** completed trade. Corrected z 3.32 → 0.49,
DSR 0.9996 → 0.689 → **verdict flips to FAIL**; at trade level (n=1) no
significance was ever computable. Six other family FAILs stand a fortiori
(bias was optimistic). Affected evaluators: v3 (all three) + v2 taker/mvrv;
dense-return scripts unaffected.

## Plan

1. **[DONE]** Independent red-team audit of validation core (Opus architect).
2. **[DONE]** Bit-for-bit verification recompute of the CFTC verdict (Sonnet,
   scratchpad script `f1_f2_audit.py`; no repo writes, no holdout, no
   prospective outcomes).
3. **[DONE]** Governance check: `campaign.py`, `multiple_testing.py`, `splits.py`,
   campaign scripts are NOT immutable-protected and NOT manifest-listed; operator
   authorization for the change recorded via session directive 2026-07-21.
4. **[DONE]** Core fix (Opus implementer) — landed in campaign.py:
   trade-level significance via score_trade_significance() (n = completed
   trades), fail-closed sample-count identity guard, min_validation_trades
   (default 10) → INSUFFICIENT_ACTIVITY verdict, pbo_max REMOVED (honest
   absence chosen over unenforced declaration; runner retains no per-slice
   stats so CSCV is disproportionate), correlation haircut via
   implied_independent_trials (clamped so it never lowers the bar), dead
   nested-fold code deleted, sample variance consistent. Six evaluators
   across v2/v3/first-budgeted scripts now return TrialScore with trade
   returns; frozen selections reproduce bit-for-bit. Regression tests added
   (tests/test_campaign.py). ruff/mypy clean, pytest 1146 passed.
   Original sub-plan:
   a. Verdict-deciding DSR/z computed on trade-level returns, n = completed
      non-overlapping trades; per-bar Sharpe demoted to descriptive.
   b. Fail-closed identity guard: sample_count fed to DSR must equal the length
      of the series the Sharpe was computed on.
   c. Min-activity guard: pre-registered `min_validation_trades`; below floor →
      verdict `INSUFFICIENT_ACTIVITY`, no DSR claim; n<2 never attempts a Sharpe.
   d. F3a: enforce PBO or remove `pbo_max` from the schema with documented
      rationale (implementer chooses honest-minimal, justifies).
   e. F3b: correlation haircut via `implied_independent_trials`, deflation stays
      hierarchy-wide.
   f. F4: delete dead nested-fold scoring or wire `fold.test` meaningfully.
   g. F6: consistent sample variance (÷n−1).
   h. Regression tests (structural): identity guard, insufficient-activity path,
      haircut applied.
5. **[DONE]** Corrected re-score executed (`scripts/rescore_frozen_campaigns.py`,
   artifacts in `artifacts/validation/campaigns/corrections/`). Final honest
   verdicts: CFTC PASS-ELIGIBLE → **INSUFFICIENT_ACTIVITY** (1 trade);
   funding and vol-contraction → INSUFFICIENT_ACTIVITY (0 and 7 trades);
   tx-activity, cross-venue, taker, MVRV → FAIL (corrected z −2.36 / −0.05 /
   −2.35 / −0.10). **Zero passes; no family moved toward a pass.**
   Vol-contraction input data had drifted under a parallel session; re-scored
   on committed HEAD, non-reproduction recorded transparently in its artifact
   (decisive FAIL invariant to the drift); other six reproduced exactly.
6. **[DONE]** D-112 appended to DECISION_LOG.md: findings F1–F6, verification
   numbers, formal retraction, corrected methodology in force, both prospective
   lanes continue (CFTC lane now hypothesis-generating; 2027 reviews apply
   corrected statistics).
7. **[DONE]** PACKAGE_CHANGELOG v8.120 entry and handoff retraction note landed.
   Gate was initially red at the integrity step because the D-112 append changed
   hash-listed DECISION_LOG.md — the D-030 sanctioned-regeneration case; the
   manifest row was rehashed (old 1a7aaf66… → new 66a25f98…), version line
   bumped to v8.120, changelog bullet added. Full 452-row manifest sweep found
   no other drift. **Final gate: `package integrity: PASS` — 1146 passed,
   29 deselected, 54.29s, ruff/format/mypy clean.**
8. **[DONE]** Trace the three not-yet-verified custom-DSR scripts for the same
   bug (Sonnet, read-only): all three **CLEAN** — `run_g10_candidate.py` and
   `run_canonical_baseline_campaign.py` use vectorbt dense per-bar returns with
   `sample_count == len(returns)` by construction (the canonical baseline even
   asserts `bars_total == sample_count == dataset rows`, failing closed);
   `run_seed_candidate_g10.py` builds a dense local equity curve including cash
   bars. No PASS-like verdicts exist among their recorded artifacts
   (all FAIL/METHOD_BLOCKED). Damage radius confirmed limited to v2/v3 sparse
   evaluators; no D-113 required.
9. **[DONE]** Close-out: statuses updated, gate verified green, step 8 found all
   three custom-DSR scripts CLEAN so no D-113 was needed. The 24/7 orchestrator
   loop was found not running during close-out and was restarted
   (2026-07-21 ~14:30 local, `make orchestrator` detached, PID logged to
   `artifacts/orchestrator/loop_stdout.log`) so the wired prospective observers
   cycle daily.
10. **[DONE]** Post-remediation state summary delivered to operator 2026-07-21.
    Final honest research state: 7 families searched, 0 passes
    (4 FAIL, 3 INSUFFICIENT_ACTIVITY), CFTC PASS-ELIGIBLE retracted (D-112).
    Forward evidence paths: two prospective lanes (observers automated),
    lawful holdout reads after 2027-01-14, or new families with new data.

## Follow-ups outside this remediation (tracked, not blocking)

- **[OPERATOR]** New-family scouting: survey community strategy libraries as a
  hypothesis source (ideas only; evidence only ever from in-repo pre-registered
  campaigns). Offered 2026-07-21, awaiting operator go/no-go.
- **[OPERATOR]** Demo-lane −15% disaster-stop + venue-resting stop order
  (MAE analysis: median −2.67%, −15% never hit in 259 trades). Offered earlier,
  never confirmed.
- **[PENDING]** Differential-testing backlog item: cross-check the campaign
  evaluator against an independent implementation (e.g. vectorbt) on synthetic
  data to reduce single-implementation risk (audit's residual concern).

## Invariants this plan must not break

- No trial-ledger writes outside pre-registered campaigns; re-scoring is a
  correction of recorded selections, never a rescue or re-search.
- No reads of `artifacts/holdout/`, `artifacts/sealed/`, post-2026-07-14 CFTC
  outcomes, or post-2026-06-28 MVRV outcomes.
- Immutable paths untouched (`self_modification.py` list); manifest edited only
  with same-change rehash per D-030.
- Stop rules stand: no family re-search; forward evidence = prospective lanes,
  lawful holdout reads after 2027-01-14, or new families with new data.
