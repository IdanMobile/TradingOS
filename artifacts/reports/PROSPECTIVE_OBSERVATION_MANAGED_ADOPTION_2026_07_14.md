# Prospective observation managed-adoption evidence — 2026-07-14

## Result

The already-running D-095 public observer was adopted by the frozen D-096/D-097 TradingOS
observation service without restart or byte changes. The post-adoption verifier reported
`AVAILABLE / MANAGED / OBSERVING / FRESH`, no blockers, and target `8,640` checkpoints.

At adoption, three consecutive schema-5 checkpoints were finalized from the same process,
connection epoch `2`, and continuity epoch `2`; the longest retained chain was three and `8,637`
checkpoints remained. The bound observer process started at `2026-07-13T21:28:03.839549+00:00`
from commit `2b398c10eaf1c6d7357e88ff85a0f655f4a081bc`.

## Immutable evidence

- adopted intent: `artifacts/prospective/BTC-LIQUIDATION-STRESS-V1/operations/intents/intent_ee043ada0ec765d75152f77e1cbf49fb42a6bdd6a7062e020e5f4dfde9abbc8d.json`;
- checkpoint 1: `session_26e8e787b8be8a7c91395007abf1829740251e1b84d6e6b859abd3c3b079d74e.json`;
- checkpoint 2: `session_c101a81fc34dd6909009ba58ce816e4d7b89f30f6dd712949133cd20b1840565.json`;
- checkpoint 3: `session_1b189a1faab68ce295438f07c9855cc80a50a7f9fd54592bfd4f2b7cb4de2a55.json`.

## Authority and interpretation

Market-data transport is public read-only. Credentials are unused; venue/account connection,
paper orders, live orders, and execution authority are all `NONE` or `DISABLED`. The dashboard has
no observation process-control write path. This proves managed evidence collection only. It does
not validate alpha, permit warm-up analysis, make the signal promotion-eligible, or activate a bot.
