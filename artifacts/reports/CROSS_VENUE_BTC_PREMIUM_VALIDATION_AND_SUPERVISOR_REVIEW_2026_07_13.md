# Cross-venue BTC premium validation and supervisor review

Date: 2026-07-13 UTC
Campaign: `CROSS-VENUE-BTC-PREMIUM-G1-G11-V1`
Run commit: `2cb84c840dab1f9d260599818922f52ed5a92634`
Supervisor verdict: **REJECT — exact context closed without rescue**
Execution authority: `NONE`

## Outcome

The preregistered development selection chose `SV-f77752ce8b7882b0`:
`CONTINUATION_POSITIVE`, a 168-hour prior baseline, and a strict 2.0-z threshold. Development,
validation, reserve, full-history, stress, one-bar-delay, and every period result lost money after
the frozen primary costs. G5 through G10 fail. G11 rejects the strategy as not validated and not
promotion eligible.

| Frozen measure (F1/S1 unless stated) | Result |
|---|---:|
| Development return / completed trades | -56.08% / 374 |
| Validation 2024 return / completed trades | -8.29% / 146 |
| Reserve 2025–2026H1 return / completed trades | -24.12% / 253 |
| Full return / max drawdown | -69.44% / -73.45% |
| Full F2/S3 stress return / max drawdown | -96.50% / -96.87% |
| One-bar-delay full return | -72.99% |
| Positive periods | 0 of 6 |
| PBO / threshold | 0.1003 / <= 0.50 (pass) |
| DSR / threshold | 0.00000395 / >= 0.95 (fail) |
| Four-role parity | PASS; max absolute metric difference 3.71e-14 |

## Gate review

- G1 data provenance: **PASS** — 382 exact public Coinbase responses, retained Binance bytes,
  normalized rows, gaps, quote conversion, and strict-later mappings verify offline.
- G2 canonical identity: **PASS** — all 12 StrategyVersion identities match the frozen roster.
- G3 causal goldens: **PASS** — timing, polarity, zero variance, gap reset, nonextension, future
  append, and two-sided cost semantics pass.
- G4 independent reproduction: **PASS** — Decimal reference, vectorbt, Freqtrade-environment, and
  Nautilus-environment roles match in both phases within `1e-10`.
- G5 after-cost economics: **FAIL** — development, validation, reserve, full, and stress returns are
  all negative.
- G6 chronological OOS: **FAIL** — 2024 validation lost 8.29% and the untouched family reserve lost
  24.12%.
- G7 sample and clock robustness: **FAIL** — trade counts pass, but a one-bar delay loses 72.99%.
- G8 regime and tail: **FAIL** — zero of six periods is positive and full drawdown is 73.45%
  against the 25% cap.
- G9 benchmark and opportunity: **FAIL** — full per-bar Sharpe is -0.01105 versus costed
  buy-and-hold +0.00318. The strategy's smaller drawdown does not offset failed Sharpe superiority.
- G10 multiple testing: **FAIL** — PBO passes at 0.1003, but corrected DSR is 0.00000395 across an
  effective 7.79 trials.
- G11 independent risk supervisor: **FAIL / REJECT** — pervasive after-cost losses, both OOS
  failures, delay failure, zero regime breadth, tail loss, benchmark inferiority, and DSR
  independently prohibit promotion.

## Evidence classification

### Verified facts

- The runner wrote and hashed its development selection before validation or reserve evaluation.
- The selected rule loses in development and both chronological OOS segments.
- All six period slices are negative; full stress loses 96.50%.
- Full phase-one and phase-two four-role parity passes without mismatch.
- All content-addressed campaign files match the hash embedded in their filenames.
- The sealed V2 holdout and every closed-family context were not accessed.

### Inference

The completed-hour quote-normalized Coinbase/Binance premium has no robust after-cost directional
edge under this frozen six-hour long/cash context. The failure is not merely overfitting: the best
development rule itself loses materially, and both OOS segments, delay, every regime slice, stress,
benchmark, and DSR agree. This does not prove that all cross-venue information is useless at every
horizon or execution style; it rejects this exact safe offline context.

### Recommendation

Close this exact family without changing sign, baseline, threshold, holding period, quote
conversion, venue pair, timeframe, price filter, sizing, or execution assumption. Do not reinterpret
the result as an arbitrage test or add sub-hour/order-book data after seeing the outcome. Any further
autonomous strategy research must begin another source-only comparison of at most three genuinely
distinct mechanisms, and the supervisor should consider whether continued public-signal mining has
enough prior plausibility to justify its research cost.

## Safety disposition

No bot, trading-venue session, credentials, paper/demo/live state, order path, human promotion gate,
or execution authority was activated. The selected StrategyVersion is negative research evidence
only and must not be traded.

## Sources and immutable artifacts

- Family dossier: `research/STRATEGY_FAMILY_SELECTION_AND_PREREGISTRATION_V8.md`
- Data package: `research/CROSS_VENUE_BTC_PREMIUM_DATA_PACKAGE_V1.json`
- Frozen campaign: `research/CROSS_VENUE_BTC_PREMIUM_G1_G11_CAMPAIGN_V1.yaml`
- Campaign result: `artifacts/validation/campaigns/CROSS-VENUE-BTC-PREMIUM-G1-G11-V1/campaign_result_3a0753255bca8aa2eeaa2fd5b03123d2f8fcae9b8308cf73a5831232ab4cd9bb.json`
- Selection artifact: `artifacts/validation/campaigns/CROSS-VENUE-BTC-PREMIUM-G1-G11-V1/selection_80e50a17a94db52f07d049f5c414d413ef7fc0aa54865e569f4d0d9ce396fc08.json`
- Coinbase Exchange candles: https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles
- Cross-venue price-formation evidence: https://doi.org/10.1016/j.jfineco.2019.07.001 and https://arxiv.org/abs/2108.09750
