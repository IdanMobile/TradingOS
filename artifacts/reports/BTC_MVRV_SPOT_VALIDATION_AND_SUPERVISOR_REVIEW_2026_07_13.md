# Bitcoin MVRV Spot validation and supervisor review

Date: 2026-07-13 UTC
Campaign: `BTC-MVRV-SPOT-G1-G11-V1`
Run commit: `e148de5a510c934d7713a69335c8576505c8ec70`
Supervisor verdict: **REJECT — exact context closed without rescue**
Execution authority: `NONE`

## Outcome

The development barrier selected `SV-e5eadedce6b89139`: HIGH MVRV dislocation, 180-day prior
window, one-day pulse. Its development gain did not generalize. Validation, reserve, stress, and
one-bar-delay results were negative; PBO and DSR both failed. G5 through G10 fail, so G11 rejects
the strategy as not validated and not promotion eligible.

| Frozen measure (F1/S1 unless stated) | Result |
|---|---:|
| Development return / completed trades | +44.50% / 163 |
| Validation 2024 return / completed trades | -21.00% / 69 |
| Reserve 2025–2026H1 return / completed trades | -10.42% / 10 |
| Full return / max drawdown | +7.27% / -36.51% |
| Full F2/S3 stress return / max drawdown | -45.53% / -63.63% |
| One-bar-delay full return | -20.08% |
| Positive calendar periods | 1 of 6 |
| PBO / threshold | 0.5895 / <= 0.50 (fail) |
| DSR / threshold | 0.4632 / >= 0.95 (fail) |
| Four-role parity | PASS; no mismatches |

## Gate review

- G1 data provenance: **PASS** — retained Coin Metrics body/catalog and Spot hashes verified.
- G2 canonical identity: **PASS** — all 12 StrategyVersions matched the frozen roster.
- G3 causal goldens: **PASS** — window, lag, non-stack, exit, and gap semantics passed.
- G4 independent reproduction: **PASS** — Decimal, vectorbt 1.1.0, Freqtrade 2026.6, and
  Nautilus Trader 1.230.0 matched within tolerance without event mismatches.
- G5 after-cost economics: **FAIL** — OOS and stress economics were negative.
- G6 chronological OOS: **FAIL** — validation and reserve both lost money.
- G7 sample and clock robustness: **FAIL** — reserve had 10 completed trades versus 12 required,
  and the one-bar delay lost 20.08%.
- G8 regime and tail: **FAIL** — only one period was positive and drawdown exceeded 25%.
- G9 benchmark and opportunity: **FAIL** — full per-bar Sharpe was below buy-and-hold and both
  superiority requirements did not pass.
- G10 multiple testing: **FAIL** — PBO and DSR both failed.
- G11 independent risk supervisor: **FAIL / REJECT** — promotion is prohibited.

## Evidence classification

### Verified facts

- Selection was created and hash-verified before validation or reserve evaluation.
- Development returned +44.50%; validation -21.00%; reserve -10.42%; stress -45.53%.
- All four implementation roles matched within the frozen tolerance.
- The sealed V2 holdout and closed-family contexts were not accessed.

### Inference

The development relationship was regime-specific or selected noise under this design. MVRV's
current-price numerator may also make HIGH dislocations partly encode a price regime, but the
campaign cannot identify causality. Negative OOS, delay fragility, low DSR, and high PBO dominate.

### Recommendation

Close the exact MVRV pulse family. Do not change side, threshold, windows, holding periods, MVRV
variant, smoothing, price filter, asset, or timeframe as a post-result rescue. Continue only with
a genuinely distinct source-only mechanism.

## Safety disposition

No bot, venue connection, credentials, paper/demo/live state, order path, human promotion gate, or
execution authority was activated. The selected StrategyVersion is research evidence only.
