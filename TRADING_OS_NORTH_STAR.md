# Trading Intelligence OS — North Star, Product Information Architecture & Capability Map

**Document status:** Approved planning baseline v1  
**Date:** 2026-07-05  
**Implementation architecture:** Not yet approved  
**MVP market sequence:** Crypto Spot → Crypto Perpetual Futures → US Stocks/ETFs  
**First executable vertical slice:** Crypto Spot, BTC/USDT + ETH/USDT, research-to-paper pipeline

---

# 1. Executive Summary

This project is not a collection of trading bots and not merely a trading dashboard.

It is a **self-measuring Trading Intelligence OS** that discovers, tests, rejects, validates, approves, operates, monitors, learns from, and retires trading strategies while also learning which tools, engines, datasets, models, agents, prompts, research methods, and reusable knowledge assets perform best under which conditions.

The platform must be able to:

- discover where opportunities may exist;
- collect and normalize existing knowledge from the internet and primary sources;
- reuse mature open-source tools, frameworks, APIs, strategies, backtesting engines, research systems, and prior art before building custom equivalents;
- turn raw ideas into explicit hypotheses;
- create and version strategies;
- backtest and stress-test them realistically;
- detect leakage, overfitting, regime dependence, cost sensitivity, and execution fragility;
- promote strategies only through explicit evidence gates;
- approve strategies separately by market, instrument, timeframe, configuration, and environment;
- forward-test through paper/demo and shadow modes;
- allow limited real-money deployment only after approval;
- keep live risk authority independent from strategy logic;
- store every experiment, including failures and rejected ideas;
- maintain a sourced dictionary and ontology of trading, investing, markets, order types, metrics, abbreviations, and concepts;
- evaluate AI models and agents as measurable components rather than static preferences;
- convert strong one-time research into reusable Research Assets across the OS;
- continuously improve routing, tools, strategies, workflows, and knowledge based on evidence.

---

# 2. North Star

> **Build a self-measuring Trading Intelligence OS that learns which strategies, markets, tools, engines, datasets, models, agents, prompts, workflows, and research assets work best under which conditions—and safely converts only validated evidence into capital deployment.**

The system must optimize for **evidence-backed, risk-adjusted profitability**, not activity, trade frequency, headline backtest returns, or AI novelty.

---

# 3. Core Product Thesis

The core problem is not:

> How do we make a bot trade?

The real problem is:

> How do we distinguish a real, executable, durable edge from historical coincidence, bad data, leakage, selection bias, unrealistic fills, fees, slippage, regime dependence, and overfitting—and then safely deploy only what survives?

Therefore, the product should be framed as:

> **A machine for discovering, rejecting, validating, approving, monitoring, degrading, and retiring trading edges.**

---

# 4. Hard Project Principles

## 4.1 Reuse Before Build

Assume prior art exists until research proves otherwise.

Before custom-building any meaningful capability, search for:

- production-ready platforms;
- open-source applications;
- libraries;
- SDKs;
- APIs;
- trading engines;
- backtesting systems;
- optimization frameworks;
- broker/exchange adapters;
- research frameworks;
- strategy repositories;
- indicator libraries;
- academic methods;
- public implementations;
- existing bots;
- data sources;
- dashboards;
- observability tools;
- workflow engines;
- experiment trackers;
- AI evaluation frameworks;
- reference architectures;
- case studies;
- known failures.

A custom build is allowed only when reuse, reuse+adapter, or hybrid options are insufficient for a documented reason.

## 4.2 Evidence Before Capital

No strategy reaches real money because it looks promising.

Promotion requires evidence.

## 4.3 Strategy Logic Does Not Own Risk Authority

A strategy may propose or generate actions.

An independent risk and approval path determines whether the action is permitted and at what capital level.

## 4.4 Preserve Failures

Rejected strategies, failed experiments, invalid hypotheses, bad models, and negative results are valuable knowledge and must remain queryable.

## 4.5 One Score Is Not Enough

The system must not collapse complex evidence into a single magic number.

Separate scores and hard gates are required.

## 4.6 Market-Specific Approval

Approval is contextual.

At minimum, approval identity should be able to distinguish:

- strategy;
- market;
- instrument/pair;
- timeframe;
- configuration/version;
- environment;
- risk tier.

## 4.7 Deterministic and Non-Deterministic Work Are Different

