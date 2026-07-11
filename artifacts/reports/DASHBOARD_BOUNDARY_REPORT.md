# Dashboard Boundary Report

Generated: 2026-07-10

Status: **BOUNDED S2 DASHBOARD COMPLETE — FULL CONSOLE REWRITE REJECTED FOR NOW**

## Evidence Used

- The local dashboard at `http://127.0.0.1:8765` serves read-only API/UI projections for
  overview, Research Lab, Automation, Market Monitor, Datasets, Strategies, Runs,
  Engines, Validation, Dictionary, Evidence Links, and Workspace status.
- The dashboard projects retained jobs, LAB-799, seed-cycle evidence, validation status,
  canonical candles/fills, primary source provenance, and dictionary/global-search
  concepts without exposing POST, approval, venue, order, paper/demo/live, or credential
  controls.
- `make required` passes with dashboard/API/UI contract tests.
- No candidate is validated, promotion-eligible, or positive enough to justify a richer
  comparison workflow.

## Decisions

| TODO | Decision | Evidence |
|---|---|---|
| T-014-10 console IA spike / Next.js+shadcn replacement | REJECTED for bounded S2 | The current local dashboard satisfies the read-only evidence surface; a rewrite adds dependency and design churn without a missing workflow. |
| T-014-11 entity-detail layout pattern | REJECTED for bounded S2 | Existing tables/artifact links expose current entities. No operator workflow requires separate detail pages before a validated candidate exists. |
| T-014-12 global search | DONE for bounded S2 | Dictionary view projects `DICTIONARY_CONCEPTS_V1` aliases, contexts, gaps, and FIBO provenance; `ConceptRegistry` uses SQLite FTS5. |
| T-014-13 comparisons UI | REJECTED for bounded S2 | Comparison evidence remains negative and is visible in Research Lab score dimensions plus validation/research reports. Rich comparisons reopen only when a candidate has positive evidence worth comparing. |
| T-014-14 approvals UI | DEFERRED-HG | Approval write paths remain human-gated and unauthorized. The dashboard must stay read-only. |

## Reopen Triggers

- A validated, promotion-eligible candidate exists.
- The operator needs repeated entity inspection that cannot be served by existing tables
  and artifact links.
- A new approved stage authorizes approval or paper-lane UI work.
- The current local dashboard cannot keep the page refreshable or accessible at target
  viewport sizes.
