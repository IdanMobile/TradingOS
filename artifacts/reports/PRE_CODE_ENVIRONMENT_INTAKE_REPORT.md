# Pre-Code Environment & Credentials Intake Report

Task: T-003-01 (HG-1 hard gate) per `specs/ENVIRONMENT_AND_CREDENTIALS_INTAKE_GATE_V1.md`
Date: 2026-07-06 · Operator: present, answered interactively · Secrets in this file: **none**

## 1. Machine inspection (read-only, 2026-07-06)

| Item | Found | Verdict |
|---|---|---|
| OS / arch | macOS 26.3.1, arm64 (Apple Silicon) | OK |
| CPU / RAM | 8 cores / 16 GB | OK for S1 (engine bake-off sequential runs recommended) |
| Disk free | ~118 GiB on data volume | OK (canonical dataset ≪ 10 GiB) |
| Git | 2.50.1 | OK |
| Python | 3.13.7 (`python3`, `python3.13`), 3.12.13 (`python3.12`) | OK — satisfies Freqtrade ≥3.11, Nautilus ≥3.12<3.15, vectorbt ≥3.11, Hummingbot ≥3.10.12 |
| uv | 0.11.4 | OK (primary env manager) |
| Docker | CLI 29.0.1 present; **daemon NOT running** | Blocker only for T-003-03 Docker lanes (LEAN, optionally Hummingbot). Action: start Docker Desktop before engine env builds. |
| .NET SDK | not installed | Not needed — LEAN path is Docker (official distribution). No local .NET compilation planned. |
| Node.js | v25.8.1 | OK (not currently required) |
| sqlite3 | 3.51.0 | OK |
| Xcode CLT | present (full Xcode) | OK (build tools available) |
| Homebrew | 6.0.2 | OK |
| Repo state | not yet a git repo; no `.gitignore`/`.env*` existed before this gate | Expected pre-bootstrap |

## 2. Intake items and operator dispositions

Question format per gate spec; A=Configure now, B=Add later, C=Do not use, D=Not sure—recommend.

| # | Item | Status | Used by | Variable | Operator choice |
|---|---|---|---|---|---|
| 1 | OpenAI API key | Optional now | WS8 (initiative 11) | `OPENAI_API_KEY` | **B — Add later** |
| 2 | Anthropic API key | Optional now | WS8 (initiative 11) | `ANTHROPIC_API_KEY` | **B — Add later** |
| 3 | Google/Gemini API key | Optional now | WS8 (initiative 11) | `GOOGLE_API_KEY` (re-verify SDK name at impl.) | **B — Add later** |
| 4 | MLflow + DVC storage mode | Required-now decision (no credential) | WS4 (initiative 07) | n/a | **A — Fully local** (file/SQLite MLflow backend + local DVC cache; zero credentials) |

Consequence of 1–3: the AI benchmark harness proceeds credential-less via the null provider (AD-11); absence of keys blocks no other workstream.

## 3. Items recorded without operator questions (per gate spec defaults)

| Item | Disposition | Rationale |
|---|---|---|
| Local prerequisites (Git/Python/uv/Docker CLI/etc.) | Present (see §1) | Configuration prerequisites, not credentials; only gap is Docker daemon start + no .NET (both covered above) |
| Binance public Spot data | No credential expected; verified at execution time in T-004 | Gate spec §B |
| Exchange sandbox/testnet keys | **Deferred** until a gate genuinely requires them | Gate spec §E — current dataset path is public data; live/withdrawal/real-money credentials are never requested |
| Paid market data (Tardis.dev et al.) | **Deferred** | Gate spec §F — no current experiment needs microstructure/tick data |
| Hosted infra (DB, object storage, monitoring, notifications) | **Not required** for local prototype | Gate spec §G |

## 4. Generated protections

- `.env.example` created — variable names/comments only, deferred items marked; no values, no realistic placeholders.
- `.gitignore` created — ignores `.env`, `.env.local`, `.env.*.local`, PEM/key files, credential JSON, `secrets/`; explicitly does **not** ignore `.env.example`. Verified by inspection (git repo initialized in T-003-02; gitignore audit test lands in T-003-05).

## 5. Completion criteria (gate spec)

- [x] Operator received the full currently known intake list
- [x] Each item has an A/B/C/D disposition (or a spec-default deferred disposition, §3)
- [x] No required-now blockers remain (Docker daemon start is a T-003-03 precondition, recorded, non-blocking now)
- [x] Optional/deferred items recorded
- [x] `.env.example` reflects choices, secret-free
- [x] Git ignore protection in place
- [x] This report exists at the mandated path
- [x] No implementation code was started before completion

**GATE RESULT: PASS.** Implementation (T-003-02 onward) is authorized.
