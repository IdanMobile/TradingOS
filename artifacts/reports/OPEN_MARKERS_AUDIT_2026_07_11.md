# Open markers audit — 2026-07-11

## Scope

Repo-wide sweep for `TODO`, `FIXME`, `TBD`, `PROVISIONAL`, `UNRESOLVED`,
`BLOCKED`, `DEFERRED`, `WARN`, `NOT_RUN`, `follow-up`, and related markers
outside the canonical `TODO.md` projection.

## Actionable non-human items found and handled

| Area | Finding | Disposition |
|---|---|---|
| Architecture docs | AD/MODULE_CATALOG still described Hummingbot and LEAN as deferred/blocked despite new retained bounded evidence. | Updated to bounded Hummingbot/LEAN evidence roles. |
| Engine reports | ENGINE_BAKEOFF_REPORT and PROTOTYPE_READINESS_REPORT still described Docker-blocked LEAN/Hummingbot follow-up. | Updated to bounded evidence plus explicit throughput/scope tracks. |
| Research Lab evidence cycle | Validation evidence changed after G10 method fixtures, so latest lab evidence was no longer refreshed. | Ran Research Lab v0 and retained `LAB-f99dcc214f377ecca4710bbb41d445c8331d2a1b06f93931ed1c88bdf3af5924`; no winner, no execution authority. |

## Remaining real blockers or deferred gates

| Marker | Why it remains | Gate |
|---|---|---|
| Hummingbot full-history B2/B3/B4 and determinism | Throughput track. Bounded 30-day matrix is complete and deterministic; cached full-history B2 F1/S1 still timed out after 3600 seconds, with timeout manifest and container cleanup. | Not strategy approval blocking in bounded S2. |
| Nautilus full-history parity and latency/fill exercise | Documented throughput/scope expansion beyond retained bounded event-simulation evidence. | Not strategy approval blocking while no candidate is positive. |
| G4 WARN | Freqtrade lookahead follow-up overrides requested stake/trade-limit settings. Retained as a validation warning. | Blocks clean promotion claims. |
| Production G10 `NOT_RUN` | Synthetic PBO/CSCV and DSR fixtures pass, but candidate-specific integration and independent recomputation are still required. | Blocks G10 PASS claims/promotion. |
| RG-05/RG-06 venue/account questions | RG-05 public-source slice is now refreshed; exact account/product/API eligibility and RG-06 fee tier remain human/account/S3-specific. | Deferred until S3/paper-lane preparation. |
| AI provider benchmark runs/cost telemetry | No provider credentials/spend authority configured. | Deferred credentials/human authority. |
| Approvals UI/paper/demo/live paths | Require S2 exit, HG-3, validated strategy, and explicit operator approval. | Human-gated and unauthorized now. |

## Recurring/non-actionable markers

- Program governance `ONGOING` items are recurring discipline, not unfinished build work.
- Historical `BLOCKED`/`DEFERRED` wording in old retained artifacts remains as point-in-time
  evidence unless superseded by newer reports.
- Domain enum values such as `OPEN`, `REJECTED`, `NOT_RUN`, and `WARN` are data states,
  not TODOs.

## Current conclusion

The canonical TODO projection is not the only source of markers, but the remaining
open markers are now either:

1. handled in this audit pass,
2. active Hummingbot full-history throughput/chunking work,
3. explicit human/credential/S3/HG gates, or
4. retained historical evidence.

No paper/demo/testnet/live trading path or credential path is enabled.
