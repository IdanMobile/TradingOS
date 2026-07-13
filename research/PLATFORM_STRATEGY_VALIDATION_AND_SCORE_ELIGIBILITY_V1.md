# Platform strategy validation and score eligibility V1

Review time: `2026-07-13T12:18:18Z`  
Mode: official-source platform review  
Execution authority: `NONE`  
Venue connection: `NONE`  
Promotion authority created: `false`

## Decision first

TradingOS should reuse platform validation capabilities as independent evidence lanes,
but it must not inherit any platform metric, ranking, optimization result, or published
backtest as approval.

The four reviewed platforms expose materially useful controls:

- Freqtrade detects lookahead and recursive-indicator defects, retains backtest inputs,
  supports explicit optimization objectives, and recommends dry-run comparison;
- QuantConnect/LEAN exposes detailed result statistics and replaceable fill, fee,
  slippage, buying-power, and brokerage reality models;
- MetaTrader 5 supports explicit optimization populations, forward-period retesting,
  real-tick or simplified simulation modes, execution delay, commissions, margin, and
  multiple optimization criteria; and
- TradingView exposes strategy properties, trades, costs, drawdown, Sharpe, Sortino,
  profit factor, buy-and-hold comparison, forward updating, and lower-timeframe Bar
  Magnifier fills.

None of the reviewed official documentation defines a universal strategy-admission
threshold that proves a strategy is robust, locally reproducible, correctly selected,
or safe to promote. MetaTrader displays heuristic colors and filters, QuantConnect
reports a probabilistic Sharpe ratio, Freqtrade optimizes a chosen loss function, and
TradingView reports performance metrics. Those are measurements or selection aids, not
independent approval decisions.

Therefore TradingOS keeps its locked rule:

`independent dimensions + hard gates + complete evidence -> eligibility`

and rejects:

`one blended platform score -> approval`.

## Scope and method

This review answers two separate questions:

1. How do established strategy platforms help validate a strategy?
2. When is a TradingOS result eligible to receive a score or promotion decision?

Only current official platform documentation was used for platform claims. Community
posts, strategy marketplaces, vendor rankings, and promotional profit claims were
excluded. Documentation is continuously maintained; the retrieval time above is the
version boundary for this review.

The platforms were selected because they are already relevant to the repository's
reuse architecture or external evidence intake. This is not a claim that they are the
only or universally best platforms.

## Platform comparison

| Platform | Useful validation controls | Score/selection surface | Official limitation material to TradingOS | Reuse boundary |
|---|---|---|---|---|
| Freqtrade | Backtest export; lookahead analysis; recursive analysis; explicit fees; dry-run comparison | User-selected Hyperopt loss such as Sharpe, Sortino, drawdown, Calmar, profit/drawdown, or multi-metric | Backtests assume fills; documentation warns that impressive ranked backtests may be unrealistic; identical Hyperopt/backtest configuration is required for comparison | Directional Spot research, bias diagnostics, and dry-run parity evidence; never approval authority |
| QuantConnect/LEAN | Backtest statistics; PSR; fill, fee, slippage, margin, and brokerage models; walk-forward optimization | Objective function chosen by the researcher; reports PSR, drawdown, capacity, fees, Sharpe, expectancy, turnover, and other metrics | Default model choices can be materially optimistic; official paper brokerage documentation shows zero crypto fees and null slippage in the default model | Independent event-driven reproduction and explicit reality-model stress; TradingOS must override unsuitable defaults |
| MetaTrader 5 | Complete/genetic optimization; forward retest; real/generated ticks; delay; account, margin, and commission settings | Profit, drawdown, recovery factor, Sharpe, custom criterion, or complex criterion; forward-tests the top 10% of full-search or 25% of genetic runs | Rough modes can omit commissions and margin or create unrealistic results; UI colors/filters are heuristics, and the chosen criterion can be changed when viewing cached results | External reference for forward optimization, execution-delay stress, and parameter-surface visualization; not canonical engine or approval authority |
| TradingView | Strategy properties; trade list; commission/slippage; drawdown; Bar Magnifier; deep backtesting; realtime forward updates | Total P&L, profit factor, Sharpe, Sortino, drawdown, trade statistics, buy-and-hold comparison | Broker emulator uses chart data and intrabar assumptions; non-standard charts and some calculation settings can produce unrealistic or repainting results | Public-strategy discovery and independently reproduced comparison evidence only |

