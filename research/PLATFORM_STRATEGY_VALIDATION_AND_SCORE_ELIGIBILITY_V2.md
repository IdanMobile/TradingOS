# Platform strategy validation and score eligibility V2

Review time: `2026-07-14`

Mode: official-source platform review

Supersedes: V1 for platform-score taxonomy; V1 remains the frozen source boundary referenced by
the prospective signal preregistration

Execution authority: `NONE`

## Supervisor decision

Platform scores fall into three different classes and must not be treated as interchangeable:

1. **diagnostic metrics** describe a backtest or observed return stream;
2. **selection/ranking objectives** order candidates inside a platform-defined population; and
3. **allocation eligibility ratings** decide access to a particular platform programme.

None is, by itself, evidence of locally reproducible edge or TradingOS promotion eligibility.
TradingOS therefore retains independent metric eligibility, scorecard eligibility, and promotion
eligibility. There is no global weighted score, and no platform threshold can waive G1-G11 or an
independent review.

## Official-source comparison

| Platform | What is scored or validated | Eligibility/ranking rule found in official documentation | TradingOS interpretation |
|---|---|---|---|
| Freqtrade | Backtest metrics, explicit Hyperopt loss, lookahead analysis, recursive analysis, and dry-run comparison | The researcher selects the optimization loss; no universal admission threshold is defined | Reuse compatible bias checks and retain every optimization trial; do not inherit rank as approval |
| QuantConnect / LEAN | Backtest statistics including PSR, Sharpe, drawdown, fees, capacity, and turnover; configurable reality models | The Community Strategies leaderboard ranks by recent return and reports a score equal to one-year Sharpe reduced in proportion to less than one year of out-of-sample history | Useful OOS-age penalty and diagnostics; leaderboard eligibility is not complete robustness or multiple-testing evidence |
| MetaTrader 5 | Optimization criteria, parameter surfaces, forward retest, execution delay, tick modes, costs, margin, and drawdown | Forward testing evaluates a selected fraction of optimization passes; UI filters/colors and chosen criteria are heuristics | Reuse forward/parameter-surface patterns; do not inherit colors, filters, or optimization criterion |
| TradingView | Strategy Report P&L, costs, drawdown, Sharpe, Sortino, profit factor, trade list, buy-and-hold comparison, and forward updates | No universal strategy-admission threshold is documented; broker-emulator and chart assumptions materially affect results | Discovery and comparison evidence only; require independent causal replay and complete settings |
| Darwinex Zero | Calibration, independently normalized risk, observed track record, DarwinIA rating, and capital-allocation eligibility | DARWIN creation requires 25 risk-equivalent decisions over at least 15 trading days. DarwinIA SILVER rating combines current-month return (22%), six-month cumulative return (67%), and six-month maximum drawdown (11%), plus track-record bonuses; rating 75 guarantees an allocation under the documented SILVER rules | Strong example of separating sample/calibration eligibility, risk normalization, and programme allocation. Its proprietary return-weighted rating and virtual-allocation threshold do not validate alpha for TradingOS |

## Material current findings

### QuantConnect community score

Official documentation says community strategies are backtested daily for out-of-sample tracking.
The leaderboard ranks by three-month return. Its displayed score is the one-year Sharpe ratio with
a proportional penalty when the strategy has less than one year of out-of-sample history. This is
more disciplined than ranking an in-sample backtest alone, but it remains a leaderboard score: it
does not establish a frozen search hierarchy, realistic account-specific execution, DSR/PBO, or
the TradingOS independent review set.

TradingOS may reuse the principle that insufficient forward history must reduce eligibility, but
will express it as a hard minimum and `NOT_RUN`, not a cosmetic penalty that can be outweighed by a
large return.

### Darwinex calibration, rating, and risk normalization

Darwinex separates three layers:

- calibration requires observations—25 risk-equivalent decisions across at least 15 trading days,
  without requiring a positive return;
