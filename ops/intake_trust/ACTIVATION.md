# Intake activation authority source (pending only)

This directory contains auditable source and contracts for a possible later Phase-2b activation
authority. It does **not** activate intake. Nothing here enrolls a reviewer, creates root-owned
state, signs a record, appends history, admits a decision, or grants strategy, campaign, venue,
order, live, or real-money authority. Every record retains `execution_authority=NONE`.

## Safe source inspection

`activate.sh` is deliberately planning/status-only despite its reserved name:

```sh
ops/intake_trust/activate.sh status --json
ops/intake_trust/activate.sh plan --json
```

The commands `activate`, `init`, and `install` do not exist and fail closed. Build a deterministic,
content-addressed source directory as an unprivileged user only. The output directory must already
exist, be owned by the caller, and have mode `0700`:

```sh
mkdir -m 700 /tmp/tios-intake-activation-source
ops/intake_trust/build_activation_bundle.sh --output-dir /tmp/tios-intake-activation-source
```

The builder rejects linked source files, hashes each source before and after copying, verifies the
private copied file and its type/link count, and uses no-clobber publication followed by exact
member, manifest, and digest verification. Its JSON output intentionally omits the filesystem path
and contains only fixed vocabulary plus the lowercase bundle digest, so quotes, backslashes, and
newlines in a valid output path cannot corrupt the JSON. The caller derives the directory name as
`<bundle_sha256>.activation-source.bundle` beneath the supplied output directory.

This unprivileged convenience builder detects ordinary source drift and blocks other unprivileged
users through its private output directory. It is not a defense against root or a malicious
concurrent process running as the same user, and it does not claim race-free or crash-durable
publication in a hostile parent filesystem. The returned digest and final directory must still be
reviewed through an independent channel. The builder does not use `sudo`, compile, install, or
write under `/Library` or `/private/var/db`.

## Required external activation evidence

An activation can be assessed only after all of these exist outside the writable repository and
pass independent security review:

1. The already reviewed root-owned signature-verifier helper and exact source-bundle digest.
2. An independent reviewer's public credential, exact allowed-signers file, revocation KRL, and
   trust snapshot. The reviewer private key never enters this repository or the operator host.
3. A root-owned activation policy whose digest exactly matches `activation_policy.json`.
4. One canonical `AuthorityGenesis` binding all helper, bundle, policy, and trust digests.
5. A persisted monotonic genesis head with the exact stream identity
   `INTAKE-ACTIVATION-AUTHORITY`, binding that genesis, plus a status receipt binding the supplied
   genesis, head, policy, and trust records. The time chain must satisfy
   `genesis.initialized_at <= head.observed_at <= receipt.issued_at <= current observation`.
   `ACTIVE_NO_DECISIONS` means only that this empty authority boundary was initialized; it does not
   admit any decision. A `BLOCKED` receipt can never satisfy the activation-snapshot validator.
6. A separate, reviewed state-publication ceremony and an independently signed review record.

Repository validation is necessary but never sufficient. `validate_activation_snapshot` checks
the cross-record bindings and trusted-time ordering without persisting state. The Swift source can
check bounded canonical genesis/receipt syntax but explicitly reports that semantics, bindings,
and persisted time remain externally unverified.

## Trusted-time design for the future installed authority

The proposed clock is the host OS wall clock read only by the installed root-owned authority. Its
last accepted whole-second UTC observation is stored at the fixed path in
`activation_policy.json`, inside a root-owned `0700` state tree, as one regular root-owned file
with link count one. A future reviewed publisher must use descriptor-relative operations, a new
same-directory temporary file, `fsync`, and atomic no-replace/compare-and-swap publication. It
must re-open and verify the resulting inode and bytes before returning a receipt.

The authority fails closed when:

- the current clock is earlier than the persisted observation (any rollback);
- the elapsed jump exceeds `maximum_forward_jump_seconds` without a separately reviewed recovery
  event that binds both observations;
- evidence or a receipt is expired, not-yet-valid, or older than policy permits;
- a timestamp is not canonical whole-second UTC, the state is missing/linked/multiply linked, or
  a crash/race leaves publication ambiguous;
- the genesis, monotonic head, policy, trust snapshot, or receipt digest does not bind the exact
  supplied record.

No recovery is implicit. An interruption or clock anomaly leaves activation blocked until an
independent review of the fixed state and a new signed recovery protocol. A malicious root user or
operator who can replace the OS, clock implementation, compiler, or root-owned state is outside
this local threat model; protection against that actor requires a separately designed external
transparency log or hardware-backed attestation. This exclusion does not convert operator action
into reviewer independence.

## Future root-boundary requirements (not implemented here)

Any later installation/initialization change must be separately operator-approved and reviewed.
It must use fixed absolute system tools and paths, validate all untrusted digests before path
derivation, copy into a unique root-owned staging directory, reject symlinks/hardlinks/unexpected
members, re-hash after copying, validate safe ancestors and exact ownership/modes, and atomically
publish a complete directory without overwrite. No repository or `/tmp` script may be executed as
root before a fail-fast digest precheck. This source bundle intentionally contains no such root
ceremony.
