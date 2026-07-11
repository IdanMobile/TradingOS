# Trading Intelligence OS — Missing and Open Items

Last updated: 2026-07-11

## Open research gaps (tracked in detail in `research/RESEARCH_GAP_MATRIX.md`)

- RG-05 public-source venue availability slice is complete for the authorized
  2026-07-11 recheck. Human/account-specific venue eligibility, permissions,
  terms, product availability, and fee-tier checks remain before S3 paper venue
  selection.
- RG-07 G10 PBO/DSR candidate-specific integration and independent recomputation
  before production G10 activation. Synthetic method fixtures now pass.

## Current environment/coverage constraints

- BTC-only B2 Freqtrade/Hummingbot parity remains non-identical but is explained and
  retained as execution/order-state plus missing-data behavior; it is not a P&L fixture.

Docker was made available on 2026-07-11. LEAN bounded local Docker execution is
now retained for B1-B4 x `{F0/S0,F1/S1}` with one B1 F0/S0 determinism rerun.
Evidence: `artifacts/bakeoff/lean/STATUS.md`.
Hummingbot full-history follow-up is now runtime/throughput blocked: B2 BTCUSDT
F1/S1 consumed CPU but hit the lane's initial 1800 second timeout without
`raw.json`, and a cached full-history retry still hit the 3600 second timeout
while writing a clean timeout manifest and stopping the named container. Evidence:
`artifacts/reports/HUMMINGBOT_FULL_HISTORY_TIMEOUT_2026_07_11.md`.
The bounded Hummingbot capability/regression lane is now complete: BTCUSDT 30-day
B1-B4 x `{F0/S0,F1/S1}` x `{run1,run2}` completed, normalized, fee-audited, and
byte-deterministic. Evidence:
`artifacts/reports/HUMMINGBOT_PRODUCTIONIZATION_STEP_2026_07_11.md`.
NautilusTrader remains bounded-window evidence; full-history parity and latency/fill
evidence remain open. Deferred adapters and normalized artifacts are retained as
evidence-only/deferred assets under D-037.

## Open S2 evidence and exit items

0. Repo-wide open-marker audit is retained at
   `artifacts/reports/OPEN_MARKERS_AUDIT_2026_07_11.md`. Stale architecture/report
   wording for bounded LEAN/Hummingbot evidence was reconciled; remaining markers are
   classified as throughput/scope tracks, validation blockers, or human/credential/S3
   gates. The supervised Hummingbot full-history retry is now closed as a
   documented throughput timeout, not an active running job.
1. Real retained Research Lab evidence now exists: LAB-799 completed and the persisted
   jobs/dashboard projection show three succeeded `RESEARCH_LAB_V0` jobs plus the
   six-hour offline schedule. Continue the next S2 evidence cycle from the recorded
   blockers; do not treat the batch or scheduler as strategy approval. A follow-on
   seed-candidate cycle also retained 16 trials for the two reproduced QuantConnect seed
   specs and selected no winner. A 2026-07-11 refresh after G10 fixture evidence
   produced `LAB-f99dcc214f377ecca4710bbb41d445c8331d2a1b06f93931ed1c88bdf3af5924`,
   again with 66 trials, no winner, and `execution_authority=NONE`.
2. Strategy validation remains `INCOMPLETE_NOT_APPROVABLE`: B2 is rejected for paper,
   G4 remains WARN, and G10 remains inactive despite passing synthetic method
   fixtures because candidate-specific integration and independent recomputation
   are still required.
3. Preserve and close only with evidence the remaining Hummingbot, NautilusTrader,
   and cross-engine signal/order/fill semantic gaps described above.
4. S2 exit/HG-3 remains blocked: the verification package is retained, but the
   requirement audit says not to prepare HG-3 because no strategy is complete,
   approvable, or promotion-eligible.

## Resolved authorized decision slices (2026-07-11)

- `T-001-03` official-source Kraken/Coinbase Israel availability recheck is
  retained in `artifacts/reports/VENUE_ISRAEL_SOURCE_RECHECK_2026_07_11.md`.
  Kraken is not demoted on the checked public-source evidence; Coinbase has
  Israel identity-document support, but exact account/product/API eligibility is
  still human/S3-gated.
- `T-020-01`/`T-020-02`/`T-020-03` design-only expansion work is retained in
  `artifacts/reports/FUTURE_MARKET_EXPANSION_DESIGN_REVIEW_2026_07_11.md`.
  Implementation remains deferred to S3+.
- `T-017-05` was rechecked after an operator decision, but credentials are not
  visible in the current environment. Evidence:
  `artifacts/reports/AI_COST_TELEMETRY_CREDENTIAL_RECHECK_2026_07_11.md`.

## Resolved bounded S2 research-asset evidence

- ResearchAsset registry/backfill for the bounded S2 slice is implemented and tested:
  `research/RESEARCH_ASSETS_V1.json` contains 8 retained RA records with freshness,
  dependencies, consumers, human-review flags, reverify triggers, and existing
  source/quality evidence refs. `ResearchAssetRegistry` enforces invalid-without-evidence,
  duplicate/unknown/cyclic graph rejection, freshness filtering, and deterministic digest.
  Evidence: `src/tios/research_assets/assets.py` and `tests/test_research_assets.py`.
- RA cost amortization is queryable from the same registry via consumer counts and
  cost-per-consumer projection. Current retained local evidence has zero external cost.

## Resolved bounded S2 observability evidence

- Bounded S2 observability is complete without a general stack: JSON artifacts, SQLite
  job rows, environment mode fields, and dashboard read models are the structured
  operational records. Prometheus/Grafana and OTel are rejected for the current
  single-operator local lab; AI cost telemetry stays credential-gated. Evidence:
  `artifacts/reports/OBSERVABILITY_BOUNDARY_REPORT.md`.

## Resolved bounded S2 dictionary/ontology evidence

- Bounded dictionary/ontology seed is implemented and tested: `research/DICTIONARY_CONCEPTS_V1.json`
  contains 16 `CON-*` concepts covering S1/S2 evidence vocabulary, FIBO URI provenance
  where applicable, local project-contract definitions, and explicit gap rows for full
  FIBO import, venue-specific meanings, and scraped definitions. `ConceptRegistry`
  validates graph/source integrity, rejects embedded strategy parameter values, and
  exposes SQLite FTS5 search. Evidence: `src/tios/knowledge/concepts.py` and
  `tests/test_dictionary_concepts.py`.
- The dashboard projects the same concept registry through a read-only Dictionary view,
  closing the bounded global-search slice without adding a write path.

## Resolved bounded S2 dashboard backlog evidence

- The bounded dashboard backlog is closed for the current S2 scope: the full console
  rewrite, entity-detail layout, and richer comparisons UI are rejected until documented
  reopen triggers occur; global search is done through the Dictionary view; approvals UI
  remains human-gated and unauthorized. Evidence:
  `artifacts/reports/DASHBOARD_BOUNDARY_REPORT.md`.

## Resolved AI provider source re-check evidence

- RG-08 is closed for pre-paid-benchmark planning: official OpenAI and Google AI
  Developers sources now capture GPT-5.6 pricing, Gemini 3.x context/pricing, and Google
  model deprecation handling. Real-provider runs remain credential/spend/human-review
  gated. Evidence: `artifacts/reports/AI_PROVIDER_SOURCE_RECHECK_2026_07_10.md`.

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
  (rechecked 2026-07-11 without printing values; intake gate's "add later" AI-key
  disposition still holds). T-011-01..04 and
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