Deterministic automation should not be evaluated like AI work.

AI models and agents must be versioned, benchmarked, attributed, and scored separately.

## 4.8 Research Once, Reuse Broadly

Strong one-time research should become a reusable Research Asset rather than being repeatedly regenerated.

## 4.9 Dashboard as Operating System

Anything important in the project must have a visible, inspectable, understandable home in the dashboard.

---

# 5. Market Sequence

## Approved sequence

### Phase 1 — Crypto Spot

Initial focus:

- BTC/USDT
- ETH/USDT

Goals:

- prove research-to-paper pipeline;
- validate experiment lineage;
- validate backtesting and anti-overfitting gates;
- validate strategy-specific and market-specific approvals;
- validate data and execution assumptions;
- validate AI/model/agent measurement;
- validate dashboard operating model.

### Phase 2 — Crypto Perpetual Futures

Add:

- long + short;
- leverage;
- funding;
- liquidation-aware validation;
- derivatives-specific risk controls;
- venue-specific execution semantics.

### Phase 3 — US Stocks + ETFs

Goal:

- prove that the platform generalizes beyond crypto;
- handle market hours, corporate actions, different data models, and broker execution semantics.

### Phase 4+ — Other Markets

Only after evidence:

- futures;
- forex;
- options;
- commodities;
- other venues.

---

# 6. MVP Strategy Scope

The MVP should support separate strategy families with primary emphasis on:

1. frequent short-duration opportunities;
2. intraday/day-trading strategies;
3. multiple strategy families evaluated independently.

Longer-term investment strategies remain part of the OS model but are not the first execution priority.

The system must never treat scalping, intraday, swing, and long-term strategies as one homogeneous category.

---

# 7. Promotion & Capital Ladder

```text
RAW IDEA
   ↓
FORMAL HYPOTHESIS
   ↓
SANITY TEST
   ↓
HISTORICAL BACKTEST
   ↓
LEAKAGE / BIAS TEST
   ↓
COST + SLIPPAGE STRESS
   ↓
TEMPORAL OUT-OF-SAMPLE
   ↓
PARAMETER ROBUSTNESS
   ↓
REGIME VALIDATION
   ↓
PAPER / DEMO TRADING
   ↓
SHADOW EVALUATION
   ↓
HUMAN / POLICY APPROVAL
   ↓
LIMITED LIVE CAPITAL
   ↓
SCALED LIVE
   ↓
CONTINUOUS MONITORING
   ↓
DEGRADE / PAUSE / RETIRE
```

Real money is permitted only for approved strategies in approved markets/contexts.

---

# 8. Domain-Specific Strategy Validation

A generic product score is insufficient.

Each strategy should be evaluated using specialized dimensions such as:

- net expectancy after fees;
- slippage sensitivity;
- spread sensitivity;
- out-of-sample performance;
- walk-forward robustness;
- max drawdown;
- tail risk;
- parameter sensitivity;
- regime stability;
- turnover;
- liquidity/capacity;
- execution feasibility;
- paper-vs-backtest consistency;
- live-vs-paper consistency;
- multiple-testing / overfitting risk;
- leakage risk;
- concentration;
- correlation with other strategies.

## Recommended score families

1. Economic Edge Score
2. Out-of-Sample Score
3. Overfitting Risk Score
4. Cost & Execution Robustness Score
5. Drawdown & Tail-Risk Score
6. Regime Stability Score
7. Parameter Stability Score
8. Liquidity & Capacity Score
9. Paper-vs-Sim Consistency Score
10. Live-vs-Paper Consistency Score

**Rule:** approval is based on hard gates plus evidence, not a weighted-average score alone.

---

# 9. Product Information Architecture

## 9.1 Overview

### 01. Overview / Command Center

Purpose:

- global system state;
- research activity;
- test activity;
- paper/live status;
- approvals;
- risk;
- P&L;
- alerts;
- data health;
- AI spend;
- current bottlenecks.

---

## 9.2 Discover

### 02. Markets

- Crypto Spot
- Crypto Perpetuals
- Stocks
- ETFs
- Future markets

Per market/instrument:

- price state;
- trend;
- volatility;
- liquidity;
- spread;
- volume;
- order-book state;
- regime;
- anomalies;
- compatible strategies;
- experiments;
- approvals.

