# Prospective BTC liquidation-stress first-session report

Date: 2026-07-13 UTC  
Frozen implementation commit: `2e385a8e67aa2af0e907d26aca3509ba3de52a7a`  
Signal: `PROSPECTIVE-BTC-LIQUIDATION-STRESS-V1`  
Signal event: `SIG-495ecfb03d8003161565ea47`  
Supervisor disposition: **OBSERVATION STARTED / FLAT / ACTION BLOCKED**  
Execution authority: `NONE`

## Outcome

The first bounded prospective session completed after the signal contract and implementation were
committed. It used the fixed public unauthenticated BTCUSD_PERP force-order stream for 30 seconds.
No forced-order snapshot arrived, which is valid because Binance publishes nothing in a one-second
interval without a liquidation. The session therefore records zero events, an incomplete
five-minute window, a `FLAT` signal, and an independent `BLOCK` decision.

This is an operational/provenance result, not strategy performance. No metric, scorecard,
directional edge, or promotion decision is eligible.

## Verified evidence

| Check | Result |
|---|---|
| Frozen commit precedes observation | PASS — session binds to `2e385a8…` |
| Exchange identity | PASS — `BTCUSD_PERP`, pair `BTCUSD`, perpetual, trading |
| Contract size | PASS — USD 100 from exact exchange-info bytes |
| Exchange-info raw hash | `07a0858c96751c863d3222c70715523a27fa42396d5773171a0025d9d6b1d723` |
| Session content hash | `4638af9e36fa9f34bd800dbc3057f883f3336c04bde50aab2936ff707af6c685` |
| Source status / received events | `COMPLETE` / `0` |
| Signal | `FLAT`, `PROSPECTIVE_SOURCE_WINDOW_INCOMPLETE` |
| Risk decision | `BLOCK`, independent |
| Credentials | none |
| Venue/account session | none; public read-only market-data transport only |
| Paper/live orders | disabled / disabled |

No account, order, position, portfolio, fill, ledger, paper-runtime, venue-authentication, or
execution database was created or changed by the session.

## Interpretation

Zero events in 30 seconds says nothing about liquidation frequency or future returns. It proves
only that the committed observer can connect to the fixed public source, validate exact exchange
identity, retain content-addressed evidence, emit a deterministic signal identifier, and preserve
the independent action block.

## Remaining gate

The current observer deliberately marks a short session as an incomplete window. The next safe
implementation step is deterministic assembly and verification of fully covered UTC-aligned
five-minute windows across bounded sessions, including explicit gaps and zero-event windows. No
statistical review is allowed before 30 days of consecutive complete warm-up and, after that, the
later of 180 calendar days or 50 sell-dominant stress events.

## Sources and artifacts

- Frozen specification: `research/PROSPECTIVE_BTC_LIQUIDATION_STRESS_SIGNAL_V1.yaml`
- Session: `artifacts/prospective/BTC-LIQUIDATION-STRESS-V1/session_4638af9e36fa9f34bd800dbc3057f883f3336c04bde50aab2936ff707af6c685.json`
- Raw exchange info: `artifacts/prospective/BTC-LIQUIDATION-STRESS-V1/raw/exchange_info_07a0858c96751c863d3222c70715523a27fa42396d5773171a0025d9d6b1d723.json`
- Official stream semantics: https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-coin-m-futures/api/ws-streams/~#market-liquidation-order-streams

No bot, order path, credential, paper/demo/live state, human gate, promotion, or execution
authority was activated.
