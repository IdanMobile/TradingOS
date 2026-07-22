#!/bin/sh
set -eu
PATH=/usr/bin:/bin
export PATH
LC_ALL=C
export LC_ALL

STAGING_ROOT=/private/var/db/tios-intake-staging
TARGET=/Library/PrivilegedHelperTools/com.tios.intake-verifier.d
STATE=/private/var/db/tios-intake

refuse() { /bin/echo "$1" >&2; exit 1; }
usage() { /bin/echo "usage: install.sh status --json | install --expected-bundle-sha256 <64-lowercase-hex>" >&2; exit 64; }
COMMAND=${1-}
if /bin/test "$COMMAND" = status && /bin/test "${2-}" = --json && /bin/test "$#" -eq 2; then
  /usr/bin/printf '{"execution_authority":"NONE","install_path":"%s","staging_root":"%s","status":"SETUP_ONLY_NOT_INSTALLED"}\n' "$TARGET" "$STAGING_ROOT"
  exit 0
fi
/bin/test "$COMMAND" = install && /bin/test "${2-}" = --expected-bundle-sha256 && /bin/test "$#" -eq 3 || usage
EXPECTED=$3
/bin/echo "$EXPECTED" | /usr/bin/grep -Eq '^[0-9a-f]{64}$' || usage
/bin/test "$(/usr/bin/id -u)" -eq 0 || refuse "install requires root"
/bin/test -x /usr/bin/swiftc || refuse "fixed compiler unavailable"
STAGED="$STAGING_ROOT/$EXPECTED.bundle"
/bin/test "$(cd "$(/usr/bin/dirname "$0")" && /bin/pwd -P)" = "$STAGED" || refuse "installer must execute from exact staged bundle"

check_dir() { /bin/test -d "$1" && /bin/test ! -L "$1" && /bin/test "$(/usr/bin/stat -f '%u:%g:%Lp' "$1")" = "0:0:$2" || refuse "unsafe directory: $1"; }
check_file() { /bin/test -f "$1" && /bin/test ! -L "$1" && /bin/test "$(/usr/bin/stat -f '%u:%g:%Lp:%l' "$1")" = "0:0:$2:1" || refuse "unsafe file: $1"; }
check_ancestor() { /bin/test -d "$1" && /bin/test ! -L "$1" && /bin/test "$(/usr/bin/stat -f '%u:%g:%OLp' "$1")" = "0:0:drwxr-xr-x" || refuse "unsafe ancestor: $1"; }
check_ancestor /Library
check_ancestor /Library/PrivilegedHelperTools
check_ancestor /private
check_ancestor /private/var
check_ancestor /private/var/db
check_dir "$STAGING_ROOT" 555
check_dir "$STAGED" 555
check_dir "$STAGED/verifier" 555
check_file "$STAGED/install.sh" 555
check_file "$STAGED/VERSION" 444
check_file "$STAGED/MANIFEST.sha256" 444
check_file "$STAGED/verifier/main.swift" 444
/bin/test "$(/usr/bin/find "$STAGED" -mindepth 1 -maxdepth 2 -print | /usr/bin/sed "s#^$STAGED/##" | /usr/bin/sort)" = "MANIFEST.sha256
VERSION
install.sh
verifier
verifier/main.swift" || refuse "staged file set mismatch"
/bin/test "$(/usr/bin/shasum -a 256 "$STAGED/MANIFEST.sha256" | /usr/bin/awk '{print $1}')" = "$EXPECTED" || refuse "bundle digest mismatch"
(cd "$STAGED" && /usr/bin/shasum -a 256 -c MANIFEST.sha256) >/dev/null || refuse "bundle manifest mismatch"
/bin/test ! -e "$TARGET" && /bin/test ! -L "$TARGET" || refuse "installed target already exists; inspect status rather than overwrite"
/bin/test ! -e "$STATE" && /bin/test ! -L "$STATE" || refuse "state path already exists; initialize separately after review"

PARENT=/Library/PrivilegedHelperTools
WORK=$(/usr/bin/mktemp -d "$PARENT/.com.tios.intake-verifier.XXXXXXXX")
trap '/bin/rm -rf "$WORK"' EXIT HUP INT TERM
/bin/mkdir "$WORK/source"
/bin/cp "$STAGED/MANIFEST.sha256" "$WORK/MANIFEST.sha256"
/bin/test "$(/usr/bin/shasum -a 256 "$WORK/MANIFEST.sha256" | /usr/bin/awk '{print $1}')" = "$EXPECTED" || refuse "manifest changed during copy"
EXPECTED_MAIN=$(/usr/bin/awk '$2 == "verifier/main.swift" {print $1}' "$WORK/MANIFEST.sha256")
/bin/echo "$EXPECTED_MAIN" | /usr/bin/grep -Eq '^[0-9a-f]{64}$' || refuse "main source manifest entry invalid"
/bin/cp "$STAGED/verifier/main.swift" "$WORK/source/main.swift"
/bin/cp "$STAGED/VERSION" "$WORK/VERSION"
/bin/test "$(/usr/bin/shasum -a 256 "$WORK/source/main.swift" | /usr/bin/awk '{print $1}')" = "$EXPECTED_MAIN" || refuse "staged bytes changed during copy"
/usr/bin/swiftc -O -whole-module-optimization -o "$WORK/tios-intake-verifier" "$WORK/source/main.swift"
/bin/rm -rf "$WORK/source"
/bin/chmod 0555 "$WORK" "$WORK/tios-intake-verifier"
/bin/chmod 0444 "$WORK/MANIFEST.sha256" "$WORK/VERSION"
/usr/sbin/chown -R root:wheel "$WORK"
/bin/mv "$WORK" "$TARGET"
trap - EXIT HUP INT TERM
check_dir "$TARGET" 555
check_file "$TARGET/tios-intake-verifier" 555
check_file "$TARGET/MANIFEST.sha256" 444
check_file "$TARGET/VERSION" 444
/bin/test "$(/usr/bin/find "$TARGET" -mindepth 1 -maxdepth 1 -print | /usr/bin/sed "s#^$TARGET/##" | /usr/bin/sort)" = "MANIFEST.sha256
VERSION
tios-intake-verifier" || refuse "post-install file set mismatch; operator inspection required"
/bin/echo "signature-verification helper installed; trust/state remain uninitialized and no authority is created"
