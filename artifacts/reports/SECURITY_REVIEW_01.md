# Security Review #1 — Bootstrap Baseline (T-003-05)

Date: 2026-07-06 · Reviewer: code-reviewer agent (SKILL_SECURITY_REVIEWER first pass) + fixes applied same day
Scope: foundation files only (.gitignore, .env.example, scripts/, Makefile, pyproject, tests/, engines/build_envs.sh, intake report)

## Verdict

**PASS.** Zero secrets found anywhere. Zero blocking findings. Six open items were raised; all six were fixed immediately (below). Remaining notes are recorded, non-blocking, with owners/triggers.

## Findings and dispositions

| # | Finding | Severity | Disposition |
|---|---|---|---|
| 1 | `engines/build_envs.sh` always exited 0 even with blocked lanes (silent success) | OPEN-ITEM | **FIXED** — script now exits 1 if any `engines/*/BLOCKER.md` exists |
| 2 | LEAN CLI installed unpinned | OPEN-ITEM | **FIXED** — pinned `lean==1.0.227` |
| 3 | Hummingbot pulled by mutable tag | OPEN-ITEM | **FIXED** — future pulls pinned to recorded `@sha256:1b14fca4…` digest |
| 4 | `engines/build.log` not gitignored (install logs not guaranteed secret-free) | OPEN-ITEM | **FIXED** — `*.log` ignored; added to gitignore audit test |
| 5 | Pre-commit secret-scan hook was opt-in only | OPEN-ITEM | **FIXED** — `scripts/bootstrap.py` now sets `core.hooksPath=scripts/githooks` automatically when `.git` exists |
| 6 | No DVC gitignore entries (future WS4 gap) | OPEN-ITEM | **FIXED** early — `.dvc/cache/`, `.dvc/tmp/` ignored + tested |

## Notes carried as recorded ceilings (non-blocking)

- Secret scanner is a deliberate minimal regex pass (`ponytail:` ceiling documented in `tests/test_secret_scan.py`). This pass added Stripe live keys and DSN-embedded credentials; JWT/generic `password=` detection deferred — upgrade path: gitleaks/detect-secrets if coverage proves insufficient.
- Live-state guard patterns now case-insensitive with mixed-case planted-state test; becomes the real forbidden-transition test when the `approval` state machine lands.
- `.gitignore` filename patterns can't catch extension-less keys (e.g. `id_rsa`); mitigated by the content-based PEM regex in the scanner (defense in depth).
- `make audit` uses a fixed temp path; acceptable single-dev local usage.

## Verification

- Full local gate green after fixes (`make check`: ruff, ruff format, mypy strict, pytest).
- `make audit` (pip-audit over exported lockfile): no known vulnerabilities (2026-07-06).
- Engine environments: all 5 lanes built and smoke-tested (freqtrade 2026.6, nautilus_trader 1.230.0, vectorbt 1.1.0, lean CLI 1.0.227, hummingbot image digest-recorded); zero BLOCKER records.
- vectorbt license verified from installed dist-info (RG-03/T-001-01): **Apache 2.0 with Commons Clause** — internal research use permitted; selling a product/service deriving value from it is not. Captured at `engines/vectorbt/LICENSE_CAPTURED.txt` (sha256 a914859a…ec84).
