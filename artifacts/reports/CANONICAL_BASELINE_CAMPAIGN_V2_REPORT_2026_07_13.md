# Canonical baseline V2 campaign report — 2026-07-13

Status: **COMPLETED / NEGATIVE / METHOD_BLOCKED / NOT PROMOTABLE**
Campaign: `SEARCH-CANONICAL-BASELINE-G10-V2`
Frozen run commit: `6bac8bfa64ac38af2425e33fbb42fb73d90d79e3`
Execution authority: `NONE`

## Plain-language outcome

The corrected baseline test worked as designed, and the strategies did not.

- B2's best moving-average variant made only **+3.54% with impossible zero costs** over
  the full 5.5-year sample. At the frozen F1/S1 economic cell (10 bps fee plus 1 bp
  adverse slippage per side), it lost effectively **100%** because it traded far too often.
- B4's best breakout variant was already **-96.99% before costs** and also lost effectively
  100% at F1/S1.
- B3's statistical “winner” was a preregistered, mathematically inert zero-trade variant.
  That is not an edge; it is a useful demonstration that doing nothing beat the active B3
  variants after costs.
- Five expanding chronological pseudo-out-of-sample folds did not rescue B2 or B4.
- Nothing was promoted, no winner was adopted, and no venue/order capability was enabled.

This is a successful research result in the important sense: it closes an attractive-looking
but uneconomic path without hiding the failure or tuning after seeing it.

## What V2 corrected

V1 was intentionally preserved as a legacy reproduction. V2 is a separate implementation
that follows the canonical baseline rules:

- signal decisions use bar-close information only;
- fills occur only at the next **exactly adjacent** five-minute bar open;
- signals expire across gaps, while already-held positions carry without synthetic fills;
- indicator warm-up resets after gaps;
- B2 uses persistent `fast SMA > slow SMA` eligibility, not crossover pulses;
- B3 uses population standard deviation (`ddof=0`);
- B4 excludes the current high from its breakout threshold;
- simultaneous B4 entry/exit states resolve from position state: flat enters, held exits;
- final-bar signals do not fill; open final positions are marked at final close;
- all calculations disclose Decimal128-to-float64 conversion in the vectorbt lane.

Micro-fixture tests independently match the exact B2 3/5, B3 3/1, and B4 5/3 canonical
controls. Timing tests cover first eligible entry, state conflicts, last-bar expiry, gap
behavior, adverse buy/sell slippage, fees, and final mark-to-market.

## Frozen scope

| Item | Frozen value |
|---|---:|
| Data | BTCUSDT Spot, 5m, 2021-01-01 through 2026-06-30 |
| Bars | 577,803 |
| Known gaps / missing bars | 7 / 213 |
| B2 trials | 35 |
| B3 trials | 16 |
| B4 trials | 16 |
| Campaign-wide trials | 67 |
| Cost cells | 6 |
| Historical walk-forward folds | 5 |
| CSCV slices | 16 |
| Governed selection cell | F1/S1 |
| Governed metric | non-annualized per-bar Sharpe |

The cost grid is F0/S0, F1/S1, F1/S2, F1/S3, F2/S2, and F2/S3. F0/S0 is diagnostic
only. F1 is 10 bps per executed side; F2 is 15 bps. S1/S2/S3 are 1/5/10 bps adverse
slippage per side. They are stress assumptions, not empirical order-book evidence.

## Statistical results

| Scope | Selected diagnostic trial | PBO | DSR | Numeric verdict | Gate status |
|---|---|---:|---:|---|---|
| B2 | `fast=15,slow=60` | 0.5066 | 0.0000 | FAIL | METHOD_BLOCKED |
| B3 | `window=3,deviation=1.5` (zero trades) | 0.0163 | withheld | METHOD_BLOCKED | METHOD_BLOCKED |
| B4 | `lookback=3,exit_window=10` | 0.3739 | 0.0000 | FAIL | METHOD_BLOCKED |
| All 67 | `b3:window=3,deviation=1.5` (zero trades) | 0.0163 | withheld | METHOD_BLOCKED | METHOD_BLOCKED |

B2's PBO is above the frozen 0.5 maximum and its DSR is zero. B4's PBO is below 0.5,
but its DSR is zero, so it still fails. B3 and campaign-wide DSR are correctly withheld:
the retained structural zero-trade variants have undefined return correlations, so inventing
an effective independent-trial count would be invalid.

Even a hypothetical numeric pass could not clear G10 here. The historical upstream process
that admitted these families was not retained, so hierarchy-wide search lineage and effective
trial evidence remain unavailable.

## Economic results

### Full-sample selected diagnostics

| Family | F0/S0 total return | F1/S1 total return | F1/S1 trades | F1/S1 turnover / initial cash |
|---|---:|---:|---:|---:|
| B2 | +3.54395% | -99.99993% | 6,442 | 945.83x |
| B3 | 0.00000% | 0.00000% | 0 | 0.00x |
| B4 | -96.98689% | -99.99998% | 6,221 | 964.34x |

