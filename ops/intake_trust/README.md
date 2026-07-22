# Intake external-trust setup source

This directory is an auditable, setup-only bundle. It is not installed or activated by the
repository. It grants no intake, campaign, venue, order, or execution authority. The native
helper exposes only read-only `status --json` and `verify-decision`; it cannot sign receipts,
change trust, append history, advance checkpoints, or activate anything.

## Operator ceremony

Review every source file and build the deterministic source bundle as an unprivileged account:

```sh
mkdir /tmp/tios-intake-reviewed-bundles
ops/intake_trust/build_bundle.sh --output-dir /tmp/tios-intake-reviewed-bundles
```

Record both returned digests through the independent change-control channel. Do not execute
`install.sh` from the repository or unprivileged output. Run the following single fail-fast
ceremony from an unprivileged interactive shell. It reads rather than evaluates the recorded
values, validates them before `sudo`, revalidates them as root before deriving a path, copies the
mutable bundle into a unique root temporary directory, verifies it entirely with fixed system
tools, atomically stages it, prints `TIOS_INTAKE_PRECHECK_OK`, and immediately replaces the root
shell with only the verified staged installer. Any failure before that marker prevents execution.

```sh
/usr/bin/printf 'Reviewed bundle SHA-256: '
IFS= read -r tios_reviewed_bundle_sha256
/usr/bin/printf 'Reviewed installer SHA-256: '
IFS= read -r tios_reviewed_installer_sha256
case "$tios_reviewed_bundle_sha256" in *[!0-9a-f]*|'') /bin/echo 'invalid bundle digest' >&2; exit 1;; esac
case "$tios_reviewed_installer_sha256" in *[!0-9a-f]*|'') /bin/echo 'invalid installer digest' >&2; exit 1;; esac
/bin/test "${#tios_reviewed_bundle_sha256}" -eq 64 || exit 1
/bin/test "${#tios_reviewed_installer_sha256}" -eq 64 || exit 1
/usr/bin/sudo /usr/bin/env TIOS_BUNDLE_SHA256="$tios_reviewed_bundle_sha256" TIOS_INSTALLER_SHA256="$tios_reviewed_installer_sha256" /bin/sh <<'TIOS_ROOT_CEREMONY'
set -eu
case "$TIOS_BUNDLE_SHA256" in *[!0-9a-f]*|'') exit 1;; esac
case "$TIOS_INSTALLER_SHA256" in *[!0-9a-f]*|'') exit 1;; esac
/bin/test "${#TIOS_BUNDLE_SHA256}" -eq 64
/bin/test "${#TIOS_INSTALLER_SHA256}" -eq 64
TIOS_SOURCE=/tmp/tios-intake-reviewed-bundles/${TIOS_BUNDLE_SHA256}.bundle
TIOS_STAGING_ROOT=/private/var/db/tios-intake-staging
TIOS_FINAL=${TIOS_STAGING_ROOT}/${TIOS_BUNDLE_SHA256}.bundle
/bin/test "$(/usr/bin/stat -f '%Su:%Sg:%HT:%Lp' /private)" = 'root:wheel:Directory:755'
/bin/test "$(/usr/bin/stat -f '%Su:%Sg:%HT:%Lp' /private/var)" = 'root:wheel:Directory:755'
/bin/test "$(/usr/bin/stat -f '%Su:%Sg:%HT:%Lp' /private/var/db)" = 'root:wheel:Directory:755'
/bin/test "$(/usr/bin/stat -f '%HT' "$TIOS_SOURCE")" = 'Directory'
/usr/bin/install -d -o root -g wheel -m 0555 "$TIOS_STAGING_ROOT"
/bin/test "$(/usr/bin/stat -f '%Su:%Sg:%HT:%Lp' "$TIOS_STAGING_ROOT")" = 'root:wheel:Directory:555'
/bin/test ! -e "$TIOS_FINAL"
/bin/test ! -L "$TIOS_FINAL"
TIOS_WORK=$(/usr/bin/mktemp -d "$TIOS_STAGING_ROOT/.ceremony.XXXXXXXX")
trap '/bin/rm -rf "$TIOS_WORK"' EXIT HUP INT TERM
/bin/test "$(/usr/bin/stat -f '%Su:%Sg:%HT:%Lp' "$TIOS_WORK")" = 'root:wheel:Directory:700'
/bin/cp -R "$TIOS_SOURCE" "$TIOS_WORK/bundle"
/usr/bin/printf '%s\n' MANIFEST.sha256 VERSION install.sh verifier verifier/main.swift > "$TIOS_WORK/expected-members"
/usr/bin/find "$TIOS_WORK/bundle" -mindepth 1 -maxdepth 2 -print | /usr/bin/sed "s#^$TIOS_WORK/bundle/##" | /usr/bin/sort > "$TIOS_WORK/actual-members"
/usr/bin/diff -u "$TIOS_WORK/expected-members" "$TIOS_WORK/actual-members"
/bin/test "$(/usr/bin/stat -f '%HT' "$TIOS_WORK/bundle")" = 'Directory'
/bin/test "$(/usr/bin/stat -f '%HT' "$TIOS_WORK/bundle/verifier")" = 'Directory'
for TIOS_FILE in MANIFEST.sha256 VERSION install.sh verifier/main.swift; do
  /bin/test "$(/usr/bin/stat -f '%HT:%l' "$TIOS_WORK/bundle/$TIOS_FILE")" = 'Regular File:1'
done
/usr/sbin/chown root:wheel "$TIOS_WORK/bundle" "$TIOS_WORK/bundle/verifier" "$TIOS_WORK/bundle/MANIFEST.sha256" "$TIOS_WORK/bundle/VERSION" "$TIOS_WORK/bundle/install.sh" "$TIOS_WORK/bundle/verifier/main.swift"
/bin/chmod 0555 "$TIOS_WORK/bundle" "$TIOS_WORK/bundle/verifier" "$TIOS_WORK/bundle/install.sh"
/bin/chmod 0444 "$TIOS_WORK/bundle/MANIFEST.sha256" "$TIOS_WORK/bundle/VERSION" "$TIOS_WORK/bundle/verifier/main.swift"
/bin/test "$(/usr/bin/stat -f '%Su:%Sg:%HT:%Lp' "$TIOS_WORK/bundle")" = 'root:wheel:Directory:555'
/bin/test "$(/usr/bin/stat -f '%Su:%Sg:%HT:%Lp' "$TIOS_WORK/bundle/verifier")" = 'root:wheel:Directory:555'
for TIOS_FILE_MODE in 'MANIFEST.sha256:444' 'VERSION:444' 'install.sh:555' 'verifier/main.swift:444'; do
  TIOS_FILE=${TIOS_FILE_MODE%:*}
  TIOS_MODE=${TIOS_FILE_MODE##*:}
  /bin/test "$(/usr/bin/stat -f '%Su:%Sg:%HT:%Lp:%l' "$TIOS_WORK/bundle/$TIOS_FILE")" = "root:wheel:Regular File:$TIOS_MODE:1"
done
/bin/test "$(/usr/bin/shasum -a 256 "$TIOS_WORK/bundle/MANIFEST.sha256" | /usr/bin/awk '{print $1}')" = "$TIOS_BUNDLE_SHA256"
/bin/test "$(/usr/bin/shasum -a 256 "$TIOS_WORK/bundle/install.sh" | /usr/bin/awk '{print $1}')" = "$TIOS_INSTALLER_SHA256"
(cd "$TIOS_WORK/bundle" && /usr/bin/shasum -a 256 -c MANIFEST.sha256)
/bin/mv "$TIOS_WORK/bundle" "$TIOS_FINAL"
trap - EXIT HUP INT TERM
/bin/rm -rf "$TIOS_WORK"
/usr/bin/printf '%s\n' TIOS_INTAKE_PRECHECK_OK
exec "$TIOS_FINAL/install.sh" install --expected-bundle-sha256 "$TIOS_BUNDLE_SHA256"
TIOS_ROOT_CEREMONY
```

