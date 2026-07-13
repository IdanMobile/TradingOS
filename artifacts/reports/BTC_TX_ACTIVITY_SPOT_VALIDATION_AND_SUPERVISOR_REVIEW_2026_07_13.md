# Bitcoin transaction-activity Spot validation and supervisor review

Date: 2026-07-13 UTC
Campaign: `BTC-TX-ACTIVITY-SPOT-G1-G11-V1`
Run commit: `265baee0ddd172d196440f7ab5e74966ea083222`
Supervisor verdict: **REJECT — exact context closed without rescue**
Execution authority: `NONE`

## Outcome

The preregistered development selection chose `SV-702a430c99d438cf`:
`HIGH`, 56 prior complete daily observations, and a one-day pulse. Its development result was
positive, but both chronological out-of-sample segments were negative. The full result, stressed
result, and one-bar-delayed result were also negative. G5 through G10 fail. G11 therefore rejects
the strategy as not validated and not promotion eligible.

| Frozen measure (F1/S1 unless stated) | Result |
|---|---:|
| Development return / completed trades | +26.68% / 139 |
| Validation 2024 return / completed trades | -1.57% / 41 |
| Reserve 2025–2026H1 return / completed trades | -22.22% / 71 |
| Full return / max drawdown | -3.02% / -38.49% |
| Full F2/S3 stress return / max drawdown | -51.98% / -61.68% |
| One-bar-delay full return | -21.41% |
| Positive calendar periods | 2 of 6 |
| PBO / threshold | 0.2965 / <= 0.50 (pass) |
| DSR / threshold | 0.3422 / >= 0.95 (fail) |
| Four-role event parity | PASS; no mismatches |

## Gate review

- G1 data provenance: **PASS** — exact retained official response bytes and Spot data hashes
  verified offline.
- G2 canonical identity: **PASS** — all 12 StrategyVersion identities matched the frozen roster.
- G3 causal goldens: **PASS** — consecutive-window, two-day-lag, no-stack, pulse-exit, and gap
  semantics passed.
- G4 independent reproduction: **PASS** — Decimal reference, vectorbt 1.1.0, Freqtrade 2026.6,
  and Nautilus Trader 1.230.0 matched within the frozen tolerance, with no event mismatch.
- G5 after-cost economics: **FAIL** — validation, reserve, full primary, and stress economics were
  not all positive.
- G6 chronological OOS: **FAIL** — validation and reserve both lost money.
- G7 sample and clock robustness: **FAIL** — trade counts passed, but the one-bar delay lost 21.41%.
- G8 regime and tail: **FAIL** — only two of six periods were positive and full drawdown exceeded
  the 25% cap.
- G9 benchmark and opportunity: **FAIL** — strategy full per-bar Sharpe (0.000660) was below
  buy-and-hold (0.005476); both required superiority conditions did not pass.
- G10 multiple testing: **FAIL** — PBO passed, but DSR was only 0.3422.
- G11 independent risk supervisor: **FAIL / REJECT** — the OOS, cost, delay, drawdown, regime,
  benchmark, and DSR evidence jointly prohibit promotion.

## Evidence classification

### Verified facts

- The development-only phase produced and hashed the selection artifact before validation or
  reserve evaluation.
- The selected development return was +26.68%; validation was -1.57%, reserve was -22.22%, and
  the full after-cost result was -3.02%.
- All framework roles agreed on events, counts, and metrics within the preregistered tolerance.
- The sealed V2 holdout and closed calendar/funding contexts were not accessed.

### Inference

The observed development association did not generalize. A plausible regime-specific activity
relationship cannot be distinguished from selection noise under this frozen sample; the failed
DSR, two negative OOS segments, and delay fragility make the latter risk material. This is not a
causal conclusion about Bitcoin network activity.

### Recommendation

Close the exact transaction-count shock family without changing side, threshold, window, holding
period, smoothing, price filter, asset, or timeframe. Begin a new source-only comparison of at
most three genuinely distinct mechanisms if autonomous offline research continues.

## Safety disposition

No bot, venue connection, credentials, paper/demo/live state, order path, human promotion gate, or
execution authority was activated. The selected StrategyVersion is research evidence only and
must not be traded.

## Sources and immutable artifacts

- Source and family dossier: `research/STRATEGY_FAMILY_SELECTION_AND_PREREGISTRATION_V4.md`
- Frozen campaign: `research/BTC_TX_ACTIVITY_SPOT_G1_G11_CAMPAIGN_V1.yaml`
- Campaign result: `artifacts/validation/campaigns/BTC-TX-ACTIVITY-SPOT-G1-G11-V1/campaign_result_f77b5d3481413d062fd8b7f4218e641cb2d71656ddcdcf2d7edcd29c8cdc5ef6.json`
- Selection artifact: `artifacts/validation/campaigns/BTC-TX-ACTIVITY-SPOT-G1-G11-V1/selection_affb5b1f22b75c73cbd4edbfba46064d63cebe99eed9efc10c0f9862d5844e17.json`
- Blockchain.com Charts API: https://www.blockchain.com/explorer/api/charts_api
- Koutmos (2018): https://doi.org/10.1016/j.econlet.2018.03.021
- Aalborg et al. (2019): https://doi.org/10.1016/j.frl.2018.08.010
