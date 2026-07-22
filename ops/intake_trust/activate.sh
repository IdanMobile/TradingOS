#!/bin/sh
set -eu
PATH=/usr/bin:/bin
export PATH
LC_ALL=C
export LC_ALL

AUTHORITY_TARGET=/Library/PrivilegedHelperTools/com.tios.intake-authority.d
STATE_TARGET=/private/var/db/tios-intake/authority
COMMAND=${1-}

if /bin/test "$COMMAND" = status && /bin/test "${2-}" = --json && /bin/test "$#" -eq 2; then
  /usr/bin/printf '{"authority_path":"%s","execution_authority":"NONE","state_path":"%s","status":"SOURCE_ONLY_PENDING_EXTERNAL_ACTIVATION"}\n' "$AUTHORITY_TARGET" "$STATE_TARGET"
  exit 0
fi
if /bin/test "$COMMAND" = plan && /bin/test "${2-}" = --json && /bin/test "$#" -eq 2; then
  /usr/bin/printf '{"blockers":["EXTERNAL_REVIEWER_NOT_ENROLLED","ROOT_OWNED_STATE_NOT_INITIALIZED","SECURITY_REVIEW_NOT_COMPLETE","TRUSTED_TIME_NOT_INITIALIZED"],"execution_authority":"NONE","status":"BLOCKED"}\n'
  exit 0
fi
/bin/echo "usage: activate.sh status --json | plan --json (activate/init/install are unavailable)" >&2
exit 64
