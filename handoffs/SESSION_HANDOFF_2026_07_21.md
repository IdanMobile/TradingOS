# Session handoff — 2026-07-21 (v8.118, D-111)

Written before a context compaction. This is the authoritative catch-up for the next
session; DECISION_LOG.md D-107 through D-111 and PACKAGE_CHANGELOG.md v8.110–v8.118
carry the full detail.

## Where the project stands

**All seven data-backed strategy families have now been searched once** under
pre-registration, trial budgets, and hierarchy-wide DSR deflation. The ledger holds
**234 trials across 7 families** (`artifacts/validation/trial_budget/`). Results:

| # | Family | Verdict | Note |
|---|--------|---------|------|
| 1 | FAM-VOL-CONTRACTION-BREAKOUT-V1 | FAIL | overfit signature (D-109) |
| 2 | FAM-TAKER-IMBALANCE-V1 | FAIL | negative even in-sample (D-110) |
| 3 | FAM-MVRV-DISLOCATION-V1 | FAIL | first promising negative, DSR 0.76 (D-110) |
| 4 | FAM-TX-ACTIVITY-V1 | FAIL | overfit signature (D-111) |
| 5 | FAM-CROSS-VENUE-PREMIUM-V1 | FAIL | negative in-sample (D-111) |
| 6 | FAM-CFTC-POSITIONING-V1 | **PASS-ELIGIBLE → RETRACTED (D-112)** | corrected to INSUFFICIENT_ACTIVITY, 1 validation trade |
| 7 | FAM-FUNDING-PRESSURE-V1 | FAIL | zero validation trades (D-111) |

CFTC selected variant: net noncommercial share of OI, 1.5σ below 26-week norm → long
168h; train +0.024, validation +0.077 (validation 3× train — recorded as a suspicion,
not a celebration). **No authority created** — G1-G11, independent specialist review,
and prospective evidence still stand before any capital.

**D-112 (2026-07-21) supersedes the CFTC pass above:** an independent methodology audit found the
DSR was computed on total validation bars while the Sharpe covered only in-position bars (F1). The
CFTC PASS-ELIGIBLE rested on a single completed validation trade and is **formally retracted** —
corrected verdict INSUFFICIENT_ACTIVITY. All seven families were re-scored under trade-level
significance (`scripts/rescore_frozen_campaigns.py`); the six other FAILs stand a fortiori. Future
campaigns now use trade-level DSR with a `min_validation_trades` floor. See D-112 for the full
finding set (F1–F6), the corrected methodology, and the unchanged prospective lanes.

Stop rules forbid re-searching any closed family. New information can only come from:
prospective observation, the sealed holdout reads lawful after **2027-01-14**, or a new
family backed by new data.

## Prospective lanes (opened this session, boundaries frozen)

- **MVRV**: `research/PROSPECTIVE_MVRV_DISLOCATION_V1.yaml` +
  `scripts/run_prospective_mvrv_observer.py` (live, keyless CoinMetrics fetch; first row
  recorded in `artifacts/prospective/MVRV-DISLOCATION-V1/observations.jsonl` — source day
  2026-07-18, z +1.41, FLAT). Idempotent per source day; should run daily
  (orchestrator loop or cron). First review earliest 2027-01-17.
- **CFTC**: `research/PROSPECTIVE_CFTC_POSITIONING_V1.yaml` — prereg only; weekly
  fetcher flagged NOT_YET_BUILT (weekly cadence + 8-day availability lag means nothing is
  lost yet). **Next concrete build item.** First review earliest 2027-01-21.

## Gate status at handoff

`make check` went red mid-session on **formatting only** — 10 files from a parallel
session (decision_inspector, backtest_attribution, decision_intelligence ×2, arrow_time,
2 probe scripts, 3 tests). This session ran `ruff format` on exactly those files
(whitespace-only, none manifest-listed) plus one more that appeared mid-session
(`scripts/run_backtest_loss_attribution.py`) and re-ran the gate:
**GREEN — 1136 passed, 29 deselected (slow band), ~60s.** If it goes red again, the
cause is almost certainly further parallel-session edits, not the v8.118 work — v8.118's
own files pass ruff/format clean, and mypy gates only `src/tios` (scripts are out of
scope by config).

A parallel session is/was active: it extended IMMUTABLE_PATHS (self_modification.py),
added the decision-intelligence modules and B2 trace artifact, and had missed manifest
regeneration on `scripts/verify_*.py` + `trading_domain/__init__.py` (fixed here per the
D-030 rule, noted in v8.118 changelog). Treat its files as intentional; do not revert.

## Open items (nothing else pending from the operator's last approvals)

1. DONE 2026-07-21 — Build the CFTC weekly prospective fetcher (publicreporting.cftc.gov,
   keyless) before the next report's availability date.
   `scripts/run_prospective_cftc_observer.py`, live-verified exit 0.
2. DONE 2026-07-21 — Wire the MVRV observer into the orchestrator's daily loop (it was
   manual). `src/tios/ops/orchestrator.py::observe_prospective_observers()`.
3. Offered but never confirmed by the operator: −15% disaster-stop + venue-resting stop
   order for the demo lane (analysis in D-110-era notes: median MAE −2.67%, −15% never
   hit in 259 trades).
4. Operator-side, standing: security-test diff review (parked ledger), operator
   attestation fill (`ops/OPERATOR_ATTESTATION.example.json`), OpenAI billing (operator
   said ignore).
5. Parked items ledger: `artifacts/driver/parked_items.jsonl` — all honest blockers with
   causes; nothing new parked this session.

## Conventions the next session must keep

- Never run two pytest suites concurrently (they starve each other; gate ~90s fast,
  30-40min full via `make check-full`).
- Every controlled edit to a manifest-listed file → rehash
  `PACKAGE_INTEGRITY_MANIFEST.md` + changelog entry in the same change.
- Tests must assert structural properties, not pinned task states/IDs (four stale-test
  incidents this project).
- Campaign discipline: preregister → train-only search → freeze → single validation
  read → deflate against `global_trial_count` → artifact; promotable is always False;
  no rescue on fail.
- Formatter may rewrite files between reads — re-read exact text before Edit.
