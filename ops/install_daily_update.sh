#!/usr/bin/env bash
# Install a launchd agent that runs the dataset daily-update every day (macOS).
# Idempotent. Offline data refresh only — no venue, order, or credential.
# Uninstall: launchctl bootout gui/$UID/com.tios.dailyupdate
#
# TCC note: from ~/Downloads, ~/Desktop, ~/Documents a background agent is denied
# folder access unless you grant Full Disk Access to the Python binary printed below.
# After granting it, re-run with --force. (Cleaner long-term: move the project out.)
set -euo pipefail

FORCE=0
if [ "${1:-}" = "--force" ]; then FORCE=1; shift; fi
HOUR="${1:-6}"      # local hour to run (default 06:xx)
MINUTE="${2:-10}"

LABEL="com.tios.dailyupdate"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$ROOT/.venv/bin/python"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG="$HOME/Library/Logs/tios_daily_update.log"

[ -x "$PY" ] || { echo "venv python not found at $PY — run the project's install first"; exit 1; }
# FDA is keyed to the RESOLVED binary (PY_REAL) — that's what you authorize. But the
# agent invokes the venv symlink ($PY): it resolves to the same FDA-granted binary yet
# keeps the venv's site-packages (pyarrow etc.), which the bare base interpreter lacks.
PY_REAL="$("$PY" -c 'import sys; print(sys._base_executable)')"

case "$ROOT/" in
  "$HOME/Downloads/"*|"$HOME/Desktop/"*|"$HOME/Documents/"*)
    if [ "$FORCE" -ne 1 ]; then
      echo "REFUSING: project is under a macOS TCC-protected folder:"
      echo "  $ROOT"
      echo "A scheduled launchd agent cannot access it until you either:"
      echo "  1. move the project outside ~/Downloads, ~/Desktop, ~/Documents, then re-run; or"
      echo "  2. grant Full Disk Access to this exact binary, then re-run with --force:"
      echo "       $PY_REAL"
      echo "Meanwhile the dashboard 'Refresh data now' button already works."
      exit 2
    fi
    echo "note: installing from a TCC-protected folder (--force). This only works if you have"
    echo "      granted Full Disk Access to: $PY_REAL"
    ;;
esac

mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PY</string><string>-m</string><string>tios.dataset.daily_update</string>
  </array>
  <key>WorkingDirectory</key><string>$ROOT</string>
  <key>EnvironmentVariables</key><dict><key>PYTHONPATH</key><string>$ROOT/src</string></dict>
  <key>StartCalendarInterval</key><dict>
    <key>Hour</key><integer>$HOUR</integer><key>Minute</key><integer>$MINUTE</integer>
  </dict>
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
</dict></plist>
PLIST

launchctl bootout "gui/$UID/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$UID" "$PLIST"
echo "installed $LABEL — runs daily at $(printf '%02d:%02d' "$HOUR" "$MINUTE") local"
echo "plist:  $PLIST"
echo "test:   launchctl kickstart gui/$UID/$LABEL   &&  sleep 8  &&  cat $LOG"
