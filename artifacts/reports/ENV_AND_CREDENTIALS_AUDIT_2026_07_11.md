# Environment and Credentials Audit — 2026-07-11

Scope: every environment variable, credential, endpoint, and config value referenced in
code, docs, specs, and the intake gate, classified for current and future workflows
(live data, paper/demo, backtesting, signals, AI benchmarks, storage, workspace TODO
API, observability). Supersedes nothing; extends
`PRE_CODE_ENVIRONMENT_INTAKE_REPORT.md` (2026-07-06) and
`AI_COST_TELEMETRY_CREDENTIAL_RECHECK_2026_07_11.md`.

## 1. Complete variable/config inventory

Sweep method: `grep` for `os.environ`/`getenv` across `src/`, `scripts/`, `tests/`,
`benchmarks/`; plus `.env.example`, Makefile, and spec/doc references.

| Variable / Config | Purpose | Used By | Required Now? | Required Later? | Optional? | Safe Default? | Add Later Allowed? | Blocking What? | Notes |
|---|---|---|---|---|---|---|---|---|---|
| `TIOS_AI_MODE` | AI execution mode selector (`mock`/`real`); anything else fails closed | `benchmarks/ai_agent/harness/provider.py`, `scripts/run_research_lab_v0.py` (rejects non-mock), jobs runner (forces `mock`) | No | Yes (real benchmark runs) | Yes | Yes — absent ⇒ `mock`, null provider, no network | Yes | Nothing now | **Was missing from `.env.example`; added 2026-07-11 (names/comments only).** |
| `TIOS_AI_PROVIDER` | Provider selector when `TIOS_AI_MODE=real` (`anthropic`/`openai`/`google`) | `benchmarks/ai_agent/harness/provider.py` | No | Yes (real runs) | Yes | Yes — unused in mock mode; `real` without it fails closed | Yes | T-011-05, T-017-05 | Added to `.env.example` 2026-07-11. |
| `ANTHROPIC_API_KEY` | Anthropic benchmark credential | AI harness (real mode only) | No | Yes (T-011-05 real runs) | Yes | Yes — absent ⇒ provider `not configured`, honest BLOCKED | Yes (operator intake choice 2026-07-06: "Add later") | T-011-05, T-017-05, EG-6 real slice | **Spend gate: do not configure until operator authorizes spend + cost telemetry wiring.** Rechecked 2026-07-11: absent. |
| `OPENAI_API_KEY` | OpenAI benchmark credential | same | No | Yes | Yes | Yes | Yes | same | same disposition. |
| `GOOGLE_API_KEY` | Google benchmark credential | same | No | Yes | Yes | Yes | Yes | same | same disposition; exact SDK var name re-verified at implementation time. |
| MLflow remote tracking vars | remote lineage | none | No | Only if local mode proves insufficient (AD §P reopen trigger) | — | Yes — fully local by operator choice 2026-07-06 | Yes | nothing | Intentionally absent from `.env.example`. |
| DVC remote credentials / S3 | remote artifact storage | none | No | Only at an approved storage gate | — | Yes — local DVC remote on separate volume | Yes | nothing | Backup set policy in AD §P covers current needs. |
| Exchange/venue API keys (live) | live trading | none — no code path exists | **NEVER in current phase** | S4 only, after HG-4/5 + 10 human-only items | — | — | Gate-controlled | live trading (deliberately) | **Prohibited: no withdrawal-enabled keys ever; no live keys before documented gates.** |
| Exchange testnet/demo keys (e.g. OKX demo, Binance Spot testnet) | paper/demo lane | none yet | No | Yes (S3, after S2 exit + HG-3 + paper-lane decision T-015-01) | — | Yes — absent | Yes | paper/demo activation (deliberately) | Must be visually/operationally separated from any live key; isolated state per AD §AA. |
| Market-data credentials | paid data tiers | none | No | Only per D-018 justification | Yes | Yes — Binance public data needs no credential | Yes | nothing | Frozen dataset re-downloadable without credential. |
| Workspace TODO API config | dashboard host/port | `make dashboard` → `tios.services.dashboard_ui.server` | No | No | — | Yes — loopback-only binding enforced in code (`is_loopback_host`), port 8765, no auth token by design (operator-only, local) | — | nothing | No env var exists or is needed; adding public-bind config is architecturally prohibited (AD §P/§AI operator-only loopback). |
| Observability credentials (Prometheus/Grafana/OTel) | monitoring stack | none | No | Only on AD §AC reopen triggers | — | Yes — rejected for bounded S2 | Yes | nothing | `OBSERVABILITY_BOUNDARY_REPORT.md`. |
| `CHECK_ARTIFACT`/`CHECK_ARTIFACT_TMP` | internal Makefile plumbing for `make check` artifact | Makefile only | — | — | — | Yes — set by make itself | — | — | Not operator config; excluded from `.env.example` deliberately. |