## What each platform actually validates

### Freqtrade

Verified official capabilities:

- `lookahead-analysis` reruns and perturbs a strategy to identify indicator or signal
  changes caused by future information;
- `recursive-analysis` recalculates indicators with different startup histories to
  expose values that change between bounded live history and full-history backtests;
- Hyperopt requires an explicit objective/loss function and records epochs;
- backtest export includes the strategy, parameters, sanitized configuration, report,
  and market-change data, subject to the same data remaining available; and
- Freqtrade explicitly recommends dry-run comparison after backtesting and warns that
  backtests assume orders fill.

What it does not establish:

- absence of every form of selection bias;
- complete trial-family accounting across work done outside Hyperopt;
- point-in-time universe correctness;
- a universal Sharpe, drawdown, or profit-factor pass threshold;
- deployable capacity or account-specific execution; or
- promotion eligibility.

TradingOS use: Freqtrade's lookahead and recursive analyses are blocking technical
checks for a compatible directional Spot strategy. A clean result is necessary but not
sufficient. Dry-run is not activated in the current phase.

Official sources:

- [Freqtrade Strategy Quickstart](https://www.freqtrade.io/en/stable/strategy-101/)
- [Freqtrade lookahead analysis](https://docs.freqtrade.io/en/latest/lookahead-analysis/)
- [Freqtrade recursive analysis](https://docs.freqtrade.io/en/stable/recursive-analysis/)
- [Freqtrade Hyperopt](https://www.freqtrade.io/en/stable/hyperopt/)
- [Freqtrade backtesting](https://www.freqtrade.io/en/stable/backtesting/)

### QuantConnect / LEAN

Verified official capabilities:

- reports PSR, fees, total trades, drawdown, net profit, Sharpe, expectancy, capacity,
  turnover, and other portfolio statistics;
- defines PSR as the probability that estimated Sharpe exceeds a benchmark;
- supports scheduled walk-forward optimization over trailing windows;
- exposes replaceable fill, slippage, fee, buying-power, and brokerage models; and
- can model partial/stale fills and use quotes, trades, or bars according to the
  selected fill model.

Material official caveat: the default paper brokerage uses null slippage and zero fees
for crypto and crypto futures. A backtest using those defaults would fail the TradingOS
realistic-cost gate unless explicitly replaced and evidenced. Official slippage docs
also state that missing volume in some crypto data can make a volume-share model return
zero slippage.

What it does not establish:

- that a reported PSR used the TradingOS campaign-wide trial hierarchy;
- that the benchmark or return sampling matches the preregistration;
- that walk-forward frequency was chosen before results;
- that default reality models match an intended venue/account; or
- promotion eligibility.

TradingOS use: LEAN is an independent event-driven reproduction lane and a reality-model
stress lane. TradingOS owns the frozen costs, fills, hierarchy, and eligibility decision.

Official sources:

- [QuantConnect backtest results](https://www.quantconnect.com/docs/v2/cloud-platform/backtesting/results)
- [QuantConnect walk-forward optimization](https://www.quantconnect.com/docs/v2/writing-algorithms/optimization/walk-forward-optimization)
- [LEAN trade-fill key concepts](https://www.quantconnect.com/docs/v2/writing-algorithms/reality-modeling/trade-fills/key-concepts)
- [LEAN slippage models](https://www.quantconnect.com/docs/v2/writing-algorithms/reality-modeling/slippage/supported-models)
- [QuantConnect paper brokerage model](https://www.quantconnect.com/docs/v2/writing-algorithms/reality-modeling/brokerages/supported-models/quantconnect-paper-trading)

### MetaTrader 5 Strategy Tester

Verified official capabilities:

- complete enumeration or genetic parameter optimization;
- a fixed forward-period split using the latest half, third, quarter, or custom period;
- forward evaluation of the best 10% of full-search passes or 25% of genetic passes,
  with at least 256 passes when enough exist;
- real-tick and generated-tick modes, configurable delay, symbol/account settings,
  margin, and commission schedules; and
- per-pass profit, trades, profit factor, expected payoff, drawdown, recovery factor,
  Sharpe, inputs, and optimization criterion.

The official interface permits filters that hide no-trade, losing, drawdown-over-50%,
recovery-under-1, or Sharpe-under-0.5 passes. It also colors Sharpe over 2, recovery over
2, and complex criterion over 80 favorably. These are display/filter conventions, not
evidence that the remaining passes are statistically valid.

The documented rough `profit in pips` mode eliminates swaps and commissions and does not
perform margin control. The MQL5 testing documentation also warns that simplified OHLC
simulation can create a historical “grail” that fails online and recommends retesting
apparently exceptional results with the accurate tick mode.

What it does not establish:

- a preregistered global trial hierarchy;
- correction for trying multiple EAs, symbols, periods, or optimization criteria;
- point-in-time data provenance independent of the connected trade server;
- DSR/PBO or neighborhood robustness; or
- promotion eligibility.

TradingOS use: forward-selection mechanics and execution-delay/tick-mode stress are
design inputs. MetaTrader's filters and colors do not become TradingOS thresholds.

Official sources:

- [MetaTrader 5 strategy optimization](https://www.metatrader5.com/en/terminal/help/algotrading/strategy_optimization)
- [MetaTrader 5 strategy testing](https://www.metatrader5.com/en/terminal/help/algotrading/testing)
- [MQL5 testing reference](https://www.mql5.com/en/docs/runtime/testing)

### TradingView Strategy Report

Verified official capabilities:

- reports P&L, commission, buy-and-hold comparison, drawdown, trade outcomes, Sharpe,
  Sortino, profit factor, margin calls, and a complete simulated trade list;
- records symbol, timeframe, date range, strategy inputs, capital, sizing, margin,
  pyramiding, commission, and slippage in strategy properties;
- supports deep historical backtesting and realtime forward updates; and
- offers Bar Magnifier to replace some OHLC intrabar assumptions with lower-timeframe
  data.

Official documentation warns that:

- the broker emulator otherwise infers intrabar paths from chart OHLC;
- non-standard charts use synthetic prices and can produce non-reproducible fills;
- historical and realtime calculations can differ or repaint;
- `calc_on_order_fills` can produce unobtainable fills in some cases; and
- costs must be configured or historical profitability may be overstated.

What it does not establish:

- a multi-symbol controlled search population;
- full external data provenance and immutable raw bytes;
- independent reproduction of Pine semantics;
- selection-bias correction; or
- promotion eligibility.

TradingOS use: public strategy reports remain discovery/comparison evidence. Only
visible, legally reusable code with complete settings can enter independent local
reproduction, and even then its TradingView result is not inherited.

Official sources:

- [TradingView Pine strategy concepts](https://www.tradingview.com/pine-script-docs/concepts/strategies/)
- [TradingView Strategy Report overview](https://www.tradingview.com/support/solutions/43000764138-tradingview-strategy-report-how-to-start/)
- [TradingView deep backtesting](https://www.tradingview.com/support/solutions/43000666265-how-deep-backtesting-works/)
- [TradingView unrealistic non-standard charts warning](https://www.tradingview.com/support/solutions/43000481029-strategy-produces-unrealistic-results-on-non-standard-chart-types-heikin-ashi-renko-etc/)
- [TradingView calculation/repainting warning](https://www.tradingview.com/support/solutions/43000483946-i-believe-that-the-strategy-is-giving-the-wrong-results/)

## TradingOS score eligibility

TradingOS has no blended approval score. This is already binding in the Scorecard
contract: dimensions remain independent; `NOT_RUN` blocks eligibility; and a hard fail
cannot be averaged away.

The following terms are now explicit:

### Metric eligibility

A metric may be computed only when its mathematical inputs and conventions are complete.
Examples:

- Sharpe/Sortino require a declared return frequency, annualization rule, risk-free
  convention, and enough non-constant observations;
- DSR requires the complete declared trial hierarchy, selection rule, return
  distribution inputs, and effective-trial method;
- PBO requires the complete comparable trial population and preregistered CSCV method;
- profit factor requires realized winning and losing observations and is undefined when
  the denominator is zero;
- capacity requires volume/quote inputs and an explicit impact model; and
- trade-level statistics require causal fills and a nonzero event count.

An ineligible metric is `NOT_RUN` or `NOT_APPLICABLE_WITH_REASON`, never zero and never
silently imputed.

### Scorecard eligibility

A StrategyVersion/context can receive a governed TradingOS scorecard only when all of
the following exist:

1. immutable StrategyVersion and exact context identity;
2. checksum-pinned point-in-time dataset and provenance;
3. frozen family hierarchy, transformations, parameters, trial bound, selection metric,
   split policy, cost grid, and stop rules;
4. one retained terminal record for every declared trial, including failures;
5. causal signal/fill evidence and applicable lookahead/recursive checks;
6. declared benchmark and after-cost return stream;
7. environment and engine-version evidence; and
8. explicit blockers for unavailable dimensions.

Before these conditions, research diagnostics may be retained, but the subject remains
`UNVALIDATED / NOT_ELIGIBLE` and receives no approval score.

### Promotion eligibility

Promotion is a separate state decision. It requires:

- every mandatory G1-G11 gate completed for the exact context;
- no hard fail or missing required dimension;
- realistic after-cost economics rather than zero-cost-only profit;
- chronological untouched evidence and walk-forward stability;
- stable parameter neighborhoods and regime behavior;
- adequate event count;
- cross-engine or independent-reference reproduction;
- campaign-wide `PBO <= 0.5` and corrected `DSR >= 0.95` with complete hierarchy;
- independent statistical, risk, supervisor, and security review; and
- `COMPLETE_APPROVABLE` with `promotion_eligible=true`.

A platform Sharpe, PSR, profit factor, forward-test match, Hyperopt rank, public strategy
report, or marketplace status cannot waive any item.

## Reuse decisions

| Capability | Decision | Reason |
|---|---|---|
| Freqtrade lookahead/recursive analysis | Reuse | Strong compatible defect checks; retain output as blocking evidence |
| Freqtrade Hyperopt | Conditional reuse | Accelerator only after TradingOS freezes the complete hierarchy and retains every epoch |
| LEAN reality models | Reuse with explicit overrides | Valuable event-driven lane; default crypto costs/slippage are unsuitable |
| LEAN statistics/PSR | Comparison only | Useful diagnostic, but not corrected for the TradingOS campaign hierarchy by default |
| MetaTrader optimization/forward mechanics | Pattern reuse | Helpful split and surface concepts; no need to adopt a second canonical engine |
| MetaTrader filters/complex criterion | Do not inherit | Heuristic display/selection, not statistical approval |
| TradingView Strategy Report | External comparison | Useful transparent settings and metrics when captured completely |
| TradingView public ranking/publication | Discovery only | Publication and simulated results are not local validation |

## Consequence for the next strategy campaign

Before any FAMILY-SELECT-V2 candidate is scored:

- freeze its complete search population and one primary selection metric;
- keep platform metrics as named dimensions, not an aggregate rank;
- require causal next-observation fills and explicit nonzero cost cells;
- run compatible lookahead/recursive checks;
- retain all trials and failed runs;
- reserve a latest chronological family-unseen evaluation period;
- compare against buy-and-hold/cash and opportunity cost;
- compute DSR/PBO only from the complete declared hierarchy; and
- leave promotion and execution authority false until every independent gate passes.

No networked dry-run, paper, demo, testnet, or live session is authorized by this
report.
