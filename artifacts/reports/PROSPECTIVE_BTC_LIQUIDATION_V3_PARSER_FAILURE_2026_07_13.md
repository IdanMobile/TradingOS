# Prospective BTC Liquidation Observer V3 — Diagnosed Parser Failure

Date: 2026-07-13  
Run commit: `8c5ee60`  
Execution authority: `NONE`

## Verified failure

The first V3 retry covered `2026-07-13T19:46:50.260025Z` through `19:50:10.593287Z` and
failed before a complete window. V3 retained the exact rejected public message and reconstructed
the error `LiquidationStressError: invalid force-order snapshot schema`.

Session SHA-256:
`d4278c9bb637195c176583ef21f0a0fd009ac18aa21f4816f87bd5b9213e03e5`.

The message is a BTCUSD_PERP `forceOrder` snapshot with `st: 2` inside the order object `o`. The
parser incorrectly read `st` from the top-level payload. The synthetic fixture encoded the same
mistake, so earlier tests did not detect it. The current Binance liquidation-stream documentation
places order fields under `o`; the retained live byte record establishes the migrated `o.st`
location for this stream.

## V4 correction

Observer V4 reads `o.st`, updates the fixture, and versions new sessions as schema 4. The exact V3
session remains immutable and verifiable as the known pre-fix failure. All source identity,
causality, notional, window, signal, risk, label, and authority rules are unchanged.

The failed V3 interval admits zero complete windows and emits
`SIG-551f7deac66dbcba41fa710d`, `FLAT`, `SOURCE_WINDOW_INCOMPLETE`, and independent `BLOCK`.

No credential, account session, venue connection, order, fill, position, paper/demo/live state,
sealed V2 holdout access, human gate, or execution authority was activated.
