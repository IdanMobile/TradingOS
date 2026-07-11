# Initiative 01 — Research Completion (S0/S1, parallel)

Each task closes an RG-xx row in `research/RESEARCH_GAP_MATRIX.md`. Default skill: SOURCE_VERIFIER (R2) unless noted. Default complexity S. All parallelizable: Yes.

## T-001-01 vectorbt OSS license text (RG-03)
- Actions: fetch LICENSE from the repo at the pinned version; classify; record in registry.
- Outputs: registry row updated to S-strength; evidence record. Acceptance: exact license text quoted. Failure: text unavailable → vectorbt probe blocked, recorded.
- Blocks: T-006-06. Status: **DONE 2026-07-06** — Apache 2.0 + Commons Clause verified from installed v1.1.0 dist-info; evidence engines/vectorbt/LICENSE_CAPTURED.txt; RG-03 closed as CG-10.

## T-001-02 LEAN local data/pricing boundary (RG-02)
- Actions: fetch current QuantConnect datasets/pricing/CLI docs; determine free local crypto-spot backtest path; note account requirements.
- Outputs: evidence record + WS3 LEAN lane preconditions. Acceptance: boundary stated with quotes; else INSUFFICIENT recorded and lane proceeds to executable check with blocker protocol. Blocks: T-006-04 (soft). Status: **DONE 2026-07-07** (local Docker/custom-data boundary recorded in `artifacts/bakeoff/lean/STATUS.md`; no QuantConnect account required for local lane).

## T-001-03 Kraken/Coinbase Israel availability (RG-05)
- Actions: official supported-countries/legal pages; record verdicts; update venue matrix ranking if warranted (decision-log entry).
- Outputs: evidence records; possible AD-13 revision. Not blocking S1. Status: **DONE FOR AUTHORIZED SOURCE RECHECK 2026-07-11 / HUMAN ACCOUNT CHECKS DEFERRED-S3** — official-source slice retained in `artifacts/reports/VENUE_ISRAEL_SOURCE_RECHECK_2026_07_11.md`. Kraken is not demoted for Israel availability on the checked public-source evidence; Coinbase has Israel identity-document support but retail/product/account eligibility remains human-gated before S3 paper venue selection. No venue credential path exists now.

## T-001-04 AI provider primary-source pricing/policy sweep (RG-08)
- Actions: verify OpenAI GPT-5.6 tier pricing, Gemini 3.x context windows, Google deprecation policy from primary pages.
- Outputs: registry §7 rows at S-strength. Blocks: first paid benchmark run (T-011-05). Status: **DONE FOR SOURCE RECHECK 2026-07-10 / DEFERRED-CREDENTIALS FOR RUNS** — official OpenAI and Google primary-source pricing/context/deprecation pages are captured in `AI_PROVIDER_SOURCE_RECHECK_2026_07_10.md`; mock mode remains default until the operator enables a real provider.

## T-001-05 promptfoo ownership check (RG-09)
- Trigger-only: execute if promptfoo is proposed for WS8. Outputs: evidence record. Status: **NOT APPLICABLE FOR CURRENT S2 2026-07-10** — MLflow/null-provider harness remains the selected path and promptfoo is not proposed. Reopen only if promptfoo enters WS8 tooling.

## T-001-06 Registry 90-day refresh sweep
- Recurring: re-verify all REG rows nearing expiry; recompute reverify dates.
- Outputs: registry deltas + changelog note. Status: ONGOING (first due 2026-10-04).
