# Prospective BTC liquidation-stress first complete-window report

Date: 2026-07-13 UTC  
Frozen observer commit: `eaf2604d786772b008384af2af24cf3497a6f591`  
Signal: `PROSPECTIVE-BTC-LIQUIDATION-STRESS-V1`  
Signal event: `SIG-54b9c184a05a3a037df6495d`  
Supervisor disposition: **COMPLETE WINDOW / WARMUP FLAT / ACTION BLOCKED**  
Execution authority: `NONE`

## Outcome

Observer V2 connected at `2026-07-13T18:43:17.317193Z`, remained continuously connected through
`2026-07-13T18:50:00.005004Z`, and retained the fully enclosed half-open UTC window
`[18:45:00Z, 18:50:00Z)`. Binance published no BTCUSD_PERP forced-order snapshot in that window.
Because coverage is complete, this is a valid zero-event source observation—not an inference that
no liquidation occurred outside the throttled snapshot stream.

The window is `WARMUP_BLOCK` because none of the required 8,640 immediately prior complete windows
exists. The emitted signal is `FLAT`; independent risk remains `BLOCK`; metrics, scorecard, and
promotion are ineligible.

## Verified evidence

| Check | Result |
|---|---|
| Observer frozen before capture | PASS — `eaf2604…` |
| Source coverage | PASS — uninterrupted around the full UTC window |
| Complete windows requested / retained | 1 / 1 |
| Raw snapshot events | 0 |
| Gross / buy / sell snapshot notional | USD 0 / 0 / 0 |
| Window reconstruction | PASS |
| All retained sessions reconstruction | PASS — 2 sessions |
| Session SHA-256 | `2f582162f4296e41d9d85f93db5dfa9e4a42d6f25fc2d06a9253abb50891d810` |
| Signal | `SIG-54b9c184a05a3a037df6495d`, `FLAT`, `PROSPECTIVE_WARMUP_BLOCK` |
| Risk | independent `BLOCK` |
| Metric / scorecard / promotion eligibility | false / false / false |
| Credentials / venue session | none / none |
| Paper / live orders | disabled / disabled |

## Platform eligibility interpretation

The platform review's distinction is enforced: the observer can emit a signal without making it
score-eligible. The immutable identity, exact source bytes, causal window, and environment evidence
advance technical provenance. Missing prospective sample, future labels, costs, benchmarks,
robustness, G1-G11, and independent reviews continue to block scorecard and promotion eligibility.

## Next evidence gate

Continue append-only observation under the unchanged V1 rule. Before outcomes can be analyzed,
freeze a strictly-later Binance Spot BTCUSDT label contract for 1h, 6h, and 24h horizons and prove
that unavailable future labels remain `NOT_AVAILABLE`, never zero or forward-filled. Statistical
review remains prohibited before the complete 30-day warm-up and the later of 180 days or 50
sell-dominant stress events.

## Artifacts

- Session: `artifacts/prospective/BTC-LIQUIDATION-STRESS-V1/session_2f582162f4296e41d9d85f93db5dfa9e4a42d6f25fc2d06a9253abb50891d810.json`
- Observer freeze: `research/PROSPECTIVE_BTC_LIQUIDATION_OBSERVER_V2.yaml`
- Platform eligibility: `research/PLATFORM_STRATEGY_VALIDATION_AND_SCORE_ELIGIBILITY_V1.md`

No bot, account, authenticated venue connection, order, fill, position, paper/demo/live state,
human gate, promotion, or execution authority was activated.