- its risk engine normalizes the investable DARWIN independently of the trader, targeting a
  documented 3.25%-6.5% monthly VaR range and applying duration-sensitive leverage caps; and
- DarwinIA rating then ranks/qualifies an observed track record using weighted returns, drawdown,
  and longevity.

That separation is useful architecture. The exact rating is proprietary, return-heavy, tied to a
specific allocation programme, and may lead to virtual allocation. It is not an independent
statistical proof and is not portable as a TradingOS promotion threshold.

TradingOS reuses the separation, not the formula:

`sample eligibility -> normalized risk evidence -> multidimensional validation -> promotion gate`

## TradingOS deterministic eligibility contract

The implementation in `src/tios/validation/eligibility.py` freezes the following semantics.

### Metric eligibility

A named metric is eligible only when inputs and conventions are complete, its declared minimum
sample is met, and retained evidence references exist. An ineligible metric receives blocker codes;
it is never silently represented as zero.

### Scorecard eligibility

A governed scorecard requires exact StrategyVersion/context identity, pinned dataset and
preregistration, complete terminal trial population, causal signal/fill evidence, benchmark and
after-cost return references, environment and engine identity, all ten independent dimensions,
and explicit blockers for every unavailable dimension. A scorecard may truthfully contain failures;
being scorecard-eligible does not mean promotion-eligible.

### Promotion eligibility

Promotion requires all of the following for the exact context:

- scorecard eligibility;
- `COMPLETE_APPROVABLE` with no hard fail;
- exact G1-G11 set, every gate `PASS`, with evidence for every gate;
- every scorecard dimension `PASS`;
- independent statistical, risk, supervisor, and security reviews all `PASS`, each with evidence;
  and
- no live-order capability in the evaluator environment.

The earlier implementation defect that omitted G10 from `MANDATORY_GATES` is corrected. G12 remains
the later paper-forward gate and is not misrepresented as an offline strategy-promotion gate.

## Consequence for the prospective liquidation-stress lane

The active observer is operationally managed, but its current signal remains metric-ineligible,
scorecard-ineligible, and promotion-ineligible. At this implementation checkpoint, four finalized
windows were far below the preregistered
8,640-window warm-up and the later 180-day / 50 stress-event review minima. No platform score or
current flat signal can accelerate those causal requirements.

## Official sources and retrieval boundary

All sources below are official platform documentation, retrieved `2026-07-14`:

- Freqtrade lookahead analysis: https://docs.freqtrade.io/en/latest/lookahead-analysis/
- Freqtrade recursive analysis: https://docs.freqtrade.io/en/stable/recursive-analysis/
- Freqtrade Hyperopt: https://www.freqtrade.io/en/stable/hyperopt/
- QuantConnect Community Strategies: https://www.quantconnect.com/docs/v2/cloud-platform/community/strategies
- QuantConnect backtest report: https://www.quantconnect.com/docs/v2/cloud-platform/backtesting/report
- QuantConnect paper brokerage model: https://www.quantconnect.com/docs/v2/writing-algorithms/reality-modeling/brokerages/supported-models/quantconnect-paper-trading
- MetaTrader strategy optimization: https://www.metatrader5.com/en/terminal/help/algotrading/strategy_optimization
- MetaTrader strategy testing: https://www.metatrader5.com/en/terminal/help/algotrading/testing
- TradingView Pine strategy concepts: https://www.tradingview.com/pine-script-docs/concepts/strategies/
- Darwinex Zero calibration stage: https://www.darwinexzero.com/docs/en/initial-training-phase
- DarwinIA rating: https://www.darwinexzero.com/docs/rating
- Darwinex Zero risk engine: https://www.darwinexzero.com/docs/en/risk-engine

Limitations: documentation can change; DarwinIA's internal rating mapping is proprietary; platform
account, jurisdiction, product, fee, and capital eligibility remain platform/operator-specific and
outside this offline review.
