# Future market expansion design review - 2026-07-11

## Scope

Operator decisions authorized design-only work for:

- `T-020-01` perps readiness design review;
- `T-020-02` US equities/ETFs data and broker landscape refresh;
- `T-020-03` core-spine invariance audit.

No implementation, broker connection, credentials, paper/demo/testnet, order
routing, live trading, or real-money path was enabled.

## T-020-01 Perps readiness design

Official/current source observations:

- Freqtrade documents futures support for selected exchanges, including
  exchange-specific isolated futures notes, and warns that liquidation fees are
  not tracked in liquidation P&L calculations.
- Hummingbot has a perpetual market-making strategy for perpetual swap order
  books.
- NautilusTrader models perpetual instruments and describes perpetuals with
  funding-rate, margin, and no-expiry semantics.

Design implication:

- Perps are additive to the current spot spine. They need explicit instrument
  kind, settlement currency, contract size, margin mode, leverage, funding-rate
  event stream, liquidation model, borrow/funding/carry cost gates, and
  exchange-specific fill semantics.
- Spot evidence and validation must not be reused as perps evidence.
- The first S3 perps prototype should be research-only and synthetic until the
  same approval chain used for spot is satisfied.

Minimum future gates:

1. New `InstrumentKind=PERPETUAL` contract and fixtures.
2. Funding-rate and margin/liquidation cost model with known-answer tests.
3. Engine-specific capability report for perps; no fallback approximation.
4. Validation gates requiring funding, liquidation stress, leverage exposure,
   and cross-engine reproduction where supported.
5. No paper/demo/live path before S2 exit, HG-3, validated strategy, security
   review, and specific operator approval.

## T-020-02 US equities/ETFs landscape refresh

Official/current source observations:

- Databento documents corporate actions coverage across 215+ exchanges,
  310,000+ listed/delisted securities, and 60+ event types.
- Databento reference API docs expose corporate actions, adjustment factors,
  and security master concepts.
- NautilusTrader describes a multi-asset, multi-venue system and has an
  Interactive Brokers integration surface in its official docs.

Design implication:

- Equities/ETFs require corporate-action-aware data, point-in-time security
  master identity, symbol/listing continuity, split/dividend adjustment policy,
  market-hours calendars, short-sale constraints, venue/broker order semantics,
  and tax/fee model differences.
- Databento remains a plausible multi-asset data candidate for design, but any
  production use requires credentials/pricing review and retained dataset
  evidence. No paid data access was used here.

Minimum future gates:

1. `EquityListing`/`ETFListing` identity with listing venue, MIC, currency,
   corporate-action chain, and delisting behavior.
2. Corporate-action adjustment policy captured in dataset manifests and
   validation fixtures.
3. Broker integration decision after S3, separate from data vendor decision.
4. Validation gates for calendar gaps, corporate-action replay, borrow/short
   constraints where applicable, and benchmark survivorship bias.

## T-020-03 Core-spine invariance audit

The existing spine remains valid only if expansion preserves these invariants:

| Contract | Must remain true for perps/equities |
|---|---|
| Source -> hypothesis -> spec | Public/source claims never become local proof. |
| Spec -> experiment | Engine projections are derived from canonical specs, not the identity. |
| Experiment -> retained trials | Failures, rejected candidates, and missing dimensions remain retained. |
| Validation | Required dimensions stay independent; no blended global score. |
| Evidence -> approval | No AI, engine, dashboard, or benchmark can approve trading. |
| Execution | Paper/live paths require explicit later HG/operator decisions. |

Design verdict:

- The core spine can support future markets if new instrument/data/cost models
  are additive and validation gates are expanded before any paper/live work.
- Any shortcut that maps perps/equities into the current spot-only contracts
  would violate the spine and must trigger Architecture Guardian review plus a
  decision-log entry.

## Result

`T-020-01`, `T-020-02`, and `T-020-03` are complete for the operator-authorized
design-only slice. Implementation remains deferred to S3+ and requires future
stage authorization.
