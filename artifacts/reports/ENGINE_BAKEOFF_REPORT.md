# Engine Bake-off Report

Status: **COMPLETE WITH BOUNDED/RECORDED LANE CONSTRAINTS — role recommendations, not approval.**

This report is generated from normalized artifacts and records bounded windows and
capability gaps explicitly. It does not turn engine metrics into strategy approval.

Normalized run artifacts discovered: **30**.

## Normalized evidence

| Engine | Baseline | Fills | Roundtrips | Fee audit | Artifact |
|---|---|---:|---:|---|---|
| freqtrade | B1BuyAndHold | 2 | 1 | PASS | `artifacts/bakeoff/freqtrade/B1/F0_S0/run1` |
| freqtrade | B1BuyAndHold | 2 | 1 | PASS | `artifacts/bakeoff/freqtrade/B1/F1_S1/run1` |
| freqtrade | B2MaCrossover | 132770 | 66385 | PASS | `artifacts/bakeoff/freqtrade/B2/BTCUSDT/F0_S0/market_probe` |
| freqtrade | B2MaCrossover | 132770 | 66385 | PASS | `artifacts/bakeoff/freqtrade/B2/BTCUSDT/F0_S0/run1` |
| freqtrade | B2MaCrossover | 167992 | 83996 | PASS | `artifacts/bakeoff/freqtrade/B2/F0_S0/run1` |
| freqtrade | B2MaCrossover | 167992 | 83996 | PASS | `artifacts/bakeoff/freqtrade/B2/F0_S0/run2` |
| freqtrade | B2MaCrossover | 5002 | 2501 | PASS | `artifacts/bakeoff/freqtrade/B2/F1_S1/run1` |
| freqtrade | B3BollingerMr | 204872 | 102436 | PASS | `artifacts/bakeoff/freqtrade/B3/F0_S0/run1` |
| freqtrade | B3BollingerMr | 5542 | 2771 | PASS | `artifacts/bakeoff/freqtrade/B3/F1_S1/run1` |
| freqtrade | B4VolBreakout | 104006 | 52003 | PASS | `artifacts/bakeoff/freqtrade/B4/F0_S0/run1` |
| freqtrade | B4VolBreakout | 4772 | 2386 | PASS | `artifacts/bakeoff/freqtrade/B4/F1_S1/run1` |
| hummingbot | B1 | 2 | 1 | PASS | `artifacts/bakeoff/hummingbot/B1/BTCUSDT/F0_S0/run1` |
| hummingbot | B1 | 2 | 1 | PASS | `artifacts/bakeoff/hummingbot/B1/BTCUSDT/F1_S1/run1` |
| hummingbot | B2 | 132924 | 66462 | PASS | `artifacts/bakeoff/hummingbot/B2/BTCUSDT/F0_S0/run1` |
| nautilus | B1 | 2 | 2 | PASS | `artifacts/bakeoff/nautilus/B1/F0_S0/run1` |
| nautilus | B1 | 2 | 2 | PASS | `artifacts/bakeoff/nautilus/B1/F0_S0/run2` |
| nautilus | B1 | 2 | 2 | PASS | `artifacts/bakeoff/nautilus/B1/F1_S1/run1` |
| nautilus | B1 | 2 | 2 | PASS | `artifacts/bakeoff/nautilus/B1/F1_S1/run2` |
| nautilus | B2 | 1848 | 924 | PASS | `artifacts/bakeoff/nautilus/B2/F0_S0/run1` |
| nautilus | B2 | 1848 | 924 | PASS | `artifacts/bakeoff/nautilus/B2/F0_S0/run2` |
| nautilus | B2 | 1848 | 924 | PASS | `artifacts/bakeoff/nautilus/B2/F1_S1/run1` |
| nautilus | B2 | 1848 | 924 | PASS | `artifacts/bakeoff/nautilus/B2/F1_S1/run2` |
| nautilus | B3 | 2396 | 1199 | PASS | `artifacts/bakeoff/nautilus/B3/F0_S0/run1` |
| nautilus | B3 | 2396 | 1199 | PASS | `artifacts/bakeoff/nautilus/B3/F0_S0/run2` |
| nautilus | B3 | 2396 | 1199 | PASS | `artifacts/bakeoff/nautilus/B3/F1_S1/run1` |
| nautilus | B3 | 2396 | 1199 | PASS | `artifacts/bakeoff/nautilus/B3/F1_S1/run2` |
| nautilus | B4 | 1172 | 586 | PASS | `artifacts/bakeoff/nautilus/B4/F0_S0/run1` |
| nautilus | B4 | 1172 | 586 | PASS | `artifacts/bakeoff/nautilus/B4/F0_S0/run2` |
| nautilus | B4 | 1172 | 586 | PASS | `artifacts/bakeoff/nautilus/B4/F1_S1/run1` |
| nautilus | B4 | 1172 | 586 | PASS | `artifacts/bakeoff/nautilus/B4/F1_S1/run2` |

## Role-fit recommendation

| Engine | Current role | Evidence state | Decision boundary |
|---|---|---|---|
| Freqtrade | Crypto backtest / dry-run lane | 11 runs / 4 baselines + pair-isolated parity | Lane complete with constraints; GPL subprocess boundary and slippage gap |
| NautilusTrader | Event-driven simulation candidate | 16 bounded runs / 4 baselines; deterministic and fee-audited | Full-history parity and latency probe remain |
| Hummingbot | Bounded market-making / bot-operations capability lane | 30-day BTCUSDT B1-B4 x F0/F1 x run1/run2 deterministic + retained full-period partials | Full-history B2 F1/S1/B3/B4 remain throughput-constrained; compatibility workaround and timeout cleanup documented |
| LEAN | Bounded portability candidate | Local Docker B1-B4 x F0/F1 plus B1 determinism smoke | Full-range parity remains throughput/scope expansion |
| vectorbt | Research accelerator, not peer engine | Throughput and retention evidenced | Must remain behind overfit controls |

## Cross-engine parity status

Available-lane parity has **zero unexplained residuals**. Pair-level contexts
exist for Freqtrade and Hummingbot: B1 has an expected execution-timing
divergence and BTC-only B2 has an explained, retained execution/data-gap
divergence rather than fill parity. Nautilus is
bounded-window evidence; LEAN and Hummingbot bounded lanes are now retained.
Hummingbot full-history and Nautilus full-history/latency expansion remain documented
throughput/scope tracks and are not fabricated.

## Next actions

1. Present this role-fit evidence at HG-2; no engine is a strategy approver.
2. Treat Hummingbot full-history as a throughput optimization track, not an approval dependency.
3. Use contiguous windows with explicit signal/order/fill timestamps for future parity.