### 03. Opportunities

Purpose:

- rank where research attention may be valuable;
- surface candidate opportunities;
- never present a candidate as guaranteed profit.

Candidate categories may include:

- momentum;
- breakout;
- mean reversion;
- volatility expansion/compression;
- order-book imbalance;
- unusual volume;
- statistical divergence;
- pair relationships;
- cross-venue differences;
- funding anomalies;
- event-driven anomalies.

### 04. Ideas & Hypotheses

Separate raw ideas from executable strategies.

Each hypothesis stores:

- statement;
- origin;
- source(s);
- creator (human/agent/model);
- prior evidence;
- contradictions;
- target market;
- status;
- confidence;
- linked experiments;
- derived strategies.

---

## 9.3 Learn & Knowledge

### 05. Dictionary & Concepts

A first-class Trading & Markets Dictionary / Encyclopedia.

It must cover:

- abbreviations;
- trade management;
- order types;
- market structure;
- performance metrics;
- risk;
- chart/candle terms;
- technical analysis;
- strategy families;
- backtesting terms;
- quant/statistics;
- crypto;
- equities;
- ETFs;
- futures;
- options;
- macro/investment concepts.

Examples:

- TP
- TP1 / TP2 / TP3
- SL
- TSL
- BE / B-E
- R:R
- Long / Short
- Bid / Ask
- Spread
- Maker / Taker
- Market Order
- Limit Order
- Stop Order
- Stop-Limit
- OCO
- Bracket Order
- IOC / FOK / GTC
- P&L
- Drawdown
- Sharpe / Sortino / Calmar
- Funding Rate
- Open Interest
- Mark Price
- Liquidation
- OHLCV
- RSI / MACD / ATR / VWAP
- OOS
- Walk Forward
- Lookahead Bias
- Survivorship Bias
- Overfitting
- Slippage
- Monte Carlo
- Cointegration
- Alpha / Beta
- ETF / Index / Bond / Future / Option

#### Dictionary requirements

Each concept should support:

- canonical name;
- stable internal ID;
- abbreviation(s);
- alias(es);
- definition;
- category;
- related concepts;
- market contexts;
- venue/platform-specific variants;
- source provenance;
- examples;
- implementation references;
- internal usage;
- linked strategies;
- linked tests;
- evidence status;
- freshness status.

#### Important distinction

**Dictionary meaning ≠ strategy configuration.**

Example:

- Dictionary: TP1 means first take-profit target.
- Strategy: TP1 = +2%, close 25%.

### 06. Knowledge Base

Curated knowledge organized by domain:

- trading strategies;
- indicators;
- price action;
- chart patterns;
- market microstructure;
- risk management;
- portfolio theory;
- execution;
- backtesting;
- validation;
- statistics;
- ML;
- RL;
- market regimes;
- crypto;
- equities;
- academic papers;
- books;
- case studies;
- failed approaches;
- internal learnings.

### 07. Ecosystem Library

A registry of external prior art:

- strategies;
- algorithms;
- indicators;
- patterns;
- trading logic;
- risk methods;
- portfolio methods;
- backtesting methods;
- validation methods;
- research methods;
- statistical tests;
- ML/RL/LLM approaches;
- screeners;
- scanners;
- data sources;
- APIs;
- brokers;
- exchanges;
- engines;
- frameworks;
- libraries;
- GitHub projects;
- academic papers;
- books;
- communities;
- case studies;
- known failures.

Maturity path:

```text
DISCOVERED
    ↓
REVIEWED
    ↓
REPRODUCED
    ↓
INTERNALLY TESTED
    ↓
VALIDATED
    ↓
REUSED
```

### 08. Research Assets

Reusable, durable research outputs.

Each Research Asset stores:

- title;
- research question;
- creator;
- agent;
- model;
- prompt;
- tools;
- sources;
- date;
- cost;
- quality score;
- human-review status;
- dependencies;
- consumers across the OS;
- freshness;
- contradictions;
- supersession history.

Freshness states:

- CURRENT
- AGING
- STALE
- CONTRADICTED
- SUPERSEDED

### 09. Sources & Intelligence

Source categories:

- academic papers;
- official documentation;
- regulatory sources;
- GitHub;
- books;
- strategy communities;
- blogs;
- video;
- Reddit;
- social;
- news;
- exchange research;
- broker research;
- internal sources.

