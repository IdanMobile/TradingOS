# Short-frame execution conformance report — 2026-07-23

## Scope and conclusion

The production verification of
`SHORTFRAME-BAR-HIERARCHY-AND-FILL-AVAILABILITY-V1` passed for the frozen
`DS-CRYPTO-SPOT-SHORTFRAMES-V1` dataset. The result establishes bounded
cross-frame data consistency and conservative signal-to-fill availability for
BTCUSDT and ETHUSDT across 1m, 5m, and 15m bars. It does not establish a
profitable strategy or realistic trade execution.

The artifact reports:

- `verification_status`: `PASS`
- `hierarchy_status`: `SOURCE_DIVERGENCES_PRESENT`
- top-level `status`: `PASS`
- `execution_authority`: `NONE`

The source divergences are the preregistered, pinned native-source evidence. The
native parent candle remains source truth; no divergence was repaired, replaced,
or reclassified to make the result pass.

## Verified facts

### Evidence identity

| Field | Verified value |
| --- | --- |
| Protocol ID | `SHORTFRAME-BAR-HIERARCHY-AND-FILL-AVAILABILITY-V1` |
| Protocol SHA-256 | `f24b8272c9328789db71dc1152c51ecb6b9aa2cc06a0257392b63627b273b4d1` |
| Committed code identity | `ea3b2a9e25d47dd67e2a2b35679101ae8cdcc487` |
| Dataset ID | `DS-CRYPTO-SPOT-SHORTFRAMES-V1` |
| Dataset manifest SHA-256 | `05ccd69008c54f14f3b3299226e27c313d60fa224bf9b701e11ecc92beec7ce4` |
| Dataset quality SHA-256 | `cd281975e187f8e1cf43fd62fe03585891cf8c02cd44baf319575e42837f1186` |
| Stable artifact SHA-256 | `564f6f5481cf7811df173be7958ebbd5232d446d0ef246a1077a655114350ff2` |
| Canonical analysis SHA-256 | `ca475af65191eac72b18e6c780d666e3af779f67d9e38fbe1a653cca4f074d1a` |
| Fresh production reads | 2 |
| Deterministic equality | `PASS` |
| Frozen dataset window | 2021-01 through 2026-06 |
| Exclusive availability cutoff | 2026-07-01 00:00:00 UTC |

`artifacts/datasets/shortframe_execution_conformance/CURRENT.json` is
byte-identical to
`artifacts/datasets/shortframe_execution_conformance/shortframe_execution_conformance_564f6f5481cf7811df173be7958ebbd5232d446d0ef246a1077a655114350ff2.json`.

### Hierarchy results

| Instrument | Relation | Parent rows | Complete | Incomplete | Exact conformant | Source divergence | Parent missing |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| BTCUSDT | 1m→5m | 577,803 | 577,801 | 2 | 577,770 | 31 | 0 |
| BTCUSDT | 1m→15m | 192,602 | 192,599 | 3 | 192,575 | 24 | 0 |
| BTCUSDT | 5m→15m | 192,602 | 192,600 | 2 | 192,593 | 7 | 0 |
| ETHUSDT | 1m→5m | 577,803 | 577,801 | 2 | 577,768 | 33 | 0 |
| ETHUSDT | 1m→15m | 192,602 | 192,599 | 3 | 192,573 | 26 | 0 |
| ETHUSDT | 5m→15m | 192,602 | 192,600 | 2 | 192,593 | 7 | 0 |
| **Total** | **6 relations** | **1,926,014** | **1,926,000** | **14** | **1,925,872** | **128** | **0** |

The verifier matched the complete exception arrays to the preregistered
inventories:

| Inventory | Count | Canonical array SHA-256 |
| --- | ---: | --- |
| Source divergence | 128 | `f2bd636818eca622bf2eef0bde9caecfc63eb86bcc0f17bec85f711ef9884c86` |
| Incomplete children | 14 | `903ba077846d3ceef579d858322d04e4ffcfc010443cd1f43b07ce32aa52336b` |
| Unavailable gap | 42 | `c832af4617df0a4495b639ae73629d34ddb4f7cf03dc998c0a526486d25e87b8` |
| Outside frozen window | 6 | `e001fb8ec98c610637b03da01dd20b58e3a130e5a6042e277f6c7cbe094e9457` |

### Signal-to-fill availability

| Instrument | Signal frame | Signal bars | Exact nominal-boundary mappings |
| --- | --- | ---: | ---: |
| BTCUSDT | 1m | 2,889,007 | 2,888,999 |
| BTCUSDT | 5m | 577,803 | 577,795 |
| BTCUSDT | 15m | 192,602 | 192,594 |
| ETHUSDT | 1m | 2,889,007 | 2,888,999 |
| ETHUSDT | 5m | 577,803 | 577,795 |
| ETHUSDT | 15m | 192,602 | 192,594 |
| **Total** | **6 tables** | **7,318,824** | **7,318,776** |

The remaining 48 rows were unavailable by rule: 42 nominal boundaries had no
exact one-minute open and six crossed the frozen-window cutoff. The verifier did
not substitute the next later open.

All 30 authenticated early-close rows—five source events represented across two
instruments and three frames—passed
`SOURCE_CLOSE_CANNOT_ADVANCE_ALIGNED_BOUNDARY`. Source close timestamps did not
make a bar available before its nominal aligned boundary.

### Quality and operational gates

- `make check`: `1732 passed, 29 deselected`.
- Independent code review: `PASS`.
- Independent production-artifact audit: `PASS` with no findings and very high
  confidence. It independently recomputed the artifact, canonical-analysis, and
  four full-inventory hashes and reconciled every aggregate.
- Immediately before the production run, the orchestrator loop, dashboard, and
  demo lane were confirmed alive; no restart was required. This is a
  point-in-time observation, not a continuing uptime guarantee.
- The demo lane uses fake money and retained its active stop.
- The conformance run had no trial-budget effect and created no execution
  authority.

## Interpretation

The exact hierarchy classifications and pinned exception digests support the
inference that the frozen short-frame dataset has not drifted from the reviewed
hierarchy inventory. The exact-open availability rule, explicit gap/cutoff
blocks, and early-close non-acceleration check support conservative
next-boundary timing and prevent later-open substitution or early-close
lookahead within this dataset and protocol.

These are data and timing controls. They are necessary inputs to credible
backtesting, but they are not evidence that any strategy has an economic edge.

## Unknowns and non-claims

This verification does not resolve or prove:

- intraminute price path;
- spread, fees, slippage, market impact, latency, queue priority, or partial
  fills;
- strategy validity, parameter robustness, economic significance, or
  out-of-sample performance;
- return, PnL, Sharpe ratio, drawdown, win rate, ranking, selection, promotion,
  or profitability;
- future dataset drift or continuing service uptime.

## Governance and next safe action

Execution authority remains `NONE`. Do not restart or change the demo lane,
change orders, or enable any live path on the strength of this report. Do not
add individual-trade auto-tuning, self-healing, or automatic strategy mutation;
those require a separate preregistered design and review.

The next safe action is the **demo Decision Evidence Bridge**: expose the
already-authorized, fake-money demo decisions and their evidence chain for
operator review without changing execution behavior. This conformance result is
final retained evidence for its bounded data-and-timing claim only.
