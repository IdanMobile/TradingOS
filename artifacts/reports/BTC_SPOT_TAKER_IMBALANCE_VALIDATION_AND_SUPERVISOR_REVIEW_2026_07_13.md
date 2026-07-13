# BTC Spot taker-imbalance validation and supervisor review

Date: 2026-07-13 UTC
Campaign: `BTC-SPOT-TAKER-IMBALANCE-G1-G11-V2`
Run commit: `eba18df8ad87f87d518d2272b78302bc53dab5e8`
Supervisor verdict: **REJECT — exact context closed without rescue**
Execution authority: `NONE`

## Outcome

The preregistered development selection chose `SV-388d495a5155319b`:
`CONTINUATION_HIGH`, a 168-hour prior baseline, and a strict 2.0-z threshold. Development,
validation, reserve, full-history, stress, and one-bar-delay results all lost money. Only one of
seven periods was positive, full drawdown exceeded 90%, and DSR was effectively zero. G4 through
G10 fail. G11 rejects the strategy as not validated and not promotion eligible.

| Frozen measure (F1/S1 unless stated) | Result |
|---|---:|
| Development return / completed trades | -74.26% / 776 |
| Validation 2023–2024 return / completed trades | -11.37% / 332 |
| Reserve 2025–2026H1 return / completed trades | -57.15% / 255 |
| Full return / max drawdown | -90.23% / -90.37% |
| Full F2/S3 stress return / max drawdown | -99.78% / -99.79% |
| One-bar-delay full return | -90.90% |
| Positive periods | 1 of 7 |
| PBO / threshold | 0.2799 / <= 0.50 (pass) |
| DSR / threshold | 0.0000208 / >= 0.95 (fail) |
| Selected-trial phase-two parity | PASS; no mismatches |
| Full four-role parity | FAIL; two nonselected 24-hour/1.0 development trials differ in vectorbt |

## Gate review

- G1 data provenance: **PASS** — exact official-checksum archives, normalized bytes, feature rows,
  gaps, invalid-row ledger, and strict post-close mappings verified offline.
- G2 canonical identity: **PASS** — all 12 StrategyVersion identities matched the frozen roster.
- G3 causal goldens: **PASS** — timing, polarity, zero variance, nonextension, cost, reset, invalid
  input, and future-append semantics passed.
- G4 independent reproduction: **FAIL** — the selected trial and all phase-two metrics matched, but
  vectorbt disagreed on event counts and F2/S3 metrics for the nonselected continuation/24/1.0 and
  reversal/24/1.0 development trials. Maximum metric difference was 0.001003.
- G5 after-cost economics: **FAIL** — every required selected segment lost money.
- G6 chronological OOS: **FAIL** — validation lost 11.37% and reserve lost 57.15%.
- G7 sample and clock robustness: **FAIL** — sample counts passed, but the one-bar-delay result
  lost 90.90%.
- G8 regime and tail: **FAIL** — only one of seven periods was positive and full drawdown was
  90.37% against the 25% cap.
- G9 benchmark and opportunity: **FAIL** — full per-bar Sharpe was -0.014687 versus buy-and-hold
  +0.005476, and the strategy did not satisfy the required superiority conditions.
- G10 multiple testing: **FAIL** — PBO passed at 0.2799, but DSR was 0.0000208.
- G11 independent risk supervisor: **FAIL / REJECT** — pervasive after-cost losses, OOS failure,
  delay failure, tail loss, weak regime breadth, benchmark inferiority, DSR, and parity residuals
  independently prohibit promotion.

## Evidence classification

### Verified facts

- V2 produced and hashed its development selection before validation or reserve evaluation.
- The selected development return was -74.26%; validation was -11.37%, reserve was -57.15%, and
  full after-cost return was -90.23%.
- Selected-trial phase-two reference/vectorbt/Freqtrade/Nautilus events and metrics matched within
  tolerance; two nonselected development trials retained explicit vectorbt residuals.
- The sealed V2 holdout and closed-family contexts were not accessed.

### Inference

The exchange-local completed-hour imbalance pulse has no robust after-cost edge under this frozen
context. High turnover makes the observed economics decisively adverse, and the negative OOS,
delay, tail, benchmark, and DSR evidence leaves no defensible promotion case. This does not prove
that all order-flow information is useless at every horizon, venue, or execution style.

### Recommendation

Close this exact family without changing sign, baseline, threshold, holding period, aggregation,
price filter, asset, venue, timeframe, or sizing. Do not spend work resolving the two nonselected
parity residuals for promotion because independent economic gates already fail decisively; retain
them as negative conformance evidence. Any further autonomous research must begin a new source-only
comparison of at most three genuinely distinct mechanisms.

## Safety disposition

No bot, venue connection, credentials, paper/demo/live state, order path, human promotion gate, or
execution authority was activated. The selected StrategyVersion is research evidence only and
must not be traded.

## Sources and immutable artifacts

- Family dossier: `research/STRATEGY_FAMILY_SELECTION_AND_PREREGISTRATION_V7.md`
- Frozen V1 contract: `research/BTC_SPOT_TAKER_IMBALANCE_G1_G11_CAMPAIGN_V1.yaml`
- Computation-only V2: `research/BTC_SPOT_TAKER_IMBALANCE_G1_G11_CAMPAIGN_V2.yaml`
- Campaign result: `artifacts/validation/campaigns/BTC-SPOT-TAKER-IMBALANCE-G1-G11-V2/campaign_result_06111e4492a30b39789501b7d7607de27c9efd778a3a808f77e108858df082b7.json`
- Selection artifact: `artifacts/validation/campaigns/BTC-SPOT-TAKER-IMBALANCE-G1-G11-V2/selection_47fe851c738471c9c906a1699df426387a84c21b9e98503a3690f2130c7c625c.json`
- Binance public-data schema and checksum contract: https://github.com/binance/binance-public-data