Each source stores:

- provenance;
- reliability;
- date;
- claims;
- extracted concepts;
- extracted hypotheses;
- contradictions;
- linked tests;
- current status.

---

## 9.4 Build & Research

### 10. Strategy Library

Central strategy registry.

Status filters:

- Candidate
- Testing
- Validated
- Paper
- Limited Live
- Live
- Degraded
- Rejected
- Retired

Each strategy should expose tabs such as:

- Overview
- Logic
- Versions
- Markets
- Parameters
- Backtests
- Validation
- Paper
- Live
- Trades
- Risk
- Evidence
- Sources
- Memory
- Changes

### 11. Research Lab

Supports:

- campaigns;
- research jobs;
- reproductions;
- strategy mining;
- literature review;
- tool scouting;
- market studies;
- model studies;
- regime studies;
- failed hypothesis investigation.

### 12. Experiments

Immutable experiment ledger.

Each experiment should store:

- hypothesis;
- strategy version;
- dataset version;
- engine;
- code version;
- parameter space;
- all trials;
- costs assumed;
- environment;
- AI provenance;
- results;
- artifacts;
- decision;
- rejection reason;
- downstream lineage.

---

## 9.5 Test & Validate

### 13. Backtesting Lab

Modes:

- single test;
- batch test;
- parameter sweep;
- cross-asset;
- cross-timeframe;
- regime test;
- cost stress;
- slippage stress;
- Monte Carlo;
- walk-forward;
- replay;
- engine comparison.

### 14. Validation Lab

Potential gates:

- sanity;
- lookahead/leakage;
- cost model;
- slippage;
- temporal OOS;
- walk-forward;
- parameter stability;
- regime stability;
- drawdown;
- tail risk;
- liquidity/capacity;
- multiple-testing / overfit risk;
- execution realism.

### 15. Comparisons

Compare:

- strategies;
- models;
- agents;
- prompts;
- tools;
- engines;
- datasets;
- data sources;
- indicators;
- markets;
- timeframes;
- execution assumptions;
- research methods.

---

## 9.6 Trade

### 16. Paper Trading

Track:

- bot state;
- simulated capital;
- fills;
- P&L;
- divergence from backtest;
- signal frequency differences;
- slippage differences;
- failure behavior.

### 17. Bots

Fleet view:

- Research Bots
- Paper Bots
- Shadow Bots
- Limited Live
- Live
- Paused
- Failed

Each bot records:

- strategy;
- environment;
- market;
- state;
- uptime;
- signals;
- trades;
- P&L;
- risk;
- engine;
- last decision;
- alerts.

### 18. Live Trading

Visually and permission-wise separate from paper.

Must show:

- real capital;
- allocated capital;
- at-risk capital;
- approved strategies;
- active orders;
- live P&L;
- kill-switch state;
- risk events;
- execution health.

### 19. Portfolio

Track:

- market exposure;
- instrument exposure;
- strategy allocation;
- hidden correlations;
- common factor exposure;
- concentration;
- combined drawdowns;
- reserve capital.

---

## 9.7 Govern

### 20. Risk Center

Independent from strategy logic.

Potential controls:

- max capital usage;
- max daily loss;
- max strategy drawdown;
- max correlated exposure;
- max instrument exposure;
- max leverage;
- max order size;
- stale-data blocks;
- exchange-health blocks;
- emergency kill switch;
- per-strategy risk budget.

### 21. Approvals

Approval identity should support:

```text
Strategy × Market × Instrument × Timeframe × Config × Environment × Risk Tier
```

Possible decisions:

- REJECTED
- WATCH
- APPROVED FOR PAPER
- APPROVED FOR SHADOW
- REVIEW FOR LIMITED LIVE
- APPROVED LIMITED LIVE
- APPROVED LIVE
- DEGRADED
- PAUSED
- RETIRED

Each approval package should include:

- evidence;
- failed gates;
- warnings;
- human decision;
- history;
- expiry/review rules.

---

## 9.8 Infrastructure

### 22. Data Center

Sources:

- exchange APIs;
- historical bars;
- trades;
- quotes;
- L1/L2/L3 order books;
- funding;
- open interest;
- news;
- filings;
- fundamentals;
- alternative data.

Dataset functions:

