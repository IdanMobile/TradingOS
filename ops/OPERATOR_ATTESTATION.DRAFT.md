# Operator Attestation — DRAFT (pre-fill, not the real attestation)

Status: **DRAFT ONLY.** This file is `ops/OPERATOR_ATTESTATION.DRAFT.md`, not
`ops/OPERATOR_ATTESTATION.json`. It has no effect on `src/tios/approval/attestation.py`
(`load()` only reads `ops/OPERATOR_ATTESTATION.json`, per `DEFAULT_PATH` in that module).
Creating this file did not touch the real attestation, `PACKAGE_INTEGRITY_MANIFEST.md`
(checked: no `ops/` path is manifest-tracked, so this file is not integrity-gated), or any
other tracked artifact. `authorizes_live` is `false` throughout, and `attested_by` /
`attested_at` are left `UNSET` — nothing here constitutes the operator's actual sign-off.

Schema source: `ops/OPERATOR_ATTESTATION.example.json` and the authoritative loader/validator
`src/tios/approval/attestation.py` (`REQUIRED_FACTS`, `OperatorAttestation`, `authorizes()`).
The ten facts themselves are enumerated in `MISSING_AND_OPEN_ITEMS.md` §"Human-only before
live trading" (line ~703).

## 1. The ten facts: what project knowledge supports vs. what only the operator can supply

| # | Fact | What project knowledge suggests (source) | Confidence | Remaining human-only question |
|---|---|---|---|---|
| 1 | Venue (Israel/operator account eligibility) | `artifacts/reports/VENUE_ISRAEL_SOURCE_RECHECK_2026_07_11.md`: Kraken's official prohibited-jurisdiction source does not name Israel; Coinbase's prohibited-region source does not name Israel and its ID-verification page accepts Israeli documents. `DECISION_LOG.md` line ~154 separately notes OKX "promoted (Israel explicitly supported + demo environment)". The demo lane already runs against Bybit demo (`scripts/demo_eth_lane.py`), which is a distinct, already-approved *demo* choice (D-105/D-046), not a live-venue decision. | DERIVED-WEAK | Which venue will you actually use for **live** trading, and have you personally confirmed *your own account's* eligibility there? The recheck itself says explicitly: "this does not select a paper venue" and eligibility "remains account-specific and human-gated." |
| 2 | Account eligibility confirmed | None — this is inherently about a specific account the project has no visibility into. | HUMAN-ONLY | Is your specific account approved/eligible to trade on the chosen venue? |
| 3 | Product availability confirmed | Weak signal only: Coinbase/Coinbase Prime accept Israeli ID documents for identity verification (`VENUE_ISRAEL_SOURCE_RECHECK_2026_07_11.md`), which is identity-doc support, explicitly **not** a trading/product-availability guarantee per that same report. | HUMAN-ONLY | Are the exact spot products/pairs you intend to trade actually enabled on your account? |
| 4 | API trading permissions | `artifacts/reports/OPERATOR_ACCESS_PREP_CHECKLIST_2026_07_11.md` documents the *policy* to follow (start read-only where possible, IP-bind, narrowest permissions, withdrawal disabled) and reserves env-var names per venue. Code enforces the shape at the contract level: `RestrictedCredentialPolicy` in `src/tios/trading_domain/models.py` (~L1785) is `Stage.S4_LIVE`-only, rejects any policy naming `CredentialPermission.FUNDS_OUT` or `TRANSFER_FUNDS`, and requires `credential_material_present=False`. | DERIVED-STRONG (policy + code-enforced ceiling) / HUMAN-ONLY (actual key) | What exact permissions did you actually select when creating the real API key, and did you disable withdrawal/transfer as the policy requires? |
| 5 | Automated-trading terms reviewed | None found beyond the general instruction in the access-prep checklist to review "API terms" before creating keys. No project artifact can read or agree to a venue's ToS on the operator's behalf. | HUMAN-ONLY | Have you personally read and accepted the venue's current automated/API-trading terms? |
| 6 | Fee tier | None — fee tier is account-volume-specific and not derivable from any doc in this repo. `OPERATOR_ACCESS_PREP_CHECKLIST_2026_07_11.md` only instructs that fee tier be verified before S3/S4, it does not state one. | HUMAN-ONLY | What is your actual current maker/taker fee tier on the chosen venue account? |
| 7 | Funding path documented | `OPERATOR_ACCESS_PREP_CHECKLIST_2026_07_11.md` gives prep guidance (prefer subaccounts/demo credentials, no withdrawal permission) but does not and cannot state your actual deposit/withdrawal method. | HUMAN-ONLY | What is your documented funding path (bank/method), and where is it recorded (never in Git/chat)? |
| 8 | Credential isolation and revocation process | Fairly strong: `OPERATOR_ACCESS_PREP_CHECKLIST_2026_07_11.md` documents the process end to end (password-manager vault, least-privilege, IP-bound, revocable, no withdrawal); `RestrictedCredentialPolicy` (`src/tios/trading_domain/models.py`) makes the "no funds movement" half of that process a code-level `ContractError` rather than a convention. | DERIVED-STRONG for "a documented process exists and where" | Have you actually created the real credential following that documented process, and can you point `credential_isolation_process_ref` at where *your* execution of it is recorded? |
| 9 | Capital amount / max drawdown | None — inherently a personal financial decision. `src/tios/approval/attestation.py` only enforces the *shape* (`max_capital > 0`, `0 < max_drawdown_fraction <= 1`), never a value. | HUMAN-ONLY | How much capital, and what maximum drawdown fraction triggers your kill switch? |
| 10 | Tax/accounting workflow | None — personal/jurisdictional and outside project scope. | HUMAN-ONLY | What is your tax/accounting workflow reference (accountant, software, etc.)? |
| — | Final human approval (`attested_by`/`attested_at`) | N/A by construction — `attestation.py::template()` deliberately leaves these fields un-fillable by an agent: "a plausible-looking guess is worse than a blank because it reads as confirmed." | HUMAN-ONLY | Who is attesting, and when? |

