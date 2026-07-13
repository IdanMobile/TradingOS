# Strategy and market-structure catalog

Use this catalog to decide what a strategy needs and where it can fail. Do not treat a named strategy as a complete specification.

| Family | Typical horizon | Main edge hypothesis | Required evidence | Common failure |
|---|---|---|---|---|
| Trend following | hours to months | persistent directional movement | regime, trend strength, costs, exits | sideways whipsaw |
| Momentum / relative strength | minutes to months | recent strength persists or rotates | universe, ranking, turnover, crowding | reversal and crowded exits |
| Breakout | minutes to weeks | range expansion continues after trigger | liquidity, confirmation, false-break rate | failed breakouts |
| Pullback | minutes to weeks | retracement resumes the dominant move | trend context, structure, invalidation | trend reversal |
| Mean reversion | minutes to days | temporary displacement returns toward value | range stability, spread, volatility, costs | trending or news markets |
| Statistical arbitrage | hours to weeks | related assets temporarily diverge | stationarity, hedge stability, execution | structural break |
| Volatility / squeeze | minutes to months | volatility regime transitions | realized versus implied volatility, event calendar | false expansion or decay |
| Funding / basis / carry | hours to months | price or funding differential persists after costs | funding, basis, margin, liquidity, counterparty | regime reversal, liquidation |
| Options / volatility surface | days to months | mispricing or risk premia can be harvested | IV, Greeks, skew, liquidity, assignment | gap, vol expansion, model error |
| Arbitrage | milliseconds to days | executable price or venue differential exceeds all costs | latency, balances, transfer risk, fill probability | fees, latency, transfer/counterparty risk |
| Market making | seconds to days | spread capture exceeds adverse selection | order book, inventory, toxicity, queue position | sharp move and inventory loss |
| Event driven | minutes to months | information changes expected value | event timing, source credibility, reaction study | surprise, rumor, delayed execution |
| Fundamental / valuation | weeks to years | cash flows, quality, or valuation reprice | filings, accounting, estimates, catalysts | valuation trap or regime change |
| On-chain / flow | minutes to months | wallet, exchange, protocol, or stablecoin flows lead price | entity labeling, coverage, lag, false attribution | noisy or manipulated flows |
| Portfolio / allocation | months to years | diversification, trend, factors, or risk budgeting improve compounding | benchmark, correlation, drawdown, rebalance costs | concentration and regime shift |

## Required strategy specification

Every strategy must define:

- objective and market hypothesis;
- asset universe and eligibility rules;
- instrument and venue;
- holding horizon and time stop;
- data inputs and availability timing;
- features, indicators, and exact formulas;
- signal and confirmation rules;
- entry, invalidation, exit, and sizing rules;
- fees, spread, slippage, funding, borrow, and latency assumptions;
- regime filters and no-trade conditions;
- portfolio interaction and correlation limits;
- backtest, paper, and live promotion gates;
- known failure modes and kill conditions.

## Multi-timeframe review

Use higher timeframes for regime and context, middle timeframes for setup, and lower timeframes for execution. Never count correlated indicators or lower-timeframe noise as independent confirmation. Resolve timeframe conflict by reducing exposure, waiting, or rejecting the setup.