- versioning;
- provenance;
- quality checks;
- gap detection;
- duplicate detection;
- timestamp validation;
- freshness;
- coverage;
- schema;
- licensing constraints.

### 23. Tools & Engines

Registry categories:

- trading engines;
- backtesting engines;
- optimization systems;
- indicator libraries;
- ML frameworks;
- data libraries;
- exchange connectors;
- broker connectors;
- research tools;
- visualization;
- statistics;
- risk libraries;
- scrapers/intelligence;
- observability;
- workflow tools.

Each tool stores:

- category;
- version;
- status;
- use cases;
- official docs;
- repository;
- license;
- maintenance;
- internal tests;
- integrations;
- known limitations;
- security notes;
- current decision;
- replacement options.

---

## 9.9 AI Intelligence

### 24. AI Command Center

Global view of:

- active agents;
- model usage;
- current spend;
- task routing;
- benchmark drift;
- failures;
- top-performing configurations;
- stale benchmarks;
- reusable research output.

### 25. Model Registry

Track exact models, not brand families only.

Each model stores:

- provider;
- exact model ID;
- version/snapshot;
- first seen;
- status;
- capability evidence;
- task-specific performance;
- latency;
- cost;
- tool-call performance;
- structured-output validity;
- failure rate;
- benchmark count;
- last evaluation.

### 26. Agent Registry

An agent is distinct from a model.

Agent configuration includes:

- role;
- model;
- prompt version;
- tools;
- context package;
- reasoning settings;
- budget;
- workflow;
- output schema;
- critic/reviewer passes.

### 27. Benchmark Lab

Two benchmark modes are required.

#### Controlled Benchmark

Freeze:

- prompt;
- dataset;
- source corpus;
- tools;
- budget;
- timeout;
- output schema.

Purpose:

- isolate model effect.

#### Natural Best-Configuration Benchmark

Allow:

- model-specific prompts;
- different tool usage;
- reasoning settings;
- optimized agent workflows.

Purpose:

- determine which complete system performs best in practice.

### 28. Task Router

Route tasks based on internal evidence:

- task class;
- required quality;
- cost limit;
- latency limit;
- privacy;
- tool needs;
- historical benchmark results;
- reliability;
- current model status.

### 29. Prompt Library

Version prompts and connect them to:

- agents;
- benchmark results;
- models;
- tasks;
- changes;
- downstream outcomes.

### 30. AI Experiments

Experiment dimensions may include:

- model;
- agent;
- prompt;
- toolset;
- source corpus;
- context package;
- budget;
- retry strategy;
- critic pass;
- multi-agent workflow.

### 31. Cost Intelligence

Track:

- cost per task;
- cost per useful result;
- cost per validated hypothesis;
- cost per surviving strategy;
- cost per paper candidate;
- cost per live-approved candidate;
- reusable asset amortization;
- model-provider spend;
- agent spend.

### 32. AI Learnings

Examples:

- best model for deep one-time research;
- best cheap model for bulk classification;
- best agent for contradiction discovery;
- best model for source extraction;
- models whose ideas frequently fail OOS;
- model updates that degrade quality;
- tools that improve results more than model upgrades.

---

## 9.10 Memory

### 33. Memory & Learning

Memory categories:

- trading learnings;
- strategy learnings;
- market learnings;
- regime learnings;
- research learnings;
- tool learnings;
- model learnings;
- agent learnings;
- data learnings;
- execution learnings;
- failure memory;
- operational learnings.

Memory must be evidence-linked.

Example:

```text
Finding:
BTC 15m Bollinger mean-reversion variants repeatedly lost edge
under 1.5× fee stress during high-volatility regimes.

Evidence:
EXP-381, EXP-402, EXP-419, EXP-601

Contradiction:
EXP-712

Confidence:
HIGH
```

---

## 9.11 System

### 34. Reports

- research reports;
- strategy reports;
- validation packages;
- paper/live reports;
- risk reports;
- AI/model reports;
- cost reports;
- portfolio reports;
- incident reports.

### 35. Operations

- jobs;
- queues;
- schedules;
- failures;
- retries;
- data freshness;
- adapter health;
- exchange/broker status;
- model-provider status;
- observability;
- incidents.

### 36. Settings

