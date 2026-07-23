# Phase-2b independent reviewer enrollment packet

Status: **PUBLIC PREPARATION ONLY — EXECUTION AUTHORITY `NONE`**

This packet prepares the next external gate described by `README.md`, `ACTIVATION.md`, and the
Phase-2b contracts. It is not an enrollment record, trust snapshot, activation ceremony, security
review, or authorization. Phase 3 and Phase 4 remain blocked.

## Non-negotiable boundary

- The reviewer must be a genuine independent person operating a separate reviewer-controlled
  machine. The operator host, this repository, another local account, a VM controlled by the
  operator, or an agent-generated identity does not establish independence.
- The reviewer generates and keeps the private Ed25519 key and passphrase exclusively on that
  separate machine. Neither may enter the operator host, repository, ticket, chat, transcript,
  backup shared with the operator, or any TIOS state directory.
- Only public metadata, the public key, its fingerprint, and the detached response to a
  non-secret operator challenge may cross the boundary. The public key and fingerprint must cross
  through an independently authenticated channel.
- Do not use these materials to create `allowed_signers`, a KRL, trust state, genesis, history,
  checkpoint, trusted-time state, or an activation receipt. Those require a later, separately
  approved and independently reviewed root-owned publication ceremony.
- Do not run network commands or `sudo` as part of this packet. Do not expose secrets while
  requesting help.

## Current independently checkable installation evidence

Observed on 2026-07-23:

| Evidence | Verified value |
| --- | --- |
| Installed directory | `/Library/PrivilegedHelperTools/com.tios.intake-verifier.d` |
| Directory ownership/mode | `root:wheel 0555` |
| Installed binary SHA-256 | `2b5021a0eade8f4de3c3ca03b589e452c84fa608d27fac7ea6fa16405c2e3640` |
| Installed binary ownership/mode | `root:wheel 0555` |
| Installed `MANIFEST.sha256` SHA-256 | `74b6c436b8d66d0cfef587e04934ffa9fdfb92989197a5ba485b95c7086cce1d` |
| Installed `MANIFEST.sha256` ownership/mode | `root:wheel 0444` |
| Installed version | `2` |
| Activation-source bundle SHA-256 | `72ab6bcac50764f1861708673fd858381c549dc9184e75f29020d79073133ba6` |
| Authority | `NONE` |

`/private/var/db/tios-intake` and
`/Library/PrivilegedHelperTools/com.tios.intake-authority.d` were absent when this packet was
prepared. The installed helper verifies signatures only; success means
`SIGNATURE_VERIFIED_SEMANTICS_UNVERIFIED`, not admission or activation.

## Sequential offline checklist

### 1. Reviewer: create a fresh key before any challenge exists

Run only on the separate reviewer-controlled machine, outside every repository. These commands
create a fresh reviewer-owned `0700` directory, prove both key targets absent and non-symlink, and
ask for the passphrase interactively:

```sh
umask 077
TIOS_REVIEWER_KEY_DIR=$(/usr/bin/mktemp -d "$HOME/tios-intake-reviewer.XXXXXXXX")
/bin/test -d "$TIOS_REVIEWER_KEY_DIR"
/bin/test ! -L "$TIOS_REVIEWER_KEY_DIR"
/bin/test "$(/usr/bin/stat -f '%Su:%HT:%Lp' "$TIOS_REVIEWER_KEY_DIR")" = "$(/usr/bin/id -un):Directory:700"
TIOS_REVIEWER_PRIVATE="$TIOS_REVIEWER_KEY_DIR/reviewer_ed25519"
TIOS_REVIEWER_PUBLIC="$TIOS_REVIEWER_PRIVATE.pub"
/bin/test ! -e "$TIOS_REVIEWER_PRIVATE"
/bin/test ! -L "$TIOS_REVIEWER_PRIVATE"
/bin/test ! -e "$TIOS_REVIEWER_PUBLIC"
/bin/test ! -L "$TIOS_REVIEWER_PUBLIC"
/usr/bin/ssh-keygen -t ed25519 -a 100 -f "$TIOS_REVIEWER_PRIVATE"
/bin/test "$(/usr/bin/stat -f '%Su:%HT:%Lp:%l' "$TIOS_REVIEWER_PRIVATE")" = "$(/usr/bin/id -un):Regular File:600:1"
/bin/test -f "$TIOS_REVIEWER_PUBLIC"
/bin/test ! -L "$TIOS_REVIEWER_PUBLIC"
/bin/test "$(/usr/bin/stat -f '%Su:%HT:%l' "$TIOS_REVIEWER_PUBLIC")" = "$(/usr/bin/id -un):Regular File:1"
/usr/bin/ssh-keygen -lf "$TIOS_REVIEWER_PUBLIC" -E sha256
/usr/bin/shasum -a 256 "$TIOS_REVIEWER_PUBLIC"
```

The private file and passphrase never leave that machine.

### 2. Reviewer and operator: authenticate the public key before challenge issuance