**Note on an eleventh, undocumented requirement:** `MISSING_AND_OPEN_ITEMS.md` lists exactly
ten facts, but the actual enforcement code (`attestation.py::authorizes()`) also hard-blocks
on `kill_switch_conditions` being empty (`KILL_SWITCH_CONDITIONS_NOT_DECLARED`). The example
schema includes the field but the human-only-facts list doesn't call it out as fact #11. It is
HUMAN-ONLY regardless (what conditions should auto-halt trading is a risk-appetite decision),
flagged here so it isn't missed when the operator fills the real file.

## 2. Pre-filled draft (schema per `ops/OPERATOR_ATTESTATION.example.json`)

This is illustrative text inside this Markdown file — **not** a separate `.json` file, and
**not** `ops/OPERATOR_ATTESTATION.json`.

```json
{
  "schema_version": 1,
  "_comment": "DRAFT pre-fill. Not the real attestation. Every HUMAN:<question> placeholder must be replaced by the operator, in ops/OPERATOR_ATTESTATION.json, before it has any effect.",
  "venue": "HUMAN:Which venue will you use for live trading, and have you confirmed YOUR account's eligibility there? (Kraken/Coinbase cleared of blanket Israel-prohibition per 2026-07-11 official-source recheck; OKX separately noted as Israel-supporting with a demo env; none of this is account-specific eligibility.)",
  "account_eligibility_confirmed": "HUMAN:Is your specific account eligible/approved on the chosen venue?",
  "product_availability_confirmed": "HUMAN:Are the exact products/pairs you intend to trade enabled in your account?",
  "api_trading_permissions": "HUMAN:What exact API key permissions did you create (must exclude withdrawal/transfer per RestrictedCredentialPolicy)?",
  "automated_trading_terms_reviewed": "HUMAN:Have you read and accepted the venue's current automated/API-trading terms?",
  "fee_tier": "HUMAN:What is your actual current maker/taker fee tier?",
  "funding_path_documented": "HUMAN:What is your documented deposit/withdrawal path, and where is it recorded (not in Git/chat)?",
  "credential_isolation_process_ref": "HUMAN:Point this at where YOUR followed process is recorded. Documented process to follow: artifacts/reports/OPERATOR_ACCESS_PREP_CHECKLIST_2026_07_11.md (least-privilege, IP-bound, revocable, no withdrawal); code-level ceiling: RestrictedCredentialPolicy in src/tios/trading_domain/models.py.",
  "max_capital": "HUMAN:What dollar/currency amount of capital are you committing?",
  "max_drawdown_fraction": "HUMAN:What maximum drawdown fraction (0-1) halts trading?",
  "tax_workflow_ref": "HUMAN:What is your tax/accounting workflow reference?",
  "attested_by": "UNSET",
  "attested_at": "UNSET",
  "expires_at": null,
  "authorizes_live": false,
  "kill_switch_conditions": ["HUMAN:List the concrete auto-halt conditions you want enforced (e.g. drawdown breach, feed loss, manual halt)."]
}
```

Note: `authorizes_live: false` is not a placeholder — it must stay `false` in every draft and,
per `attestation.py::authorizes()`, live-authorizing states also independently require
`attestation.authorizes_live` to be explicitly `true`; a demo/paper attestation never
auto-escalates into live authority.

## 3. When this matters

The real `ops/OPERATOR_ATTESTATION.json` gates entry into `DEMO_STATES`
(`PAPER_APPROVED`/`PAPER_ACTIVE`) and `LIVE_STATES`
(`LIMITED_LIVE_REVIEW`/`LIMITED_LIVE_APPROVED`/`LIVE_APPROVED`) via
`attestation.authorizes()` — it is enforced automatically by the engine, not just a form.
It is an **S4 gate**: `MISSING_AND_OPEN_ITEMS.md` lists "S4/human-gated: `T-015-05` human-only
venue gates package," and today S3 and S4 both read `NOT_READY` per the retained
`artifacts/reports/S3_S4_CONTROL_PLANE_READINESS_2026_07_11.md` evidence — no strategy has
exited S2, so the attestation has nothing to unlock yet. Per the operator, 2026-07-21: live
authority is separately conditioned on the demo lane proving profitable first, on top of
everything above — filling this attestation is necessary but not sufficient for
`authorizes_live: true`.
