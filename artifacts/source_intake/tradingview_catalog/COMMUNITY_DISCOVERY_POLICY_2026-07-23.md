# TradingView Community Discovery Policy — Phase 0

Date: 2026-07-23
Status: enabled for bounded manual public-metadata discovery only
Intended OS use: `UNKNOWN_PENDING_OPERATOR_CONFIRMATION`
Execution authority: `NONE`

## Allowed discovery

- Official public TradingView documentation pages may be observed manually without authentication.
- An operator may supply a public community-script URL for metadata review.
- A manual review batch is limited to 25 operator-supplied public URLs and must retain source URL,
  observation time, author/title metadata, visible access class, license-review state, and a
  content-free duplicate key.
- Discovery is metadata-only. Source code, performance tables, descriptions, charts, comments,
  followers, account details, popularity metrics, and market data are not collected in Phase 0.

## API, pagination, and rate boundaries

- Approved automated API: `NONE`.
- Automated page or pagination budget: `0`.
- Automated request rate: `0`.
- Browser automation, undocumented endpoints, session replay, cookies, credentials, access-control
  bypasses, and bulk scraping are prohibited.
- A future collector requires a separately documented, officially supported collection method plus
  legal/product approval, fixed allowlisted origins, bounded pagination, explicit request rate,
  deterministic snapshots, and a no-code/no-account safety review.

## Refresh cadence

- No scheduled or unattended refresh is authorized.
- Manual official-documentation recheck: at most once per calendar quarter, or earlier only when a
  retained official source announces a material change.
- Each changed observation creates a new dated, content-addressed snapshot; historical snapshots
  are never overwritten.

## Completeness boundary

Community coverage is always `BEST_EFFORT_PUBLIC_METADATA_ONLY`. No snapshot may claim all
community scripts, all current scripts, all profitable scripts, or a representative sample.
Popularity, ranking, editor selection, recency, and reported performance are not selection or edge
evidence.

## Eligibility boundary

- Open-source visibility is only the start of review. Per-item license, attribution, intended-use,
  source-integrity, semantic, and containment checks remain required.
- Protected, invite-only, private, purchased, account-gated, unclear-license, or removed items
  remain metadata-only, `BLOCKED`, or `EXCLUDED`; they are never copied or behaviorally cloned.
- Catalog discovery cannot create a strategy version, research trial, validation result, approval,
  signal, paper/demo action, live action, venue connection, or execution authority.
