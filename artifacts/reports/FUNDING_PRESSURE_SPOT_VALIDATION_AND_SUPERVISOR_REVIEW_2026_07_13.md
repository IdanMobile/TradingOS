# Funding-pressure Spot validation and supervisor review

Campaign: `FUNDING-PRESSURE-SPOT-G1-G11-V3`  
Run commit: `f31e601`  
Result: `campaign_result_4f85fb195e3097a8d7a9b1b4484e51b0e8c4395bf16b6017801f39f196ccda76.json`  
Supervisor verdict: **REJECTED — NOT VALIDATED, NOT PROMOTION ELIGIBLE**

## Verified facts

- The offline package verified 66 funding archives, 6,021 exact-millisecond observations, and
  48,154 Spot hourly bars. Network, credentials, venue, orders, and sealed/rejected holdouts were
  prohibited.
- The two-phase barrier passed. All 12 development trials were evaluated, a content-addressed
  selection artifact was written, and only then was the selected StrategyVersion evaluated on
  validation and reserve.
- Development selected `CONTRARIAN / 3 observations / 0.0001`.
- Selected F1/S1 results: development `+55.49%` with 13 completed trades; 2024 validation `0.00%`
  with zero trades; 2025–2026H1 reserve `-2.52%` with two trades; full history `+51.58%` with 15
  trades and `-10.95%` maximum drawdown.
- Full F2/S3 stress remained positive at `+45.34%`; a one-bar delayed fill remained positive at
  `+53.20%`.
- Costed buy-and-hold returned `+102.47%`, with lower per-bar Sharpe and much worse drawdown than
  the selected strategy.
- G10 PBO passed numerically at `0.3847`, but DSR failed at `0.8235` versus the frozen `0.95`
  threshold.
- Decimal/vectorbt metric differences were at most `3.14e-14`. Freqtrade matched event parity.
  Nautilus disagreed on one non-selected development trial (`CONTINUATION / 21 / 0.0001`):
  17/16 buys/sells versus 13/12 in the reference. Selected phase-two parity passed.
- Frozen gate outcomes: G1/G2/G3/G9 PASS; G4/G5/G6/G7/G8/G10 FAIL; G11 was pending this review.

## Interpretation

The apparent full-history gain is concentrated in 2021 and 2022. The strategy produced no 2024
validation trades and only two losing reserve trades. This is insufficient evidence of a current,
repeatable edge and fails the preregistered chronological, economics, sample, regime, and
multiple-testing requirements. The low drawdown and positive stress result do not compensate for
absence of validation activity or reserve profitability.

The Nautilus mismatch is consistent with float accumulation at a strict threshold boundary, but
that cause is an inference, not a verified repair. The exact campaign fails G4 regardless, and no
post-result numerical change is permitted.

## Independent risk and red-team disposition

- **Market/model risk: REJECT.** Validation inactivity and reserve loss show material regime and
  sample instability.
- **Execution/cost risk: NOT THE DECISIVE FAILURE.** Frozen adverse costs and delay remained
  positive, but only on too few selected trades.
- **Statistical risk: REJECT.** DSR fails and the selected evidence has 15 completed trades over
  the full 5.5-year sample.
- **Implementation/conformance risk: REJECT.** One declared trial fails Nautilus event parity.
- **Security/authority: PASS FOR OFFLINE CONTAINMENT ONLY.** No authenticated transport or order
  capability was used; this grants no further authority.
- **No-rescue check: PASS.** No alternate polarity, lookback, threshold, filter, sizing, cost,
  period, or reserve interpretation is admitted.

G11 is therefore **FAIL / REJECTED_NOT_PROMOTION_ELIGIBLE**. The exact family/context is closed.
No bot, paper/demo/live activation, venue connection, credential request, order, HG-3 decision, or
promotion is authorized.

## Unknowns and next boundary

No claim is made that every possible funding-derived strategy lacks value. This campaign rejects
only the frozen directional long/cash mean-funding family. Any future work must begin with a
genuinely distinct mechanism and new unseen evidence; it may not tune or rescue this result.
