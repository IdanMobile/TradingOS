# Prospective BTC Liquidation Continuity Session — Fail-Closed Report

Date: 2026-07-13  
Run commit: `0febd4e`  
Execution authority: `NONE`

## Verified result

The bounded seven-window public-read-only observer session connected at
`2026-07-13T19:16:06.378168Z` and ended early at `19:42:55.367740Z` with
`FAILED_LiquidationStressError`.

Session SHA-256:
`78e77d1ff354e7d7078c4ca1df84b1e42b9ef96e4326945e4a805485ebbba8ed`.

The frozen V2 rule correctly admitted **zero** complete windows from the failed session, even
though the coverage interval crossed several aligned boundaries. It emitted
`SIG-add4d803dfe9832fcb326341`, `FLAT`, `SOURCE_WINDOW_INCOMPLETE`, and independent `BLOCK`.
Metric, scorecard, and promotion eligibility remain false.

## Diagnostic limitation and correction

V2 retained only the exception class. It did not retain the exact error text or the rejected
public message, so the underlying source-validation cause cannot be verified and is **unknown**.
It must not be inferred from the absence of admitted events.

D-088 freezes observer V3 before another capture. V3 retains and reconstructs exception type,
message, rejected public message, and receipt time. The signal, source, window, baseline, failed
session, risk, and authority semantics are unchanged.

No credential, account session, venue connection, order, fill, position, paper/demo/live state,
sealed V2 holdout access, human gate, or execution authority was activated.
