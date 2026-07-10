# Trading Intelligence OS — Missing and Open Items

Last updated: 2026-07-10

## Open research gaps (tracked in detail in `research/RESEARCH_GAP_MATRIX.md`)

- RG-05 Kraken/Coinbase Israel availability (before S3; Coinbase demoted provisionally).
- RG-07 G10 PBO/DSR estimator and known-answer validation before G10 activation.
- RG-08 OpenAI/Gemini primary-source pricing + context windows (before paid benchmark runs).

## Current environment/coverage constraints

- BTC-only B2 Freqtrade/Hummingbot parity remains non-identical but is explained and
  retained as execution/order-state plus missing-data behavior; it is not a P&L fixture.

Docker is currently stopped, so LEAN execution and missing Hummingbot B3/B4 runs
cannot proceed in the present environment. NautilusTrader remains bounded-window
evidence; full-history parity and latency/fill evidence remain open. Deferred adapters
and normalized artifacts are retained as evidence-only/deferred assets under D-037.

## Open S2 evidence and exit items

1. Real retained Research Lab evidence now exists: LAB-799 completed and the persisted
   jobs/dashboard projection show three succeeded `RESEARCH_LAB_V0` jobs plus the
   six-hour offline schedule. Continue the next S2 evidence cycle from the recorded
   blockers; do not treat the batch or scheduler as strategy approval. A follow-on
   seed-candidate cycle also retained 16 trials for the two reproduced QuantConnect seed
   specs and selected no winner.
2. Strategy validation remains `INCOMPLETE_NOT_APPROVABLE`: B2 is rejected for paper,
   G4 remains WARN, and G10 is a deferred method candidate requiring validated
   estimators and known-answer fixtures.
3. Preserve and close only with evidence the LEAN, Hummingbot, NautilusTrader, and
   cross-engine signal/order/fill semantic gaps described above.
4. S2 exit/HG-3 remains blocked: the verification package is retained, but the
   requirement audit says not to prepare HG-3 because no strategy is complete,
   approvable, or promotion-eligible.

## Resolved S2 verification evidence

- Clean-checkout/restore/replay evidence now passes for DVC fresh-checkout replay,
  MLflow artifact restore, SQLite jobs DB logical backup/restore, retained artifact
  hash restore, LAB-799 no-winner status, and validation non-approvability. Evidence:
  `artifacts/reports/S2_RESTORE_REPLAY_REPORT.md` and
  `artifacts/quality/s2_restore_replay.json`.
- S2 live-unreachability evidence passes. Evidence:
  `artifacts/reports/S2_LIVE_UNREACHABILITY_REPORT.md`.
- S2 requirement audit is complete and blocks exit/HG-3 on evidence grounds. Evidence:
  `artifacts/reports/S2_REQUIREMENT_AUDIT.md`.

## Human-only before live trading

1. Exact Israel/operator account eligibility for selected venue.
2. Exact product availability in operator account.
3. API trading permissions.
4. Current automated-trading terms.
5. Current fee tier.
6. Funding/deposit/withdrawal path.
7. Credential isolation and revocation process.
8. Capital amount and maximum acceptable drawdown.
9. Tax/accounting workflow.
10. Final human approval.

## Deferred until justified

- paid tick/order-book data purchase;
- perpetual futures;
- leverage;
- US stocks/ETFs;
- on-chain data;
- social sentiment;
- news vendor selection;
- portfolio optimizer;
- full risk engine;
- mass strategy scraping;
- production deployment;
- autonomous AI trade path;
- full ontology ingestion;
- final 27-page dashboard implementation.

## Credential- and human-gated AI work

- T-011-05 (AI benchmark first real runs) is deferred: no `ANTHROPIC_API_KEY` /
  `OPENAI_API_KEY` / `GOOGLE_API_KEY` is configured in this environment
  (intake gate's "add later" AI-key disposition still holds). T-011-01..04 and
  T-011-06 are complete on the null provider; see
  `artifacts/reports/AI_BENCHMARK_SEED_REPORT.md`. Unblock by configuring one
  provider credential, then run controlled-mode Mode A per
  `benchmarks/ai_agent/FROZEN_BENCHMARK_SUITE_V1.md`.
- Judge calibration set (`benchmarks/ai_agent/calibration/calibration_set.json`)
  is frozen but `review_status: PENDING_HUMAN_REVIEW` — needs an operator to
  review samples and record `reviewer`/`reviewed_at` (T-011-04 human-approval
  requirement).

## Re-verification required

Before S3/S4 implementation or live use recheck:
- exchange APIs and changelogs;
- provider model versions/pricing;
- data provider pricing/licensing;
- engine versions/deprecations;
- venue fees;
- account eligibility.
