# TradingView Phase-0 Terms, License, and Source Boundary Evidence

Observed at: 2026-07-23T12:33:25Z
Status: metadata inventory only; legal/product review required
Intended OS use: `UNKNOWN_PENDING_OPERATOR_CONFIRMATION`
Execution authority: `NONE`

## Decision

The Phase-0 inventory may retain minimal public metadata and official URLs. It does not authorize
code capture, automated collection, strategy reproduction, redistribution, market-data use,
research trials, paper/demo activation, live trading, or order routing.

Until the operator states whether the OS is private, commercial, distributed, or paywalled, every
reuse or redistribution decision remains blocked on legal/product review. This note records
source-backed constraints; it is not legal advice.

## Official evidence

| Claim | Official source | Publication/update time | Observation and limitation |
|---|---|---|---|
| TradingView can change its Terms, services, features, and APIs. | [Terms of Use](https://www.tradingview.com/policies/) | Not stated | Retrieved 2026-07-23. A dated inventory cannot claim timeless completeness. |
| TradingView content and market data are display-only under the stated terms and may not feed automated trading, order generation, algorithmic decisions, risk controls, or other non-display machine processes. | [Terms of Use, sections 3 and 22](https://www.tradingview.com/policies/) | Not stated | Retrieved 2026-07-23. TIOS must compute from separately licensed, OS-owned point-in-time data; charts, alerts, webhooks, and displayed TradingView outputs are not bot inputs. |
| Open-source, protected, and invite-only are distinct visibility types. Protected and invite-only code is closed-source. | [Pine publication visibility](https://www.tradingview.com/pine-script-docs/writing/publishing/) | Not stated | Retrieved 2026-07-23. Protected, invite-only, private, purchased, or account-gated code is excluded from capture and behavioral cloning. |
| TradingView states that open-source scripts use MPL 2.0 by default unless the author specifies another license, and TradingView publishing/reuse rules still apply. | [Pine publication visibility and licensing](https://www.tradingview.com/pine-script-docs/writing/publishing/) and [Script publishing rules](https://www.tradingview.com/support/solutions/43000590599-script-publishing-rules/) | Not stated | Retrieved 2026-07-23. “Open-source” is not an automatic OS reuse clearance; the exact script, license header, author attribution, intended use, and applicable rules require per-item review. |
| The public Built-in Strategies folder currently exposes 20 named entries. | [Built-in Strategies](https://www.tradingview.com/support/folders/43000587406-built-in-strategies/) | Not stated | Retrieved 2026-07-23. This documentation index is not proof of the exact live UI inventory. |
| MovingAvg Cross and MovingAvg2Line Cross have official pages that describe strategy behavior, but their breadcrumb places them under Built-in Indicators. | [MovingAvg Cross](https://www.tradingview.com/support/solutions/43000599885-movingavg-cross/) and [MovingAvg2Line Cross](https://www.tradingview.com/support/solutions/43000599886-movingavg2line-cross/) | Not stated | Retrieved 2026-07-23. The conflict is retained as a classification/reconciliation gap, not silently resolved. |
| “All Chart Patterns” documents a 16-pattern subset, while the broader Patterns tab includes other tools. | [All Chart Patterns](https://www.tradingview.com/support/solutions/43000706927-all-chart-patterns/) and [Auto chart patterns](https://www.tradingview.com/support/solutions/43000690464-auto-chart-patterns-on-tradingview/) | Not stated | Retrieved 2026-07-23. The 16 names are a documented subset, not a complete Patterns-tab inventory. |
| TradingView widgets cannot accept custom Pine scripts or strategies. | [Widget FAQ](https://www.tradingview.com/widget-docs/faq/general/) | Not stated | Retrieved 2026-07-23. A dashboard widget is external visual context only; OS strategies must remain OS-owned research assets. |

## Allowed Phase-0 material

- Item name, item type, official public URL, observation time, public access class, and named gaps.
- Minimal metadata necessary to identify a public official page.
- Source URLs and concise, original summaries of the restrictions above.
- A deterministic digest of TIOS-authored metadata.

## Prohibited or blocked material

- TradingView market data, alerts, webhooks, chart exports, displayed values, or Strategy Report
  outputs as machine inputs to OS decisions.
- Credentials, cookies, authenticated/account content, private URLs, paid access, or bypasses.
- Protected, invite-only, private, purchased, or otherwise unavailable source code.
- Bulk capture of descriptions, code, metrics, accounts, rankings, or other site content.
- Copying official or community strategy code during Phase 0.
- Commercial redistribution, public distribution, or paywalled reuse before intended use and
  license obligations are confirmed.
- Any inference that a TradingView profitability claim proves a local edge.

## Required decision before further collection or reuse

The operator must record whether the intended OS use is private personal use, internal business
use, commercial service, distribution, paywalled access, or another defined category. Legal/product
review must then approve a named source method and reuse class before automated discovery, bulk
collection, code capture, redistribution, or commercial use is proposed.