Do not pipe a network download into the root shell. The installer compiles with fixed
`/usr/bin/swiftc` and atomically publishes the complete root-owned directory
`/Library/PrivilegedHelperTools/com.tios.intake-verifier.d`. It deliberately does not create
`/private/var/db/tios-intake` or any trust/history/checkpoint data. Trust remains uninitialized:
the operator must separately review a later activation ceremony that creates
reviewed `trust/allowed_signers` and `trust/revoked.krl` files as `root:wheel 0444`. Until all
fixed files exist with exact ownership and modes, the helper fails closed.

`verify-decision` is a compatibility command name only. Its success result is exactly
`SIGNATURE_VERIFIED_SEMANTICS_UNVERIFIED`: it proves the SSH signature against the fixed exact
principal, namespace, allowed-signers file, and KRL. It does not parse or validate decision
semantics, advance external state, or reach an activation-pending assessment.

Publication is one same-parent atomic directory rename followed by fail-closed verification of
the complete installed file set, ownership, and modes. This setup does not independently prove
crash durability of the parent directory entry. After interruption, the operator must inspect
the fixed target and rerun the reviewed ceremony only after resolving any existing target; the
installer never overwrites or repairs a partial/uncertain target.

## Independent reviewer enrollment

On a reviewer-controlled machine, outside this repository and outside the helper host, the
reviewer generates a passphrase-protected Ed25519 key:

```sh
/usr/bin/ssh-keygen -t ed25519 -a 100 -f "$HOME/.ssh/tios_intake_reviewer"
/usr/bin/ssh-keygen -lf "$HOME/.ssh/tios_intake_reviewer.pub" -E sha256
```

The reviewer chooses and enters the passphrase interactively; it must not appear in a command,
file here, ticket, chat, or operator transcript. Only the `.pub` line, SHA-256 fingerprint,
assigned reviewer/credential identifiers, and operator-issued non-secret challenge cross the
enrollment boundary. The private key stays exclusively with the independent reviewer and never
enters the repository, installed helper, state directory, or operator machine. The example JSON
contains intentionally fake public metadata and is not an enrollment record.

Credential validity, challenge verification, allowed-signers/KRL creation, trusted time,
authoritative history/checkpoint activation, and independent security review are deliberately
outside this setup slice and remain blockers.
