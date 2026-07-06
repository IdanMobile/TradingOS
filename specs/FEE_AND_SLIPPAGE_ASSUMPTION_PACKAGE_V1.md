# Fee and Slippage Assumption Package V1

Status: Approved for first Crypto Spot bake-off and validation prototypes.

## Principle

No strategy may be approved from a single optimistic transaction-cost assumption. All economic results must state fees and slippage explicitly.

## Fee scenarios

### F0 — Zero-fee diagnostic
- Entry: 0
- Exit: 0
- Use: debugging/parity only
- Never valid as profitability approval evidence

### F1 — Baseline spot fee
- Entry: 0.10%
- Exit: 0.10%
- Rationale: current Binance regular-user Spot fee page shows 0.100% maker/taker baseline in the checked schedule.
- Reverify before execution.

### F2 — Fee stress
- 1.5 × F1
- Entry: 0.15%
- Exit: 0.15%

### F3 — Venue-specific
- Load the current operator-specific maker/taker schedule for the venue under evaluation.
- Record date checked and account tier.

## Slippage scenarios

### S0 — zero slippage diagnostic
0 bps/side. Debugging only.

### S1 — low
1 bp/side.

### S2 — medium
5 bps/side.

### S3 — high
10 bps/side.

### S4 — empirical/adverse
Derived from observed spreads, volatility, order size, and/or higher-resolution market data. Required before serious live promotion.

## Mandatory scenario grid

At minimum run:
- F0/S0 (diagnostic)
- F1/S1
- F1/S2
- F1/S3
- F2/S2
- F2/S3

## Interpretation rules

- A result that is profitable only under F0/S0 is rejected as economic evidence.
- High-turnover strategies receive stronger transaction-cost scrutiny.
- Scenario sensitivity must be shown as a surface/table, not one number.
- Fees, spreads, slippage, and funding are separate concepts.
- For Spot V1, funding is N/A.

## Re-verification trigger

Recheck assumptions when:
- venue changes;
- fee tier changes;
- pair changes;
- order type changes;
- liquidity regime changes;
- strategy turnover changes materially;
- before paper/live promotion.

## Current primary source

- Binance Spot fee schedule: https://www.binance.com/en/fee
