# Environment & Credentials Intake Gate V1

## Purpose

Before any implementation code starts, the coding agent must inventory all currently known environment requirements and anticipated credentials for the approved prototype, then ask the operator to choose per item:

- **A. Configure now**
- **B. Add later**
- **C. Do not use this integration**
- **D. Not sure — recommend**

Every item must independently support **Add later**.

No secret value may be written into chat, Markdown, Git, logs, reports, screenshots, or committed files.

---

## Gate order

1. Read the SSOT and required project files.
2. Inspect the actual local machine/repository environment.
3. Build the concrete intake list from the approved workstreams and detected environment.
4. Ask the operator the intake questions before scaffolding or coding.
5. Generate `.env.example` with names/comments only.
6. Verify `.gitignore` protects secret files.
7. Record choices in `artifacts/reports/PRE_CODE_ENVIRONMENT_INTAKE_REPORT.md` with no secrets.
8. Only then begin implementation.

---

## Intake categories

### A. Local development prerequisites

Examples to inspect and present only when relevant:

- Git
- Docker / Docker Compose
- Python runtime(s)
- Node.js runtime
- package managers such as uv/pip/poetry/pnpm
- .NET SDK if LEAN execution requires it
- Rust toolchain if a candidate installation path requires local compilation
- system build tools
- available disk space
- available RAM/CPU architecture

These are configuration prerequisites, not `.env` secrets.

### B. Public/free data access

Current prototype baseline:

- Official Binance public Spot data: expected to require no credential for the canonical frozen dataset.

The coding agent must verify this at execution time.

Do not require a paid data account when public data satisfies the current test.

### C. AI model providers — optional now

Present only providers actually supported by the benchmark harness or selected for the first controlled subset.

Potential examples, subject to current project choice:

- OpenAI API key → `OPENAI_API_KEY`
- Anthropic API key → `ANTHROPIC_API_KEY`
- Google/Gemini API key → `GOOGLE_API_KEY` or exact official SDK variable verified at implementation time
- other providers only if explicitly included in the benchmark plan

Status for MVP prototype: normally `Optional now`.

The operator may choose `Add later` for each provider independently.

### D. Experiment tracking / artifact storage

Default local prototype should prefer no external credential where possible.

Potential later items:

- remote MLflow tracking URI/token
- object storage credentials
- DVC remote credentials
- cloud database credentials

Status: `Add later` unless a defined prototype requirement proves local mode insufficient.

### E. Exchange access

Current canonical dataset path uses public data and should not need live credentials.

Do not ask for live exchange keys in this phase.

Potential later items, only at the first genuinely required gate:

- sandbox/testnet API key
- sandbox/testnet API secret
- read-only market/account credential where specifically justified

Never request:

- withdrawal-enabled credentials;
- unrestricted live-trading credentials;
- real-money brokerage credentials.

### F. Paid market-data providers

Examples already in research include Tardis.dev and future candidates.

Status: `Deferred until a later gate` unless a current experiment explicitly needs microstructure/tick/order-book data unavailable through approved free sources.

Each provider must have independent `Add later` choice.

### G. Optional infrastructure services

Examples:

- hosted database
- cloud object storage
- error monitoring
- hosted observability
- email/notification service

Default: do not require for the constrained local prototype. Present only if a workstream actually needs one.

---

## Required question format

For each item:

**Item N — [Service / Configuration]**

- **Purpose:** ...
- **Status:** Required now / Optional now / Deferred until later gate
- **Used by:** WS...
- **Local variable:** `VARIABLE_NAME` or `Not applicable`
- **Official platform:** exact verified name

Choose one:

- **A. Configure now**
- **B. Add later**
- **C. Do not use this integration**
- **D. Not sure — recommend**

**Recommended:** ...

**Why:** ...

The agent should batch the questions where practical, but every item keeps its own answer.

---

## Minimum expected first-pass intake

The coding agent must determine the exact list after environment inspection, but the first pass should normally cover:

1. Local container/runtime prerequisites.
2. AI provider credentials for any benchmark runs planned now.
3. Whether to keep MLflow/DVC fully local for the prototype.
4. Any optional sandbox/testnet credentials only if an approved test truly requires them.
5. Any optional paid-data provider only if an approved test truly requires it.

The absence of optional credentials must not block unrelated work.

---

## `.env` rules

Create `.env.example` only after the operator choices are known.

Rules:

- variable names and comments only;
- no real values;
- no placeholder that resembles a real secret;
- group by provider/workstream;
- mark optional/deferred variables clearly;
- never commit `.env`;
- ignore `.env`, `.env.local`, `.env.*.local`, credential JSON files, PEM keys, and provider-specific secret files as appropriate;
- do not ignore `.env.example`.

---

## Completion criteria

This gate passes when:

- the operator has received the full currently known intake list;
- each item has A/B/C/D disposition;
- required-now blockers are resolved or explicitly stop the affected workstream;
- optional/deferred items are recorded;
- `.env.example` reflects chosen integrations without secrets;
- Git ignore protection is verified;
- `artifacts/reports/PRE_CODE_ENVIRONMENT_INTAKE_REPORT.md` exists;
- no implementation code has been started before completion.