The reviewer transfers only the exact `.pub` file bytes, the SHA-256 fingerprint, and the exact
public-key file SHA-256 through an independently authenticated channel. The operator verifies the
reviewer's identity through that channel and compares the fingerprint and digest through an
independent authenticated confirmation. An unverified chat attachment alone is insufficient.

In an unprivileged directory outside the repository, the operator runs:

```sh
/bin/test -f tios_intake_reviewer.pub
/bin/test ! -L tios_intake_reviewer.pub
/bin/test "$(/usr/bin/stat -f '%HT:%l' tios_intake_reviewer.pub)" = 'Regular File:1'
/usr/bin/ssh-keygen -lf tios_intake_reviewer.pub -E sha256
/usr/bin/shasum -a 256 tios_intake_reviewer.pub
```

Both outputs must exactly match the independently authenticated values before continuing.

### 3. Operator: confirm the pending boundary

Run these commands sequentially from the repository root on the operator host. They are read-only,
offline, and unprivileged. No repository script is executed:

```sh
/usr/bin/git status --short -- ops/intake_trust/README.md ops/intake_trust/ACTIVATION.md ops/intake_trust/activate.sh ops/intake_trust/activation_policy.json ops/intake_trust/authority/main.swift ops/intake_trust/verifier/main.swift
/bin/test "$(/usr/bin/stat -f '%Su:%Sg:%HT:%Lp' /)" = 'root:wheel:Directory:755'
/bin/test "$(/usr/bin/stat -f '%Su:%Sg:%HT:%Lp' /Library)" = 'root:wheel:Directory:755'
/bin/test "$(/usr/bin/stat -f '%Su:%Sg:%HT:%Lp' /Library/PrivilegedHelperTools)" = 'root:wheel:Directory:755'
/bin/test "$(/usr/bin/stat -f '%Su:%Sg:%HT:%Lp' /private)" = 'root:wheel:Directory:755'
/bin/test "$(/usr/bin/stat -f '%Su:%Sg:%HT:%Lp' /private/var)" = 'root:wheel:Directory:755'
/bin/test "$(/usr/bin/stat -f '%Su:%Sg:%HT:%Lp' /private/var/db)" = 'root:wheel:Directory:755'
/bin/test "$(/usr/bin/stat -f '%Su:%Sg:%HT:%Lp' /Library/PrivilegedHelperTools/com.tios.intake-verifier.d)" = 'root:wheel:Directory:555'
/bin/test "$(/usr/bin/stat -f '%Su:%Sg:%HT:%Lp:%l' /Library/PrivilegedHelperTools/com.tios.intake-verifier.d/tios-intake-verifier)" = 'root:wheel:Regular File:555:1'
/bin/test "$(/usr/bin/stat -f '%Su:%Sg:%HT:%Lp:%l' /Library/PrivilegedHelperTools/com.tios.intake-verifier.d/MANIFEST.sha256)" = 'root:wheel:Regular File:444:1'
/usr/bin/shasum -a 256 /Library/PrivilegedHelperTools/com.tios.intake-verifier.d/tios-intake-verifier
/usr/bin/shasum -a 256 /Library/PrivilegedHelperTools/com.tios.intake-verifier.d/MANIFEST.sha256
/bin/test ! -e /private/var/db/tios-intake
/bin/test ! -L /private/var/db/tios-intake
/bin/test ! -e /Library/PrivilegedHelperTools/com.tios.intake-authority.d
/bin/test ! -L /Library/PrivilegedHelperTools/com.tios.intake-authority.d
```

The scoped Git command must print nothing; existing operational/data dirt elsewhere is out of
scope and must be preserved. The two hashes must equal the table above. Any command failure,
different hash, unsafe ancestor, linked file, or unexpected state path is a stop condition.
`activate.sh` is mutable repository source and is deliberately not executed by this packet.
The recorded state remains `SOURCE_ONLY_PENDING_EXTERNAL_ACTIVATION` / `BLOCKED`, with authority
`NONE`.

### 4. Operator: issue one canonical deny-unknown challenge

Only after Step 3 passes, assign unique `reviewer_id` and `credential_id` values. Each identifier
must be 1–128 ASCII characters and match `[A-Z0-9]+(?:[-_.][A-Z0-9]+)*`.

The challenge is one UTF-8 JSON object with exactly the fields below: no missing, duplicate, or
unknown fields; lexicographically sorted keys; no insignificant whitespace; no trailing newline;
no floats or control characters. `schema_version` is integer `1`. All other values are strings.
The exact canonical bytes are:

