# Stage-exit security review (delta) — 2026-07-21 (T-018-04)

Scope: everything added since the 2026-07-20 review — the D-108/D-109 campaign machinery,
the demo-lane money/position panels, the open-work and AI-cost projections, the divergence
report, and above all the first *real network callers with credentials* (T-011-05).

Reviewer: the implementing agent. **Self-review, honestly labeled** — it cannot satisfy
D-099's independent SECURITY review and does not constitute HG-3 evidence.

## Surface review

| Component | Surface | Assessment |
|---|---|---|
| `harness/real_provider.py` | **Outbound HTTPS with API keys** — the first new credentialed network path since the demo lane | Fixed https endpoints only (Anthropic/OpenAI); keys sent in headers, never logged or persisted; no shell, no eval; bounded retries; error bodies parsed, not echoed with secrets. |
| `scripts/run_real_ai_benchmark.py` | Reads `.env` | Selective loader extracts exactly `ANTHROPIC_API_KEY`/`OPENAI_API_KEY` (SUP-011), test-pinned; keys never printed; no other variable enters the process. |
| `scripts/run_demo_divergence_report.py` | Public GET to demo-venue klines | Read-only, fixed https host, no credential read. |
| `dashboard_api/ai_costs.py`, `open_work.py`, demo-lane additions | Read-only projections | No control exposed; no credential; costs aggregated from ledger rows the runs themselves wrote. |
| Kill-switch drill | Touch/unlink of `KILL_SWITCH` | Uses the documented stop mechanism; order-blocking is the fail-safe direction; artifact records the reversible sequence. |

## Findings

None new. The 2026-07-20 findings (driver path traversal — fixed; Makefile immutability —
applied) remain in force. The cost ledger and benchmark records were checked for secret
leakage: they carry token *counts* and prices, never key material.

## Residual risks

1. **Provider keys live in `.env`** — appropriate for a local research box; revisit custody
   (keychain/vault) before any hosted deployment.
2. **Benchmark pricing table is pinned by hand** — a provider price change makes *future*
   cost rows wrong until updated; historical rows stay correct because pricing is recorded
   per record. Re-verify on the T-001-06 registry sweep cadence.
3. Self-review limitation, as above.

## Conclusion

No new credentialed capability beyond the two benchmark endpoints; no order, venue, or
live-money surface changed. Independent review remains required before HG-3/S3.