Turnover is gross executed notional divided by the fixed 1,000-unit initial cash. It is not a
capacity estimate. The number of actually executed trades falls in harsher cells because the
simulated account depletes and eventually cannot continue placing full-cash entries.

### Exact canonical controls at F1/S1

| Family | Exact control | Total return | Per-bar Sharpe | Trades |
|---|---|---:|---:|---:|
| B2 | `fast=3,slow=5` | -99.99998% | -0.03528 | 6,761 |
| B3 | `window=3,deviation=1` | -99.99998% | -0.03527 | 7,821 |
| B4 | `lookback=5,exit_window=3` | -99.99998% | -0.04901 | 6,177 |

The complete cost surface, including executed sides, buy/sell counts, gross notional, and
turnover for every trial, is retained in the content-addressed inputs and result files.

## Historical walk-forward results

The folds select using an expanding past-only training window, leave one complete five-minute
bar between selection and test, start the selected test strategy flat, and permit trailing
history only for indicator warm-up. Because these data and families influenced earlier work,
the correct label is `HISTORICAL_PSEUDO_OOS`, not untouched holdout.

| Scope | Stitched pseudo-OOS total return | Stitched per-bar Sharpe | Interpretation |
|---|---:|---:|---|
| B2 | -99.99884% | -0.02094 | Failed in every fold |
| B3 | 0.00000% | 0.00000 | Inert zero-trade variant selected in every fold |
| B4 | -100.00000% | -0.10363 | Failed severely in every fold |
| All 67 | 0.00000% | 0.00000 | Inert B3 variant selected in every fold |

## Data restoration and immutable evidence

The previous exact Parquet existed locally but was not distributable through the local-only DVC
prototype. V2 adds a tracked portable source manifest containing 66 official Binance monthly
archive URLs, sizes, and SHA-256 values. The restore command is offline/read-only by default;
`--fetch` must be explicit. Rebuilding all pinned archives with PyArrow 24 reproduced:

- rows: `577803`;
- logical content SHA-256: `3ec05eb0ea618310209ae92de4bf1940b929ed2c889bccb0b3f749ff0a8a17fa`;
- Parquet SHA-256: `d4d6b3306c44e242f3fb7f71c44bacabf9a6af1f1f8d507ca2de0853b6a727d0`;
- Parquet size: `35,542,487` bytes.

The formal campaign started from clean commit `6bac8bf`, used no network, and published 13
content-addressed files atomically. The immutable index is:

`artifacts/validation/campaigns/SEARCH-CANONICAL-BASELINE-G10-V2/campaign_index_96d746a1e8084c6a9a39e2d8752936d166c32c2685a9c31b48f5feb7a7a93950.json`

Normal verification passed, then a second complete run with the frozen generation timestamp
reproduced every all-trial JSON byte-for-byte (`RECOMPUTE_VERIFY_PASS`).

## Evidence-strength boundary

An implementation performance smoke touched the complete historical dataset before the formal
contract was committed. The exposure and the coarse verdicts are frozen in the campaign record.
Therefore V2 is an immutable historical reproducibility/conformance diagnostic, not an unseen
confirmatory test.

The genuinely prospective holdout is sealed from `2026-07-14T00:00:00Z` and may be evaluated
once, no earlier than `2027-01-14T00:00:00Z` after at least 184 days. Any adaptation after
observing it requires V3 and a new holdout. V2 consumes none of that future data.

## Decision and next action

1. Do not expand or rescue B2/B3/B4 with more parameters. Their active canonical controls and
   selected diagnostics are uneconomic at five-minute frequency under the frozen costs.
2. Keep the prospective holdout sealed; collection may be mechanical, but no interim strategy
   score should be calculated or viewed.
3. If research continues before 2027-01-14, reconstruct one economically distinct strategy
   family's canonical ownership, point-in-time data, costs, and hierarchical search contract.
   Do not reuse this baseline grid as the next search seed.
4. Keep authenticated networking quarantined. No result here authorizes paper, demo, or live
   execution.

## Primary method sources

- vectorbt Portfolio documentation: <https://vectorbt.dev/api/portfolio/base/>
- Freqtrade Strategy 101: <https://www.freqtrade.io/en/stable/strategy-101/>
- Binance public data: <https://github.com/binance/binance-public-data>
- Binance Spot fee schedule: <https://www.binance.com/en/fee/trading>
- scikit-learn TimeSeriesSplit: <https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html>
- Bailey et al., *The Probability of Backtest Overfitting*: <https://scholarworks.wmich.edu/math_pubs/42/>
- Bailey and López de Prado, *The Deflated Sharpe Ratio*: <https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf>
- DVC data sharing workflow: <https://dvc.org/doc/command-reference/get>

These sources support the method choices only. They do not validate a strategy or imply profit.
