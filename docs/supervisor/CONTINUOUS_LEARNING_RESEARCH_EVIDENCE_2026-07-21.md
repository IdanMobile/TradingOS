# Continuous-Learning Research Evidence

Date: 2026-07-21  
Scope: current primary sources relevant to evaluation loops, execution reliability, backtest validity, testing, and AI governance

## Findings adopted into the plan

### AI evaluation and observability

- MLflow documents a continuous GenAI loop from production traces to feedback, evaluation datasets, comparative evaluation, and monitoring. Its evaluation APIs can reuse traces offline, which supports frozen regression sets without repeating every expensive model call. Sources: [MLflow GenAI overview](https://www.mlflow.org/docs/latest/genai/overview/), [evaluating production traces](https://www.mlflow.org/docs/latest/genai/eval-monitor/running-evaluation/traces/), and [MLflow tracing](https://mlflow.org/docs/latest/genai/tracing).
- OpenTelemetry provides vendor-neutral traces, metrics, logs, and semantic conventions. GenAI conventions can change, so the Trading OS should own stable internal schemas and export through adapters. Sources: [observability primer](https://opentelemetry.io/docs/concepts/observability-primer/) and [semantic conventions](https://opentelemetry.io/docs/specs/semconv/).
- NIST frames GenAI risk work across Govern, Map, Measure, and Manage throughout the lifecycle. The plan maps this to authority, contextual failure taxonomy, frozen measurement, and controlled promotion/rollback. Source: [NIST AI 600-1](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf).

### Venue execution semantics

- Bybit supports a unique client order identifier (`orderLinkId`, maximum 36 characters). Market orders are converted to IOC limits and can cancel when liquidity or slippage constraints cannot be met. Therefore “market submitted” is not “filled.” Source: [Bybit create order](https://bybit-exchange.github.io/docs/v5/order/create-order).
- A single order can have multiple executions. Execution records include execution IDs, fees, and sequence information, so fills must be accumulated and deduplicated rather than represented as one response. Source: [Bybit execution stream](https://bybit-exchange.github.io/docs/v5/websocket/private/execution).
- The order stream can emit two `Filled` messages in a cancel/fill race, and cancel acknowledgement is asynchronous. The adapter must use a state machine and confirm state through streams/reconciliation. Sources: [Bybit order stream](https://bybit-exchange.github.io/docs/v5/websocket/private/order) and [cancel order](https://bybit-exchange.github.io/docs/v5/order/cancel-order).
- Order history can be delayed; the venue recommends websocket updates for real-time status. Rate limits and order-book snapshot/delta resets also require explicit recovery logic. Sources: [order history](https://bybit-exchange.github.io/docs/v5/order/order-list), [rate limits](https://bybit-exchange.github.io/docs/v5/rate-limit), and [order-book stream](https://bybit-exchange.github.io/docs/v5/websocket/public/orderbook).

These venue sources inform a future adapter only. They do not constitute venue approval, demo activation, or live authority.

### Backtest validity

- Freqtrade supplies dedicated lookahead and recursive-indicator analysis tools. Equivalent checks should be mandatory independent gates, not optional visual inspection. Sources: [lookahead analysis](https://docs.freqtrade.io/en/stable/lookahead-analysis/) and [recursive analysis](https://docs.freqtrade.io/en/stable/recursive-analysis/).
- The Deflated Sharpe Ratio adjusts for selection bias and non-normal returns, while Probability of Backtest Overfitting evaluates selection degradation across sample partitions. These support existing multiple-testing and promotion controls. Sources: [Deflated Sharpe Ratio paper](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf) and [Probability of Backtest Overfitting paper](https://escholarship.org/content/qt4hn4t174/qt4hn4t174.pdf).

### Test speed and reliability

- Pytest provides per-test temporary directories and session-scoped factories, supporting hermetic tests plus cached immutable expensive fixtures. Source: [pytest temporary directories](https://docs.pytest.org/en/stable/how-to/tmp_path.html).
- Hypothesis state machines generate sequences of actions and shrink failures to minimal reproducers. This is well suited to partial fill, cancel, restart, duplicate-event, and reconciliation behavior. Source: [Hypothesis stateful testing](https://hypothesis.readthedocs.io/en/latest/stateful.html).

## Local evidence used

- `handoffs/START_HERE_SINGLE_CODING_AGENT_PROMPT.md`
- `TRADING_OS_NORTH_STAR.md`
- `docs/architecture/AD.md`
- `docs/architecture/MODULE_CATALOG.md`
- `docs/architecture/TYPE_AND_CONTRACT_CATALOG.md`
- `docs/program/S2_AUTONOMOUS_RESEARCH_LAB_PLAN.md`
- `docs/program/DEMO_LANE_PLAN.md`
- `DECISION_LOG.md`, especially D-046 and D-104 through D-107
- `PROJECT_STATE.md` and `MISSING_AND_OPEN_ITEMS.md`
- Existing trading-domain, synthetic execution/risk/stability, experiment, eligibility, and AI benchmark code/tests

## Evidence limits

- No claim is made that the proposed system will guarantee positive returns.
- Vendor documentation defines protocol behavior, not the correctness of the current adapter.
- Academic overfitting measures reduce false confidence but cannot prove future profitability.
- AI explanations are hypotheses until deterministic evidence or prospective tests support them.

