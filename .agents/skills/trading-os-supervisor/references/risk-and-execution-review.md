# Risk and execution review

## Risk hierarchy

Review risk in this order:

1. Account and portfolio risk.
2. Strategy and correlated exposure.
3. Position risk.
4. Order and execution risk.
5. Venue, custody, protocol, and operational risk.

## Position and portfolio checks

Verify:

- risk-based sizing from invalidation distance and account risk;
- volatility and liquidity adjustment;
- aggregate exposure across correlated assets;
- strategy, sector, chain, venue, and stablecoin concentration;
- leverage and liquidation buffer;
- maximum open risk and daily loss limits;
- drawdown circuit breakers and loss-streak handling;
- time stops and stale-signal expiry;
- no martingale or unapproved averaging down;
- portfolio-level cash and reserve policy.

## Stop and target checks

An SL must represent a meaningful invalidation or risk boundary, not an arbitrary percentage. A TP must reflect structure, volatility, expected value, or a defined exit policy. Check partial exits, trailing rules, break-even movement, gap behavior, and what happens when an order is not filled.

## Execution checks

Verify venue-specific behavior for:

- market, limit, stop, stop-limit, trailing, bracket, OCO, and OTOCO orders;
- trigger price and reference price;
- reduce-only and post-only behavior;
- time-in-force;
- partial fills;
- cancel/replace semantics;
- minimum quantity and tick size;
- rate limits and retry behavior;
- duplicate-order prevention;
- clock synchronization;
- position and order reconciliation after restart;
- orphaned orders and disconnected feeds.

## Safe operating stages

`Read-only → research → simulation → paper/testnet → proposal-only → user-approved limited live → monitored live`

Never skip a stage because a strategy looks good in a backtest.
