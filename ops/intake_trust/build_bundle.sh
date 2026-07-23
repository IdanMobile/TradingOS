#!/bin/sh
set -eu
PATH=/usr/bin:/bin
export PATH
LC_ALL=C
export LC_ALL

ROOT=$(/usr/bin/dirname "$0")
OUTPUT_ROOT=${2-}
/bin/test "${1-}" = --output-dir && /bin/test "$#" -eq 2 && /bin/test -d "$OUTPUT_ROOT" && /bin/test ! -L "$OUTPUT_ROOT" || {
  /bin/echo "usage: build_bundle.sh --output-dir <existing-directory>" >&2
  exit 64
}
WORK=$(/usr/bin/mktemp -d "$OUTPUT_ROOT/.tios-intake-bundle.XXXXXXXX")
trap '/bin/chmod -R u+w "$WORK" 2>/dev/null || true; /bin/rm -rf "$WORK"' EXIT HUP INT TERM
/bin/mkdir "$WORK/bundle"
for source in install.sh verifier/main.swift; do
  /bin/test -f "$ROOT/$source" && /bin/test ! -L "$ROOT/$source" || { /bin/echo "unsafe source" >&2; exit 1; }
  /bin/mkdir -p "$WORK/bundle/$(/usr/bin/dirname "$source")"
  /bin/cp "$ROOT/$source" "$WORK/bundle/$source"
done
/usr/bin/printf '2\n' > "$WORK/bundle/VERSION"
(cd "$WORK/bundle" && {
  /usr/bin/shasum -a 256 VERSION
  /usr/bin/shasum -a 256 install.sh
  /usr/bin/shasum -a 256 verifier/main.swift
}) > "$WORK/bundle/MANIFEST.sha256"
DIGEST=$(/usr/bin/shasum -a 256 "$WORK/bundle/MANIFEST.sha256" | /usr/bin/awk '{print $1}')
INSTALLER_SHA=$(/usr/bin/shasum -a 256 "$WORK/bundle/install.sh" | /usr/bin/awk '{print $1}')
TARGET="$OUTPUT_ROOT/$DIGEST.bundle"
/bin/test ! -e "$TARGET" && /bin/test ! -L "$TARGET" || { /bin/echo "bundle already exists" >&2; exit 1; }
/bin/mv "$WORK/bundle" "$TARGET"
/bin/chmod 0555 "$TARGET" "$TARGET/verifier" "$TARGET/install.sh"
/bin/chmod 0444 "$TARGET/VERSION" "$TARGET/MANIFEST.sha256" "$TARGET/verifier/main.swift"
/usr/bin/printf '{"bundle_path":"%s","bundle_sha256":"%s","execution_authority":"NONE","installer_sha256":"%s","status":"SETUP_ONLY_NOT_STAGED"}\n' "$TARGET" "$DIGEST" "$INSTALLER_SHA"
