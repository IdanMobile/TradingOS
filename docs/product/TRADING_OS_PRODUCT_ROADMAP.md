# Trading Intelligence OS — Product Roadmap

Status: **Active roadmap; constrained S2 research-only operation is current, with the dormant S3 paper architecture locked by D-043.**
Date: 2026-07-12

This roadmap translates the North Star and the detailed operator goal into an
implementable product sequence. It does not expand the current authorization to
live trading or real-money credentials.

## Product destination

Trading Intelligence OS is a single-operator research, evidence, portfolio-risk,
and future execution control surface. It should answer, with linked evidence:

- what the market is doing now;
- what is being researched and why;
- which strategies survived which tests and in which context;
- what is running in backtest, paper, or live mode;
- what orders, positions, TP/SL levels, exposure, and risk limits exist;
- what failed, degraded, or must be retired;
- which data, engines, AI models, prompts, and workflows produce useful results.

The product is not a signal-selling page and does not convert a chart pattern or
backtest into a profit claim.

## Staged implementation

### Stage S1 — Evidence OS (complete through HG-2)

Scope: Crypto Spot, BTCUSDT/ETHUSDT, 5m/15m/1h, no money.

- frozen canonical dataset and reproducible baseline runs;
- engine bake-off, lineage, validation, cost stress, and red-team evidence;
- read-only dashboard with live project state;
- read-only market monitor with TradingView attribution;
- historical strategy markers and evidence links where artifacts support them;
- explicit rejected/deferred states.

No order commands, credentials, portfolio mutations, approvals, or live venue
connections are enabled in S1.

### Stage S2 — Native research console (current)

Entry: satisfied by the prototype evidence decision, HG-2 (D-036), and architecture
lock (D-037). The former product wave 7 is a product-facing slice of S2, not a parallel
execution track.

- extend the existing replaceable projection-first console; framework replacement is deferred;
- TradingView Lightweight Charts for owned chart composition and annotations;
- canonical candle query/datafeed API;
- selectable symbol/timeframe/range;
- indicators and overlays calculated from reproducible inputs;
- backtest buy/sell/fill markers, equity/P&L panels, and evidence drawers;
- strategy-context comparison pages;
- typed read-only portfolio/risk projections;
- search over registries and report artifacts.

The console remains execution-inert. Its only writes before the paper cockpit are the
two audited, loopback-only operator routes approved by D-038 and D-041:
`POST /api/v1/workspace-actions/decision` and
`POST /api/v1/workspace-actions/data-update`. Neither route can connect a venue,
carry credentials, mutate approval or synthetic capital, route an order, or control
paper/demo/live execution.

Lightweight Charts is preferred for the OS-owned chart because it is public,
Apache-2.0 licensed, fast, and supports series markers. It is a visualization
library, not a market-data source or broker.

### Stage S3 — Paper operations

Entry: an approved HG-3 stage-gate record and at least one validation-approved
strategy-context configuration. `SIG-VOLUME-BREAKOUT` remains research-only and is
not eligible to start a paper bot.

- `SYNTHETIC_LOCAL_SIMULATOR` is the locked first S3 architecture: Binance public
  data-only market observations, synthetic USDT, and local simulated fills only;
- no API key, account endpoint, credential, venue order route, or exchange order;
- `execution_authority=NONE`, `venue_connection=NONE`, `paper_orders=DISABLED`, and
  `live_orders=DISABLED` remain binding even while the local simulator runs;
- public Binance closed bars and quotes are observations used by the simulator, not
  evidence of a connected account or live execution;
- typed order, fill, position, account, and portfolio snapshot records;
- typed bot, signal-watch, attention, finding, portfolio-performance, and cockpit
  snapshot records for the humanized operating view;
- bracket TP/SL semantics and exchange constraints;
- independent risk engine with pre-trade checks, stale-data guards, drawdown
  limits, exposure limits, and kill switch;
- backtest-versus-paper divergence reports;
- chart annotations for paper signals, orders, fills, positions, TP, and SL;
- operational drills and immutable audit trail.

### Stage S4 — Human-gated live eligibility

Live trading is a separate product capability, not an automatic consequence of
S3. It requires human approval, verified venue/account eligibility, restricted
keys without withdrawal permission, capital and drawdown limits, kill-switch
drills, monitoring, and a context-specific approval record.

If TradingView Trading Platform access is obtained, its Broker API can provide the
chart-side order ticket, positions, executions, and bracket TP/SL presentation.
The OS backend remains responsible for authentication, risk decisions, order
routing, reconciliation, and fail-closed behavior. Without that access, the OS
uses its own Lightweight Charts UI and broker adapter.

## Canonical domain contracts for paper operations

Durable identity/evidence records must carry stable IDs, UTC timestamps, decimal
money/price/quantity, environment, strategy context, and provenance. Immutable
ephemeral cockpit value/projection rows may instead use their typed identifier/subject/source
and event/observation/as-of fields; they remain UTC and decimal-exact, carry source/environment/
provenance where applicable, and cannot authorize a transition:

- `MarketBar` / `MarketQuote` / `MarketDepthSnapshot`;
- `SignalEvent`;
- `OrderIntent` and `OrderState`;
- `FillEvent`;
- `PositionSnapshot`;
- `AccountSnapshot` / `PortfolioSnapshot`;
- `BracketLevels` (`stop_loss`, `take_profit`, optional trailing rules);
- `RiskDecision`;
- `ApprovalRecord`;
- `ChartAnnotation` linked to evidence and lifecycle environment.
- `PaperBotSnapshot` / `SignalWatchSnapshot`;
- `AttentionItem` / `FindingItem`;
- `PortfolioPerformance` / `CockpitSnapshot`.

Strategy logic may propose an intent and levels; only the independent risk and
approval layers may permit paper/live routing.

The paper/cockpit records are additive projections. They do not change the existing
S2 validators, S2 reachable approval states, or the historical-research contracts.

## Chart and market-data strategy

TradingView has three materially different integration paths:

1. **Widgets** — immediate embedded display with TradingView-provided data and
   attribution; suitable for the S1 read-only monitor.
2. **Advanced Charts** — richer custom charting with our own Datafeed API/UDF,
   but access-controlled, non-redistributable, and not a market-data source.
3. **Trading Platform** — restricted broker product with Broker API and bracket
   order capabilities; evaluate only for S4 after direct access/licensing review.

The OS must never treat TradingView chart libraries as a data entitlement, never
publish restricted library files, and never infer that a Broker API call itself
executed an order.

## Dashboard information architecture

Progressive disclosure keeps the first screen simple:

1. Overview — environment, health, evidence status, open actions;
2. Market Monitor — live/read-only chart, watchlist, market context;
3. Research — hypotheses, sources, campaigns, knowledge assets;
4. Strategies — canonical versions, contexts, lifecycle;
5. Backtests — runs, metrics, trades, equity, costs;
6. Validation — gates, red-team, contradictions, approval boundary;
7. Paper Operations — orders, fills, positions, portfolio, divergence;
8. Risk & Approvals — independent checks and human decisions;
9. AI Center — model/agent/prompt cost, quality, and downstream value;
10. Data, Engines, Dictionary, Memory, Settings.

S2 exposes only the evidence-safe subset. Paper and live views remain visibly
separate and empty until their gates exist.

## Acceptance gates for the product path

Each stage must leave machine-readable evidence and pass the local gate. No stage
may claim completion from UI appearance alone:

- chart bars match a declared source, symbol, timeframe, timezone, and freshness;
- every signal/order/fill/TP/SL annotation has an environment and provenance;
- paper account state reconciles from immutable events;
- risk decisions are independent of strategy code;
- live commands are unreachable until the human gate and restricted credentials
  exist;
- backtest, paper, and live results are compared using the same canonical metrics;
- rejected strategies and failed operations remain queryable.

## Automation and AI-provider controls

Deterministic work should run without AI: data freshness checks, dataset quality,
bounded historical backtests, fee/slippage grids, validation gates, scoring
projections, and report generation. S2 may add a persisted local scheduler only after
the identical allowlisted command proves idempotent reuse without recomputation and
preserves partial/failed evidence. No real `LAB-*` batch or enabled scheduler is implied
by the architecture lock.

AI remains an optional research dependency. `TIOS_AI_MODE` defaults to `mock` and
must be set to `real` together with one explicit `TIOS_AI_PROVIDER` before any
provider adapter may use the network. Anthropic, OpenAI, and Google keep separate
ignored local keys. Missing provider selection or credentials fails closed; the
dashboard may show configuration presence but must never display a secret value.

AI may propose research, extraction, or red-team output. It may not approve risk,
route an order, modify paper/live capital, or bypass a deterministic gate.

The first S3 paper portfolio uses real public market observations with explicitly
synthetic USDT and an immutable local paper ledger. The implementation may remain
dormant in S2, but no bot may start until HG-3 and a matching validation-approved
strategy context exist. It is not an exchange account and cannot be upgraded to real
capital merely by changing a frontend toggle.

## Reuse register for this roadmap

- TradingView Widgets: immediate read-only market display.
- TradingView Lightweight Charts: preferred owned charting layer for S2+.
- Existing Parquet + DuckDB: historical candle query and analytics foundation.
- Existing normalized engine results: trade/fill/equity evidence foundation.
- MLflow + DVC: prototype-proven generic lineage beneath the custom evidence registry;
  D-037 locks retention, backup, migration, and access boundaries; the S2 restore check
  remains executable exit evidence.
- Engine roles: vectorbt research acceleration; Freqtrade isolated Crypto Spot
  event/reproduction; NautilusTrader bounded event simulation; Hummingbot deferred
  bot-operations/market-making; LEAN deferred multi-asset portability. Deferred
  adapters and normalized artifacts remain evidence-only/deferred assets; no engine is
  the OS’s approval, risk, venue, paper, or live authority.

Sources verified 2026-07-10:

- https://www.tradingview.com/widget-docs/getting-started/
- https://www.tradingview.com/charting-library-docs/latest/getting_started/
- https://www.tradingview.com/charting-library-docs/latest/connecting_data/datafeed-api/
- https://www.tradingview.com/charting-library-docs/latest/trading_terminal/
- https://www.tradingview.com/charting-library-docs/latest/trading_terminal/trading-concepts/orders/
- https://www.tradingview.com/charting-library-docs/latest/trading_terminal/trading-concepts/brackets/
- https://github.com/tradingview/lightweight-charts