- environments;
- permissions;
- providers;
- API integrations;
- budgets;
- risk policies;
- approval policies;
- notification rules;
- retention;
- feature flags.

---

# 10. AI Model & Agent Scoring System

## 10.1 Hard Rule

Do not assign one global score to a model.

Score a **versioned model + agent configuration against a specific task class and downstream outcome**.

## 10.2 Separate Scores

### A. Task Quality Score

- accuracy;
- relevance;
- completeness;
- instruction adherence;
- reproducibility;
- structured-output validity.

### B. Research Quality Score

- evidence strength;
- primary-source ratio;
- citation correctness;
- claim support;
- contradiction discovery;
- novelty;
- hypothesis usefulness;
- duplicate rate.

### C. Downstream Value Score

Measure the funnel:

```text
Research outputs
   ↓
Hypotheses formalized
   ↓
Strategies tested
   ↓
Strategies surviving validation
   ↓
Paper candidates
   ↓
Live-approved candidates
   ↓
Actual economic contribution
```

### D. Cost Efficiency Score

- useful output / $;
- validated hypothesis / $;
- surviving strategy / $;
- research asset reuse / $.

### E. Operational Score

- latency;
- timeout rate;
- tool failure;
- malformed output;
- retry count;
- token use;
- context sensitivity.

### F. Stability Score

Measure variance across repeated equivalent runs.

### G. Economic Contribution Score

Measure whether the AI configuration created incremental value sufficient to justify cost.

---

# 11. AI Involvement Classification

Every strategy should classify AI involvement:

- **A. No AI involvement**
- **B. AI used only for historical research/provenance; runtime deterministic**
- **C. AI used during strategy development; runtime deterministic**
- **D. AI used periodically, e.g. daily regime classification**
- **E. AI in live decision path**
- **F. Multi-agent live decision path**

This affects:

- runtime cost;
- latency;
- provider dependency;
- availability risk;
- reproducibility;
- model-change risk;
- approval requirements.

---

# 12. AI Provenance Graph

The OS must preserve lineage such as:

```text
Model
  ↓
Agent Configuration
  ↓
Research Asset
  ↓
Hypothesis
  ↓
Strategy
  ↓
Backtests
  ↓
Validation
  ↓
Paper
  ↓
Live
```

This enables queries such as:

- Which model generated the most hypotheses that survived OOS?
- Which agent creates the cheapest validated strategy candidates?
- Which model generates attractive ideas that later fail?
- Which research assets are reused most?
- Which strategies were influenced by a specific model version?
- Did a provider model update improve or degrade outcomes?

---

# 13. Core Capability Map

| Capability | Purpose | MVP Priority | Current Direction |
|---|---|---:|---|
| Dashboard / OS shell | Main operating environment | Must | Custom product layer |
| Market registry | Organize markets/instruments | Must | Custom domain layer |
| Opportunity discovery | Rank research candidates | Must | Hybrid |
| Hypothesis registry | Separate ideas from strategies | Must | Custom domain layer |
| Dictionary / ontology | Shared vocabulary | Must | Seed from authoritative sources + custom normalization |
| Knowledge base | Curated reusable knowledge | Must | Custom integration layer |
| Ecosystem library | Prior-art registry | Must | Custom registry + automated discovery |
| Research assets | Reuse one-time research | Must | Custom |
| Strategy registry | Versioned strategy lifecycle | Must | Custom domain layer |
| Research lab | Campaigns and investigations | Must | Hybrid |
| Experiment ledger | Reproducibility and lineage | Must | Custom domain layer |
| Backtesting | Historical simulation | Must | Reuse existing engines first |
| Validation | Falsification and robustness | Must | Hybrid; custom governance |
| Comparisons | Cross-entity comparison | Must | Custom UI/data layer |
| Paper/demo trading | Forward test | Must | Reuse engine/broker capabilities |
| Bot fleet | Manage running bots | Must | Hybrid |
| Live trading | Real execution | Later in MVP | Reuse adapters/engines + custom governance |
| Portfolio | Combined exposure | Soon | Hybrid |
| Risk center | Independent risk authority | Must | Hybrid |
| Approvals | Promotion/demotion | Must | Custom |
| Data center | Datasets, quality, lineage | Must | Hybrid |
| Tools registry | Evaluate ecosystem tools | Must | Custom registry |
| Model registry | Track model versions | Must | Custom |
| Agent registry | Track agent configurations | Must | Custom |
| Benchmark lab | Compare models/agents | Must | Hybrid |
| Task router | Evidence-based AI routing | Soon | Custom policy + provider abstractions |
| Prompt library | Version prompts | Must | Custom registry |
| AI cost intelligence | Cost/value optimization | Must | Custom aggregation |
| Memory | Evidence-linked learnings | Must | Custom domain layer |
| Reports | Human-readable evidence | Must | Custom |
| Operations | Jobs, queues, failures | Must | Reuse infrastructure where possible |

