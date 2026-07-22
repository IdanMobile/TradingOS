#!/bin/sh
set -eu
PATH=/usr/bin:/bin
export PATH
LC_ALL=C
export LC_ALL

ROOT=$(/usr/bin/dirname "$0")
OUTPUT_ROOT=${2-}
/bin/test "${1-}" = --output-dir && /bin/test "$#" -eq 2 && /bin/test -d "$OUTPUT_ROOT" && /bin/test ! -L "$OUTPUT_ROOT" || {
  /bin/echo "usage: build_activation_bundle.sh --output-dir <existing-directory>" >&2
  exit 64
}
CALLER_UID=$(/usr/bin/id -u)
/bin/test "$(/usr/bin/stat -f '%u:%Lp' "$OUTPUT_ROOT")" = "$CALLER_UID:700" || {
  /bin/echo "output directory must be caller-owned mode 0700" >&2
  exit 1
}
WORK=$(/usr/bin/mktemp -d "$OUTPUT_ROOT/.tios-intake-activation.XXXXXXXX")
trap '/bin/chmod -R u+w "$WORK" 2>/dev/null || true; /bin/rm -rf "$WORK"' EXIT HUP INT TERM
/bin/test "$(/usr/bin/stat -f '%u:%Lp' "$WORK")" = "$CALLER_UID:700" || {
  /bin/echo "unsafe private work directory" >&2
  exit 1
}
/bin/mkdir "$WORK/bundle" "$WORK/bundle/authority"
for source in activate.sh activation_policy.json authority/main.swift; do
  /bin/test -f "$ROOT/$source" && /bin/test ! -L "$ROOT/$source" && /bin/test "$(/usr/bin/stat -f '%l' "$ROOT/$source")" -eq 1 || {
    /bin/echo "unsafe activation source" >&2
    exit 1
  }
  SOURCE_BEFORE=$(/usr/bin/shasum -a 256 < "$ROOT/$source" | /usr/bin/awk '{print $1}')
  /bin/cp "$ROOT/$source" "$WORK/bundle/$source"
  SOURCE_AFTER=$(/usr/bin/shasum -a 256 < "$ROOT/$source" | /usr/bin/awk '{print $1}')
  COPIED=$(/usr/bin/shasum -a 256 < "$WORK/bundle/$source" | /usr/bin/awk '{print $1}')
  /bin/test "$SOURCE_BEFORE" = "$SOURCE_AFTER" && /bin/test "$SOURCE_BEFORE" = "$COPIED" || {
    /bin/echo "activation source changed during copy" >&2
    exit 1
  }
  /bin/test -f "$ROOT/$source" && /bin/test ! -L "$ROOT/$source" && /bin/test "$(/usr/bin/stat -f '%l' "$ROOT/$source")" -eq 1 || {
    /bin/echo "activation source type changed during copy" >&2
    exit 1
  }
  /bin/test -f "$WORK/bundle/$source" && /bin/test ! -L "$WORK/bundle/$source" && /bin/test "$(/usr/bin/stat -f '%l' "$WORK/bundle/$source")" -eq 1 || {
    /bin/echo "unsafe copied activation source" >&2
    exit 1
  }
done
/usr/bin/printf '1\n' > "$WORK/bundle/VERSION"
(cd "$WORK/bundle" && {
  /usr/bin/shasum -a 256 VERSION
  /usr/bin/shasum -a 256 activate.sh
  /usr/bin/shasum -a 256 activation_policy.json
  /usr/bin/shasum -a 256 authority/main.swift
}) > "$WORK/bundle/MANIFEST.sha256"
DIGEST=$(/usr/bin/shasum -a 256 < "$WORK/bundle/MANIFEST.sha256" | /usr/bin/awk '{print $1}')
TARGET="$OUTPUT_ROOT/$DIGEST.activation-source.bundle"
/bin/test ! -e "$TARGET" && /bin/test ! -L "$TARGET" || { /bin/echo "bundle already exists" >&2; exit 1; }
/bin/mv -n "$WORK/bundle" "$TARGET"
/bin/test ! -e "$WORK/bundle" && /bin/test -d "$TARGET" && /bin/test ! -L "$TARGET" || {
  /bin/echo "no-clobber bundle publication failed" >&2
  exit 1
}
/bin/chmod 0555 "$TARGET" "$TARGET/authority" "$TARGET/activate.sh"
/bin/chmod 0444 "$TARGET/VERSION" "$TARGET/MANIFEST.sha256" "$TARGET/activation_policy.json" "$TARGET/authority/main.swift"
/bin/test "$(cd "$TARGET" && /usr/bin/find . -mindepth 1 -maxdepth 2 -print | /usr/bin/sed 's#^\./##' | /usr/bin/sort)" = "MANIFEST.sha256
VERSION
activate.sh
activation_policy.json
authority
authority/main.swift" || { /bin/echo "published file set mismatch" >&2; exit 1; }
(cd "$TARGET" && /usr/bin/shasum -a 256 -c MANIFEST.sha256) >/dev/null || {
  /bin/echo "published bundle manifest mismatch" >&2
  exit 1
}
/bin/test "$(/usr/bin/shasum -a 256 < "$TARGET/MANIFEST.sha256" | /usr/bin/awk '{print $1}')" = "$DIGEST" || {
  /bin/echo "published bundle digest mismatch" >&2
  exit 1
}
/usr/bin/printf '{"bundle_sha256":"%s","execution_authority":"NONE","status":"SOURCE_ONLY_PENDING_EXTERNAL_ACTIVATION"}\n' "$DIGEST"