```json
{"activation_source_bundle_sha256":"72ab6bcac50764f1861708673fd858381c549dc9184e75f29020d79073133ba6","credential_id":"<CREDENTIAL_ID>","domain_separator":"TIOS/INTAKE-REVIEWER-KEY-POSSESSION-CHALLENGE/v1","execution_authority":"NONE","expires_at":"<YYYY-MM-DDTHH:MM:SSZ>","installed_manifest_sha256":"74b6c436b8d66d0cfef587e04934ffa9fdfb92989197a5ba485b95c7086cce1d","installed_verifier_sha256":"2b5021a0eade8f4de3c3ca03b589e452c84fa608d27fac7ea6fa16405c2e3640","nonce":"<64_LOWERCASE_HEX>","public_key_file_sha256":"<64_LOWERCASE_HEX>","reviewer_id":"<REVIEWER_ID>","reviewer_role":"INDEPENDENT_INTAKE_ADMISSION_REVIEWER","schema_version":1,"ssh_fingerprint":"<SHA256_FINGERPRINT>","sshsig_namespace":"tios-intake-reviewer-enrollment-challenge-v1","valid_from":"<YYYY-MM-DDTHH:MM:SSZ>","valid_until":"<YYYY-MM-DDTHH:MM:SSZ>"}
```

Replace every placeholder before issuance. SHA-256 fields and `nonce` are exactly 64 lowercase
hexadecimal characters. The SSH fingerprint is the exact authenticated `SHA256:` value.
`valid_from`, `valid_until`, and `expires_at` are canonical whole-second UTC; `valid_from` is
earlier than `valid_until`, and the challenge must be unexpired. The operator retains the exact
bytes and their SHA-256 through an independently controlled record.

The exact SSHSIG namespace is `tios-intake-reviewer-enrollment-challenge-v1`. It is
**challenge-only** and deliberately distinct from every namespace consumed by the installed
helper. The installed helper does not consume or validate this namespace or challenge.

### 5. Reviewer: validate and sign the exact challenge bytes

The reviewer places the authenticated exact bytes in
`tios-intake-reviewer-challenge-v1.json`, confirms its SHA-256 against the operator's independently
authenticated value, and checks every field against the public key and agreed request:

```sh
/usr/bin/shasum -a 256 tios-intake-reviewer-challenge-v1.json
/usr/bin/ssh-keygen -lf "$TIOS_REVIEWER_PUBLIC" -E sha256
/usr/bin/shasum -a 256 "$TIOS_REVIEWER_PUBLIC"
/usr/bin/ssh-keygen -Y sign -f "$TIOS_REVIEWER_PRIVATE" -n tios-intake-reviewer-enrollment-challenge-v1 tios-intake-reviewer-challenge-v1.json
```

Only the exact public challenge and
`tios-intake-reviewer-challenge-v1.json.sig` return to the operator. The detached signature is a
non-secret challenge response.

### 6. Operator: verify every binding and the public response offline

Before signature verification, deny the response unless the challenge has the exact field set and
canonical encoding from Step 4. Compare every bound value: domain, challenge-only namespace, both
1–128-character identifiers, exact public-key file SHA-256, SSH fingerprint, fixed reviewer role,
canonical validity interval, installed verifier hash, installed manifest hash, activation-source
bundle hash, nonce, expiry, schema version, and `execution_authority=NONE`. Recompute both public
key outputs and the exact challenge SHA-256.

Create an unprivileged public scratch key map named `challenge_verification_keys` containing
exactly one line:

```text
<REVIEWER_ID> ssh-ed25519 <PUBLIC_KEY_BASE64>
```

This scratch input is not the fixed TIOS `trust/allowed_signers`, is not trust state, and must
never be published under `/private/var/db/tios-intake`. Then run sequentially:

```sh
/usr/bin/ssh-keygen -lf tios_intake_reviewer.pub -E sha256
/usr/bin/shasum -a 256 tios_intake_reviewer.pub
/usr/bin/shasum -a 256 tios-intake-reviewer-challenge-v1.json
/usr/bin/ssh-keygen -Y verify -f challenge_verification_keys -I '<REVIEWER_ID>' -n tios-intake-reviewer-enrollment-challenge-v1 -s tios-intake-reviewer-challenge-v1.json.sig < tios-intake-reviewer-challenge-v1.json
```

Replace `<REVIEWER_ID>` with the exact bound identifier. A successful result is only a
**verified public challenge response** demonstrating possession of the corresponding private key
for these exact public bytes.

## Completion boundary

Completion does **not** create a `ReviewerCredential`, reviewer enrollment, trust, the fixed
`allowed_signers`, a KRL, root-owned state, a trust snapshot, reviewer independence approval, or
authority. It does not admit the public key. Separate operator authorization and independent
review are required to design and perform any credential-admission or trust-publication step.

Do not treat `reviewer_enrollment.example.json` as real evidence. It contains intentionally fake
values.

## Stop and escalation conditions

Stop if the reviewer is not operationally independent, any private material crossed the boundary,
the public channel was not independently authenticated, the challenge expired or changed, any
field or signature verification fails, the installed evidence differs, or someone requests
enrollment, trust publication, or activation from this packet.

The following remain **not implemented or not authorized**: credential admission, fixed
`allowed_signers`/KRL publication, root-owned trust/state initialization, trusted-time recovery,
authority installation, genesis/history/checkpoint publication, activation-receipt publication,
the fixed-path evidence resolver, independent security approval, and any activation command.
`activate.sh activate`, `init`, and `install` do not exist.

Nothing in this packet approves a strategy, establishes profitability, authorizes a venue or
order, enables live trading, or permits real-money execution.
