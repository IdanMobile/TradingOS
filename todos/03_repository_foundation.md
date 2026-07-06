# Initiative 03 — Repository Foundation (S1, WS1) — CRITICAL PATH

Requirement source: SSOT WS1; AD §F/§G/§AH. All tasks: skill R7 (coding agent). Precondition for the whole initiative: **HG-1 intake gate passed** (`artifacts/reports/PRE_CODE_ENVIRONMENT_INTAKE_REPORT.md` exists).

## T-003-01 Pre-code environment & credentials intake — HARD GATE
- Purpose: execute `specs/ENVIRONMENT_AND_CREDENTIALS_INTAKE_GATE_V1.md` exactly. Requirement: REQ-001.
- Actions: inspect machine (read-only); build intake list; present A/B/C/D per item; generate `.env.example` + `.gitignore`; write intake report.
- Outputs: intake report; `.env.example`; `.gitignore`. Human approval: **Yes (operator answers)**. Credentials: names only, never values.
- Acceptance: intake-gate completion criteria all true; zero secrets anywhere. Failure: any secret value in any file/chat → stop, rotate, record.
- Complexity: M. Blocks: everything. Status: **DONE 2026-07-06** (gate PASS; report at artifacts/reports/PRE_CODE_ENVIRONMENT_INTAKE_REPORT.md).

## T-003-02 Workspace bootstrap
- Purpose: create the AD §F tree (src/tios skeleton per MODULE_CATALOG, artifacts/, fixtures/, tests/) without app scaffolding beyond the skeleton. Requirement: REQ-002.
- Actions: git init (if needed); create module skeletons with empty ports; create `artifacts/` evidence tree (SSOT WS1 list); machine-readable manifest stubs.
- Outputs: repo tree; `artifacts/**` dirs; bootstrap script. Acceptance: bootstrap script re-runs idempotently on a clean checkout. Complexity: M. Dependencies: T-003-01. Status: **DONE 2026-07-06**.

## T-003-03 Per-engine isolated environments
- Purpose: AD-02; RG-04. Requirement: REQ-003.
- Actions: create `engines/<name>/` env definitions (venv or Docker per engine's official install path: Freqtrade py≥3.11, Nautilus py≥3.12<3.15, LEAN Docker/.NET, Hummingbot py≥3.10.12/Docker, vectorbt py≥3.11 pandas-3 stack); pin versions; record env manifests.
- Outputs: env definitions + build scripts + version manifests. Acceptance: each env builds on the target Mac OR a reproducible blocker record exists (no-regression-by-omission). Failure: silent skip of a candidate. Complexity: L. Dependencies: T-003-02. Parallelizable: Yes (per engine). Status: **DONE 2026-07-06**.

## T-003-04 Local gate (one command)
- Purpose: TEST_MASTER_PLAN §5 local gate. Requirement: REQ-004.
- Actions: choose+pin lint/type/test tooling (verify current versions); wire pytest+hypothesis, ruff, type checker, architecture-dependency test, secret scan, decision-ID uniqueness check; single entry command.
- Outputs: gate config + `make check`-equivalent; docs in README-dev. Acceptance: gate runs <5 min on skeleton; deliberately-broken fixtures fail it (prove it can fail). Complexity: M. Dependencies: T-003-02. Status: **DONE 2026-07-06**.

## T-003-05 Security baseline
- Purpose: AD §AB minimums at bootstrap. Requirement: REQ-005.
- Actions: secret-scan hook; gitignore audit test; live-state-unreachable placeholder test; dependency-audit wiring; SKILL_SECURITY_REVIEWER first pass.
- Outputs: security review report #1. Acceptance: zero blocking findings or all recorded as open items. Complexity: S. Dependencies: T-003-04. Status: **DONE 2026-07-06**.