## 2. Changes made to `.env.example` this pass

Added (names/comments only, both commented out):

- `TIOS_AI_MODE` — documented default `mock`; `real` is gated.
- `TIOS_AI_PROVIDER` — documented allowed values and fail-closed behavior.

No variable was removed. Existing AI-provider and market-data sections were already
correct. No real value was added anywhere.

## 3. Missing credentials/config that block current work

**None.** Every currently authorized workflow (offline research lab, backtesting,
validation, dashboard, workspace TODO API, jobs/scheduling, lineage, secret scanning)
runs credential-less. This was re-verified: `make dashboard` API is live, and the
2026-07-11 credential recheck found no provider keys — which blocks only the
explicitly credential-gated tasks (T-011-05, T-017-05).

## 4. Credentials that can be added later (operator choice per item)

| Workflow | Credential | Operator options | Recommendation |
|---|---|---|---|
| Real AI benchmark runs (T-011-05) + AI cost telemetry (T-017-05) | one of `ANTHROPIC_API_KEY`/`OPENAI_API_KEY`/`GOOGLE_API_KEY` + `TIOS_AI_MODE=real` + `TIOS_AI_PROVIDER` | Configure now / **Add later** / Do not use | **Recommend: Add later** — configure one provider with a hard spend cap when you actually schedule Mode A runs; cost-tracking wiring (T-017-05) should land in the same change so spend is measured from the first call. |
| Paper/demo lane (S3) | venue testnet/demo keys | Add later (gate-controlled) | **Recommend: do not configure until S2 exit + HG-3 + T-015-01 decision.** Future-gated. |
| Live trading (S4) | venue live keys | Do not use | **Prohibited now.** Never withdrawal-enabled. Requires HG-4/5 + the 10 human-only items. |
| Remote lineage/storage | MLflow/DVC/S3 remotes | Add later | Only on AD §P reopen trigger. Future-gated. |

## 5. Security confirmations

1. `.env` is Git-ignored — verified with `git check-ignore -v .env` → `.gitignore:2`.
2. `.env.example` contains names and comments only — verified after edit.
3. No secret values found in repo (secret-scan test suite `tests/test_secret_scan.py`
   covers tracked files incl. artifacts; pre-commit hook installed per T-003-05).
4. No withdrawal-enabled, live-trading, or real-money credential is requested,
   documented, or referenced as needed now — consistent with D-028 and AD §AB.
5. AI spend credentials remain gated: cost controls (T-017-05) are not yet implemented,
   so provider keys stay "Add later" (this is the safe ordering).
6. Paper/testnet keys, when they arrive in S3, must live under distinct names
   (e.g. `*_TESTNET_*`) and never share a variable with a live key — recorded here as
   the intake rule for the future S3 credential intake gate
   (`specs/ENVIRONMENT_AND_CREDENTIALS_INTAKE_GATE_V1.md` rerun required).

## 6. Exact next credential actions for the operator

1. Nothing is required to continue current S2 offline work.
2. When (and only when) you want real AI benchmark runs: create one provider key with a
   spend cap, put it in local `.env` (never chat/Git), set `TIOS_AI_MODE=real` +
   `TIOS_AI_PROVIDER=<provider>` for that run, and record the decision via the
   dashboard workspace action for T-011-05.
3. Before S3: rerun the credential intake gate for testnet/demo keys only.