---

# 14. Existing Capability Reuse Candidates — Current Planning Status

These are **candidates**, not automatic final selections.

| Area | Candidate / Prior Art | Current Status |
|---|---|---|
| Crypto strategy research/backtesting | Freqtrade | Validated candidate |
| Crypto bot/fleet/market-making workflows | Hummingbot | Validated candidate |
| Event-driven multi-asset engine | NautilusTrader | Validated candidate |
| Broad multi-asset research/backtest/live | LEAN / QuantConnect | Validated candidate |
| High-throughput research sweeps | vectorbt | Tentative candidate |
| Crypto exchange abstraction | CCXT | Validated candidate for fit testing |
| Exchange-native connectivity | Native exchange APIs | Required comparison/fallback |
| Broker API path | Alpaca | Tentative; jurisdiction/fit required |
| Broad brokerage | Interactive Brokers | Tentative; exact integration validation required |
| Regulatory fundamentals | SEC primary datasets/filings | Validated source candidate |
| Optimization | Existing frameworks such as Optuna-class tooling | Research/reuse candidate |
| AI evals | Existing eval frameworks and provider tooling | Reuse-first required |

No final engine, broker, exchange, or data vendor is approved yet.

---

# 15. Custom Build Justification — Current Approved Candidates

The following areas are currently justified as likely custom domain layers because they encode the project’s specific North Star rather than generic trading plumbing:

## 15.1 Strategy Evidence Registry

Tracks evidence and lifecycle across engines and environments.

## 15.2 Experiment Ledger

Tracks all trials, failures, parameters, datasets, code, AI provenance, and decisions.

## 15.3 Approval Engine

Supports contextual promotion/demotion by strategy × market × instrument × timeframe × config × environment × risk tier.

## 15.4 Evidence-Linked Memory

Stores learnings with evidence and contradictions.

## 15.5 Research Asset Registry

Amortizes high-value research across the OS.

## 15.6 AI Model/Agent Evaluation Layer

Connects model and agent configurations to task-specific and downstream economic outcomes.

## 15.7 Ecosystem Library

Normalizes, evaluates, and tracks prior art from the internet and existing tools.

## 15.8 Dictionary / Trading Ontology

Creates a canonical cross-market vocabulary while preserving source- and venue-specific semantics.

---

# 16. First Executable Vertical Slice

The first vertical slice should prove the full lifecycle, not broad feature coverage.

## Scope

### Market

Crypto Spot

### Instruments

- BTC/USDT
- ETH/USDT

### Environments

- Historical research
- Backtest
- Validation
- Paper/demo
- No live capital initially

### Strategy families

Start with a small, diverse set of reusable or reproducible prior-art families, for example:

- momentum;
- mean reversion;
- breakout/volatility expansion.

Exact strategy implementations must be selected only after reuse research and evidence review.

### Required OS pages for vertical slice

1. Overview
2. Markets
3. Ideas & Hypotheses
4. Dictionary & Concepts
5. Ecosystem Library
6. Research Assets
7. Strategy Library
8. Research Lab
9. Experiments
10. Backtesting Lab
11. Validation Lab
12. Comparisons
13. Paper Trading
14. Risk Center
15. Approvals
16. Data Center
17. Tools & Engines
18. Model Registry
19. Agent Registry
20. Benchmark Lab
21. Memory & Learning
22. Operations

These may begin as thin but real pages.

### First vertical-slice proof

A successful vertical slice should demonstrate:

```text
Existing online strategy / method discovered
        ↓
Source added to Ecosystem Library
        ↓
Concepts linked to Dictionary
        ↓
Research Asset created
        ↓
Hypothesis formalized
        ↓
Strategy version created
        ↓
Experiment lineage recorded
        ↓
Backtest executed
        ↓
Validation gates executed
        ↓
Strategy rejected OR promoted
        ↓
Paper bot launched if approved
        ↓
Backtest-vs-paper divergence tracked
        ↓
Learnings written to evidence-linked memory
        ↓
Dashboard shows complete lineage
```

