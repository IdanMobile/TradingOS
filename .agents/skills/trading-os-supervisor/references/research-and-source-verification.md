# Research and source verification

## Research trigger

Research when a claim is current, niche, disputed, implementation-specific, material to risk, or absent from the project evidence. Do not browse just to decorate a simple answer.

## Research loop

1. Turn the unknown into a precise question.
2. Search primary sources first.
3. Find the original documentation, paper, filing, release, or dataset.
4. Check date, scope, definitions, and methodology.
5. Seek an independent source or reproducible test for material claims.
6. Record conflicts and explain which source was preferred.
7. Convert the result into a decision, hypothesis, or explicit unknown.

## Source classes

### Primary

Exchange and broker APIs, official protocol documentation, official smart-contract code, company filings and investor relations, regulators, central banks, official economic data, academic papers, and direct project tests.

### Secondary

Reputable market-data providers, professional research, established financial journalism, and well-documented open-source projects.

### Discovery only

Social media, influencer posts, anonymous accounts, signal marketplaces, rankings, promotional articles, and search snippets.

## Current-market evidence

Record both the market-data timestamp and retrieval timestamp. Check:

- exchange and instrument;
- quote currency;
- candle close status;
- timezone;
- data resolution;
- missing or duplicated records;
- stale feed or delayed endpoint;
- adjustment and corporate-action treatment;
- whether the value was available at the decision time.

## Sentiment evidence

Do not average headlines as if they were independent signals. Check:

- source authority;
- duplicate or syndicated articles;
- article novelty;
- entity and asset relevance;
- event polarity versus price polarity;
- publication and market reaction time;
- bot or coordinated-campaign indicators;
- decay of old sentiment;
- disagreement between sources.

## Evidence record

Use `templates/evidence-record.md` for material findings. Never store secrets, private keys, or credentials in research notes.
