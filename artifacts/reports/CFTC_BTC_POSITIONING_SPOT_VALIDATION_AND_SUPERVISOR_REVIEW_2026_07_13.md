# CFTC Bitcoin positioning Spot validation and supervisor review

Date: 2026-07-13 UTC
Campaign: `CFTC-BTC-POSITIONING-SPOT-G1-G11-V1`
Run commit: `b3bc0246e460db4414687edf0755eafcd862959a`
Supervisor verdict: **REJECT — exact context closed without rescue**
Execution authority: `NONE`

## Outcome

The preregistered development selection chose `SV-0bf55e2fa7d34ff8`:
`CONTRARIAN_LOW`, a 52-report prior baseline, and a strict 1.0-z threshold. The development result
was positive, but validation lost money and the sample, drawdown, regime, benchmark, PBO, and DSR
requirements failed. G5 through G10 fail. G11 therefore rejects the strategy as not validated and
not promotion eligible.

| Frozen measure (F1/S1 unless stated) | Result |
|---|---:|
| Development return / completed trades | +85.08% / 27 |
| Validation 2023–2024 return / completed trades | -2.50% / 13 |
| Reserve 2025–2026H1 return / completed trades | +2.67% / 6 |
| Full return / max drawdown | +85.27% / -63.35% |
| Full F2/S3 stress return / max drawdown | +62.88% / -64.86% |
| One-bar-delay full return | +87.69% |
| Positive periods | 4 of 7 |
| PBO / threshold | 0.5578 / <= 0.50 (fail) |
| DSR / threshold | 0.3493 / >= 0.95 (fail) |
| Four-role event parity | PASS; no mismatches |

## Gate review

- G1 data provenance: **PASS** — exact CFTC source bytes, publication-exception mappings, and
  combined Spot data hashes verified offline.
- G2 canonical identity: **PASS** — all 12 StrategyVersion identities matched the frozen roster.
- G3 causal goldens: **PASS** — strict-later fills, polarity, zero-variance, pulse, gap, cost, and
  future-append semantics passed.
- G4 independent reproduction: **PASS** — Decimal reference, vectorbt 1.1.0, Freqtrade 2026.6,
  and Nautilus Trader 1.230.0 matched without event mismatches; maximum metric difference was
  2.07e-14 against the 1e-10 tolerance.
- G5 after-cost economics: **FAIL** — validation was negative, so all required primary and stress
  segments were not positive.
- G6 chronological OOS: **FAIL** — validation lost 2.50%.
- G7 sample and clock robustness: **FAIL** — development completed 27 trades against 30 required,
  and reserve completed 6 against 12 required; the delay test itself was positive.
- G8 regime and tail: **FAIL** — only four of seven periods were positive and full drawdown of
  63.35% exceeded the 25% cap.
- G9 benchmark and opportunity: **FAIL** — strategy full per-bar Sharpe (0.004609) was below
  buy-and-hold (0.005476), despite a smaller drawdown than buy-and-hold.
- G10 multiple testing: **FAIL** — PBO was 0.5578 and DSR was 0.3493.
- G11 independent risk supervisor: **FAIL / REJECT** — negative validation, insufficient sample,
  excessive drawdown, weak period breadth, inferior Sharpe, PBO, and DSR prohibit promotion.

## Evidence classification

### Verified facts

- The development-only phase produced and hashed the selection artifact before validation or
  reserve evaluation.
- The selected development return was +85.08%; validation was -2.50%, reserve was +2.67%, and the
  full after-cost result was +85.27% with a 63.35% drawdown.
- All framework roles agreed on events, counts, and metrics within the preregistered tolerance.
- The sealed V2 holdout and closed-family contexts were not accessed.

### Inference

The development association did not demonstrate robust generalization. The small OOS sample and
failed PBO/DSR leave selection noise and regime concentration as material explanations. This is
not a causal conclusion about CFTC positioning or Bitcoin returns.

### Recommendation

Close this exact positioning-pulse context without changing interpretation, baseline, threshold,
holding period, availability rule, asset, or timeframe. If autonomous offline research continues,
start a new source-only comparison of at most three genuinely distinct mechanisms.

## Safety disposition

No bot, venue connection, credentials, paper/demo/live state, order path, human promotion gate, or
execution authority was activated. The selected StrategyVersion is research evidence only and
must not be traded.

## Sources and immutable artifacts

- Family dossier: `research/STRATEGY_FAMILY_SELECTION_AND_PREREGISTRATION_V6.md`
- Frozen campaign: `research/CFTC_BTC_POSITIONING_SPOT_G1_G11_CAMPAIGN_V1.yaml`
- Campaign result: `artifacts/validation/campaigns/CFTC-BTC-POSITIONING-SPOT-G1-G11-V1/campaign_result_cdab10252bd99ec144aede9a018c38ef58043f8feef5d808b0d9a3b8907a0cdc.json`
- Selection artifact: `artifacts/validation/campaigns/CFTC-BTC-POSITIONING-SPOT-G1-G11-V1/selection_0d903bb2b8fccfd0ef7a456820107f58772d97e02e04d8b20c25e7286ccd744f.json`
- CFTC Commitments of Traders: https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm
- CFTC release schedule: https://www.cftc.gov/MarketReports/CommitmentsofTraders/ReleaseSchedule/index.htm
