# Stage-exit security review — 2026-07-20 (T-018-04)

Scope: the autonomous orchestration substrate added under D-107, plus the reopened T-018-04
obligation. The 2026-07-10 review was valid only for its then-current scope and was superseded
by the authenticated Bybit demo scripts added afterwards; D-046 quarantined those transports
and D-104/D-105 recorded stage-1 and stage-2 reviews of the sanctioned lane. This review covers
what D-107 introduced and does not re-certify the demo lane.

Reviewer: automated review during implementation. **This is not an independent review.** The
same process wrote the code under review, so it cannot satisfy D-099's requirement for an
independent SECURITY review before promotion. It is a self-review recorded honestly as such.

## Findings

### SEC-2026-07-20-01 — Path traversal in driver verifier allowlist (HIGH, FIXED)

**Found:** `dispatchable()` allowlisted verifier commands matching `scripts/<path>.py`, but the
path character class permitted `..`. `scripts/../../../etc/evil.py` matched the allowlist and
would have been executed.

**Impact:** anyone able to write a producer-map YAML — including a future automated process
that generates maps — could execute an arbitrary Python file anywhere on the filesystem, under
the project's interpreter and environment. The driver is designed to run unattended, so this
would execute without a human in the loop.

**Fix:** traversal segments are rejected in `dispatchable()`, and `check_blocker()`
independently resolves the path (following symlinks) and confirms containment inside
`scripts/`. Two checks rather than one because this executes code read from a config file.

**Verification:** `tests/test_driver.py::test_dispatchable_rejects_path_traversal` and
`::test_traversal_verifier_is_not_executed`.

## Surface review

| Component | Surface | Assessment |
|---|---|---|
| `ops/driver.py` | Executes verifiers named in YAML config | Allowlist + traversal guard + containment check; `shell=False`; fixed argv; 900s timeout. Prose verifiers report PENDING, never execute. |
| `ops/self_modification.py` | `git` and `make check` subprocesses | Argv tuples, `shell=False`. `gate_command` is an internal parameter with a fixed default, not caller-facing input. |
| `approval/attestation.py` | Reads operator JSON | No `eval`/`exec`; no credential fields by construction (test-enforced); filled file is gitignored; template refuses to load. |
| `validation/trial_budget.py` | Append-only JSONL under `flock` | No network, no exec. Concurrent appends serialised. |
| `evidence/staleness.py` | Reads and hashes declared module paths | Read-only. Reads paths from artifact metadata — see residual risk below. |
| `dashboard_api/orchestrator_view.py` | New `GET /api/v1/orchestrator` | Read-only projection; no control exposed; test-enforced absence of action keys. |
| `dashboard.html` orchestrator view | Renders orchestrator output | All interpolated values pass through the existing `esc()` HTML escaper. |

## Boundary confirmations

- No component reads, stores, transmits, or logs a credential.
- No component opens a network connection. The driver, orchestrator, and self-modification
  harness are entirely local.
- No component can place, sign, or simulate an order. `execution_authority` remains `NONE`.
- The sealed holdout remains unreachable: `splits.py` refuses attribute access, enforces the
  seal date, and permits exactly one recorded open; the driver honours declared
  `sealed_holdout_access: PROHIBITED` boundaries by withholding all dispatch.
- The immutable-path guard rejects diffs touching the eligibility contract, trial budget,
  attestation module, integrity manifest, or sealed directories — checked *before* the gate,
  so a constraint edit cannot pass by also passing tests.

## Residual risks (accepted, not fixed)

1. **`staleness.py` reads paths from artifact metadata.** It only hashes file contents and
   never executes, so a malicious path yields a wrong staleness verdict rather than code
   execution. Containment was not added because the failure mode is a misreported artifact,
   not compromise. Revisit if artifacts ever become externally sourced.

2. **Self-review, not independent review.** Recorded above; blocks any promotion claim.

## Applied during review

### SEC-2026-07-20-02 — Makefile was mutable (MEDIUM, FIXED)

`make check` is the gate every orchestrator change is judged by, and `Makefile` defines it.
Omitting it from `IMMUTABLE_PATHS` left exactly the hole the rest of that list exists to
close: a change could edit the standard it must meet. `Makefile` is now immutable to the
orchestrator. Cost: new make targets require an operator. That is the intended trade.

## Conclusion

The D-107 substrate introduces no network, credential, or execution capability. One HIGH
finding was identified and fixed during review; one recommendation is left open for an
explicit decision.

**This review does not satisfy the independent SECURITY review that D-099 requires for
promotion eligibility, and does not constitute HG-3 evidence.** A refreshed formal
stage-exit review by a reviewer independent of the implementation remains required before
HG-3/S3.