The system should treat a well-justified rejection as a successful outcome.

---

# 17. What Not To Do

- Do not promise daily profit.
- Do not create one universal bot.
- Do not create one universal score.
- Do not use “last 3 years” as a universal validation rule.
- Do not promote based on maximum profit.
- Do not auto-deploy AI-generated strategies.
- Do not hide failed experiments.
- Do not let strategy code override global risk.
- Do not assume paper trading proves live profitability.
- Do not let unrestricted LLM output directly control live capital.
- Do not treat win rate as edge.
- Do not build a complete custom backtesting or execution stack before validating reuse options.
- Do not treat public strategy claims as evidence.
- Do not repeatedly pay AI models to rediscover reusable knowledge.
- Do not rank models globally without task context.

---

# 18. Major Risks

## 18.1 Backtest Overfitting

Mitigation:

- full experiment ledger;
- OOS;
- walk-forward;
- multiple-testing-aware review;
- parameter stability;
- regime analysis.

## 18.2 Costs Destroy Frequent Strategies

Mitigation:

- realistic fee/spread/slippage models;
- stress tests;
- paper-vs-sim reconciliation.

## 18.3 Data Leakage

Mitigation:

- leakage tests;
- point-in-time data;
- strict temporal pipelines.

## 18.4 AI Hallucination / Pattern Manufacturing

Mitigation:

- source-backed research;
- reproducible artifacts;
- deterministic validation;
- baseline comparisons;
- model/agent scoring.

## 18.5 Paper/Live Divergence

Mitigation:

- shadow mode;
- limited live capital;
- divergence tracking;
- execution telemetry.

## 18.6 Regime Dependence

Mitigation:

- regime stratification;
- degradation monitoring;
- contextual approvals.

## 18.7 API / Provider Drift

Mitigation:

- adapter version tracking;
- contract tests;
- changelog monitoring;
- re-verification gates.

## 18.8 Hidden Correlation Across Bots

Mitigation:

- portfolio-level exposure analysis;
- factor/correlation checks;
- independent portfolio risk limits.

## 18.9 AI Cost Waste

Mitigation:

- Research Assets;
- task routing;
- benchmark-driven model selection;
- cost per useful downstream outcome.

---

# 19. Decision Status

## Approved

- Trading Intelligence OS framing
- Reuse-before-build hard rule
- Crypto Spot → Perpetual Futures → US Stocks/ETFs sequence
- BTC/USDT + ETH/USDT initial vertical slice
- Separate strategy families
- Separate market/context approvals
- Evidence-gated capital promotion
- Dashboard as main operating environment
- Dictionary & Concepts as foundational layer
- Ecosystem Library
- Research Assets
- Experiment Ledger
- Strategy Evidence Registry
- AI Model & Agent Intelligence Layer
- Separate strategy/model/agent/research/economic scores
- AI provenance graph
- Evidence-linked memory
- Independent risk authority

## Not Yet Approved

- Final implementation architecture
- Final database architecture
- Final frontend stack
- Final trading engine
- Final backtesting engine
- Final exchange
- Final broker
- Final data vendor
- Final AI provider mix
- Final orchestration framework
- Final deployment topology

These require explicit reuse research, executable bake-offs, and evidence.

---

# 20. Immediate Next Decision Gate

Before implementation architecture is locked, complete a **Reuse & Engine Bake-Off Blueprint** for the first Crypto Spot vertical slice.

The blueprint should compare at minimum:

- Freqtrade
- Hummingbot
- NautilusTrader
- LEAN / QuantConnect
- vectorbt where relevant
- CCXT
- native exchange APIs
- candidate experiment/eval/observability infrastructure

For each capability, determine:

- reuse;
- reuse + adapter;
- hybrid;
- custom;
- defer.

The output must map each selected capability into the Trading Intelligence OS boundaries and provide exact implementation references before code begins.

---

# 21. Single Next Action

**Create the Reuse & Engine Bake-Off Blueprint for the Crypto Spot vertical slice, with exact capability mapping and executable proof tests.**
