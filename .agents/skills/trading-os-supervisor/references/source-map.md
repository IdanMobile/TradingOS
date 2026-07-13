# Initial source map and lessons

This file records why the supplied sources were reviewed and how to use them safely.

## AI-Trader

Source: https://github.com/HKUDS/AI-Trader

Useful patterns:

- bootstrap skill that routes to specialized skills;
- separation of strategy, operation, and discussion objects;
- heartbeat and persistent agent interaction;
- paper challenges, leaderboards, and experiment progress;
- explicit market and portfolio result fields.

Supervisor treatment:

- borrow the modular routing and experiment lineage ideas;
- treat signals, followers, points, and leaderboards as social or experimental data, not proof of edge;
- never copy token registration, copy-trading, or external execution instructions into the brain-only skill.

## Crypto Skills

Source: https://github.com/kukapay/crypto-skills

Useful patterns:

- separate skills for market sentiment, trading strategy, meme scouting, EVM operations, and yield research;
- references and scripts kept outside the main skill body;
- explicit workflows and output formats.

Supervisor treatment:

- use the modular decomposition as a specialist catalog;
- require stronger provenance, formula correctness, regime validation, and cost modeling;
- treat wallet, contract deployment, token minting, and transaction skills as separate high-risk Hands.

The reviewed TA example contains a placeholder MACD signal calculation and a misleading 24-hour volume field. Use it as a review-test example, not as approved logic.

## TradingView / Cointelegraph

Source: https://www.tradingview.com/news/cointelegraph:711ebb18a094b:0-how-to-develop-an-ai-agent-for-crypto-trading/

Useful checklist:

- exchange, on-chain, sentiment, and order-flow data;
- strategy-specific model selection;
- backtesting, walk-forward testing, deployment, and monitoring;
- arbitrage, trend, market making, sentiment, and reinforcement-learning categories.

Supervisor treatment:

- use as an educational checklist;
- verify claims through primary documentation or reproducible research;
- do not assume ML, deep learning, or reinforcement learning automatically creates an edge.

## Dysnix

Source: https://dysnix.com/blog/ai-agents-for-crypto-trading

Useful architecture:

- observation;
- decision logic;
- execution;
- memory and adaptation.

Useful failure modes:

- stale data;
- latency mismatch;
- key-management failure;
- runaway execution loops;
- backtest overfitting;
- self-impact in illiquid markets.

Supervisor treatment:

- use the four-layer decomposition and failure taxonomy;
- verify exchange, latency, and market-adoption claims independently.

## Cobo

Source: https://www.cobo.com/post/agentic-ai-crypto-guide

Useful architecture and governance:

- Brain plus Hands;
- applicability conditions;
- execution policy;
- termination criteria;
- reusable interfaces;
- least privilege, whitelists, multi-party controls, and human approval.

Supervisor treatment:

- keep the supervisor as Brain-only;
- require explicit interfaces and termination criteria for any future Hands;
- treat third-party skills as a supply-chain risk.

## Clawbot and marketplace directories

Sources:

- https://clawbot.ai/skills/crypto-trader.html
- https://claudemarketplaces.com/skills/category/finance

Useful patterns:

- discoverable names and descriptions;
- automatic versus user-invoked skill selection;
- broad strategy taxonomy.

Supervisor treatment:

- use as discovery only;
- reject income promises and unsupported performance language;
- inspect source, scripts, permissions, and methodology before accepting any package.
