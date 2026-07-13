# Calendar UTC validation and supervisor review — 2026-07-13

## Disposition

`SV-c79226c64f6259c5` (Wednesday UTC, BTCUSDT Spot 1h) is
**REJECTED_NOT_PROMOTION_ELIGIBLE**. It is not a verified strategy and may not enter
synthetic paper, demo, testnet, or live operation. Execution authority remains `NONE`.

This is not a marginal judgment. The frozen campaign has four preregistered numeric hard
failures, one reserve-sequencing protocol deviation, and incomplete Freqtrade/Nautilus
conformance. Positive 2024 and 2025–2026H1 returns do not offset those failures.

## Verified facts

- The campaign ran from clean commit `ecdfb3b53815d61713ebeea30d1bc19fda3bd59f`.
- Immutable preregistration SHA-256:
  `bce52193c0d7cf7335a25aef48f6e34b09c1545495f16e64e8fa75b65cf68eae`.
- The exact 48,154-row dataset and all 66 retained raw archives passed offline hash
  verification. No network, credential, venue, order route, or sealed V2 holdout was used.
- The complete seven-weekday roster was retained. Development selected Wednesday
  (`selected_weekday=2`) by the frozen F1/S1 per-hour Sharpe rule.
- Decimal-reference and vectorbt metrics agreed with no mismatch; maximum absolute metric
  difference was `6.7863e-14`, below the frozen `1e-10` tolerance.
- A second clean computation reproduced the preregistration, Decimal result, and vectorbt
  result files byte-for-byte. The campaign result differs only in its completion timestamp;
  deleting that field yields byte-identical JSON.

## Frozen gate result

| Gate | Campaign output | Supervisory disposition | Evidence |
|---|---:|---|---|
| G1 data/provenance | PASS | PASS | Offline hashes, gaps retained, no interpolation |
| G2 canonical identity | PASS | PASS | Seven content-derived StrategyVersions |
| G3 causal goldens | PASS | PASS | Boundary, price-invariance, cost, gap-expiry, and gap-exit tests |
| G4 independent reproduction | PASS | PARTIAL | Decimal/vectorbt parity passes; required Freqtrade and Nautilus conformance was not run |
| G5 after-cost economics | FAIL | FAIL | F2/S3 full return `-40.74%`; F1/S3 already `-21.12%` |
| G6 chronological OOS | PASS | INVALIDATED | 2024 `+16.46%`, reserve `+4.25%`, but reserve sequencing violated preregistration |
| G7 sample/clock robustness | PASS | PASS | Counts pass; ±1h F1/S1 returns remain positive |
| G8 regime/tail | FAIL | FAIL | F1/S1 max drawdown `-41.29%`, beyond frozen `-25%` limit |
| G9 benchmark/opportunity | FAIL | FAIL | strategy Sharpe `0.00351` < buy-and-hold `0.00548` |
| G10 multiple testing | FAIL | FAIL | PBO `0.75936`; DSR `0.30121` |
| G11 risk/supervisor | NOT_RUN | REJECT | Hard failures and protocol deviation prohibit approval |

## Economics and robustness

The zero-cost result (`+147.61%`) falls to `+31.98%` at F1/S1, `+4.99%` at
F1/S2, `-21.12%` at F1/S3, and `-40.74%` at F2/S3. This steep monotone decay is a
material turnover/cost vulnerability, not a minor calibration issue. The strategy executes
286 completed weekly trades over the full sample.

The selected weekday was positive in four of the six frozen year/H1 segments, including
2024 and the nominal reserve. It was negative in 2022 (`-24.14%`) and 2026 H1
(`-11.85%`). The full F1/S1 drawdown was `-41.29%`, versus `-77.20%` for buy-and-hold;
lower drawdown does not compensate for failing the frozen absolute tail limit and
risk-adjusted benchmark.

## Statistical-specialist review

Method verdict for the declared seven-trial development scope:
`METHOD_VALIDATED_FOR_DIAGNOSTIC_USE`. The campaign uses the corrected shared PBO/CSCV and
DSR implementation with retained synthetic known-answer fixtures, non-annualized per-bar
Sharpe throughout, 16 equal CSCV slices, all seven statistical trials, and an explicit
effective-trial estimate. These statistics do not prove profitability; here they strongly
reject selection reliability. PBO exceeds `0.5` and DSR is far below `0.95`.

The three qualitative family candidates are retained as selection lineage but do not have a
common return surface, so they cannot be inserted numerically into DSR. That limitation does
not rescue the result: the within-family G10 test already fails.

## Backtest red-team findings

1. **Critical — cost fragility confirmed.** Executable test: compare the complete frozen six-cell
   surface. Result: hard stress is negative and even F1/S3 loses 21.12%. Attack succeeds.
2. **Critical — multiple-testing instability confirmed.** Executable test: frozen 16-slice CSCV
   and corrected DSR across all seven weekdays. Result: PBO 0.759 and DSR 0.301. Attack succeeds.
3. **High — tail limit breach confirmed.** Executable test: causal F1/S1 equity drawdown.
   Result: -41.29% versus a -25% limit. Attack succeeds.
4. **High — benchmark opportunity cost confirmed.** Executable test: compare full F1/S1
   per-hour Sharpe and drawdown with costed BTCUSDT buy-and-hold. Result: calendar Sharpe is
   lower. Attack succeeds.
5. **High — reserve protocol deviation confirmed.** Executable test: inspect runner call order.
   Result: `_reference_results` computes all reserve trials before `_evaluate` performs
   development selection. Selection uses only development values, but the frozen
   select-before-read rule is still violated. The reserve is descriptive, not untouched proof.
6. **Medium — timing/leakage attack found no price-feature leakage.** Signals depend only on
   already-known UTC timestamps, ordinary fills require exact next-open adjacency, pending
   signals expire at gaps, and price mutation leaves signals unchanged. This does not repair
   the successful attacks above.
7. **Medium — engine-role completeness missing.** Freqtrade directional Spot and
   Nautilus event-driven conformance were required by the roadmap but absent from the campaign.
   Decimal/vectorbt parity is useful but not the full Task 3 acceptance package.

## Risk and security review

Risk verdict: `REJECT`. The strategy breaches the absolute drawdown limit, loses under hard
cost stress, lacks empirical spread/impact/capacity evidence, and fails multiple-testing and
benchmark gates. No weighted score or positive subperiod may offset those hard failures.

Security verdict for this run boundary: `PASS_OFFLINE_CONTAINMENT_ONLY`. The run required no
secrets and had no venue or order path. This is not a stage-exit security approval and grants no
paper/demo/live authority.

## Inferences, recommendations, and unknowns

Inference: a real Wednesday return pattern may exist in this historical sample, but the
evidence is too cost-sensitive, drawdown-heavy, and selection-unstable to be decision-useful as
a promoted strategy.

Recommendation: close this exact family/context without parameter, hour, weekday-combination,
filter, exit, sizing, or threshold rescue. Any future work must begin with a genuinely distinct
family, a new complete hierarchy, and unseen evidence. Do not reuse the nominal reserve as an
untouched holdout.

Unknowns remain empirical bid/ask spread, impact, capacity, venue-specific minimums, and
event-driven conformance. They are not worth acquiring for this rejected StrategyVersion.

## Final authority statement

No bot was activated. No synthetic account, paper/demo/testnet venue, live venue, credential,
order, position, portfolio, or execution authority was created. HG-3 was not prepared because
the prerequisite `COMPLETE_APPROVABLE` validation status is absent.
