#!/usr/bin/env python3
"""Supervised auto-start wrapper for the demo activity lane (launchd entry point).

The lane itself is reviewed order-path code and is NOT modified: every supervision concern lives
here, in one small auditable wrapper. On each start, before the lane can trade:

  1. KILL_SWITCH is absolute — a deliberately stopped lane is never resurrected.
  2. Crash-loop guard — bounded start history; too many starts in a window refuses the start.
  3. Audit — every supervised start, accepted or refused, lands in the operator's own ledger.
  4. Only then: exec the lane with a fixed argv built from module constants.

Both refusals exit 0. The LaunchAgent uses KeepAlive={SuccessfulExit: false}, so a clean exit is
launchd's signal to STAY DOWN; only a nonzero exit (a crash, or the lane's own exit 3 when another
lane already holds lane.lock) restarts it, and repeated restarts are what rail 2 exists to stop.

Demo/fake money, execution authority NONE, 0 validated strategies. Supervision increases
measurement uptime only — it does not and cannot improve results.

OUT OF SCOPE, deliberately: arm-expiry / periodic re-arm. An unattended start that never expires is
acceptable for fake money. An expiry MUST be added before this pattern is used with real money.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from tios.services.dashboard_api.audit import AuditPathError, confined_audit_handle

REPO_ROOT = Path(__file__).resolve().parents[1]
LANE_DIR = Path("artifacts/trading_domain/demo_lane")
KILL_SWITCH = LANE_DIR / "KILL_SWITCH"
START_HISTORY = LANE_DIR / "supervisor_starts.json"
AUDIT_PATH = Path("artifacts/human_decisions/demo_lane_actions.jsonl")

# Crash-loop guard. More than MAX_STARTS supervised starts inside WINDOW refuses the next one.
# Clear it with `make lane-supervise-clear-guard` (deletes START_HISTORY).
MAX_STARTS = 5
WINDOW = timedelta(minutes=10)
MAX_HISTORY = 20  # bound the file; only the newest entries can ever be inside WINDOW

# uv by absolute path: launchd gives the agent a minimal PATH that does not include ~/.local/bin.
UV_BIN = "/Users/user/.local/bin/uv"
LANE_ARGV: tuple[str, ...] = (
    UV_BIN,
    "run",
    "python",
    "scripts/demo_eth_lane.py",
    "--activity",
    "--loop",
    "--interval",
    "5m",
)

REFUSED_STAY_DOWN = 0  # clean exit; KeepAlive={SuccessfulExit:false} keeps a refused lane down


def _audit(detail: str) -> bool:
    """Append one supervisor record to the operator's human-decisions ledger. True if it landed.

    Same keys and types as the dashboard's own records (see dashboard_api/demo_lane.py), with
    `source` marking it launchd-initiated so an unattended start is never invisible. Never carries
    environment, credentials or command output — only the fixed action and a short outcome.
    """
    record: dict[str, Any] = {
        "schema_version": 1,
        "decided_at": datetime.now(tz=UTC).isoformat(),
        "source": "launchd_supervisor",
        "action": "SUPERVISED_START",
        "idempotency_key": str(uuid.uuid4()),
        "detail": detail,
        "environment": "VENUE_DEMO",
        "real_money": False,
    }
    try:
        with confined_audit_handle(REPO_ROOT, AUDIT_PATH, create=True) as handle:
            assert handle is not None
            handle.write(json.dumps(record, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    except (OSError, AuditPathError) as error:  # pragma: no cover - audit device failure
        print(f"supervisor audit unavailable: {error}", file=sys.stderr)
        return False
    return True


def _read_history(path: Path) -> list[datetime]:
    """Recent supervised start times, oldest first. A missing or corrupt file reads as empty."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    stamps = []
    for item in raw if isinstance(raw, list) else []:
        try:
            stamps.append(datetime.fromisoformat(str(item)))
        except ValueError:
            continue
    return stamps


def _write_history(path: Path, stamps: list[datetime]) -> None:
    """Atomic tmp+replace so a kill mid-write can never leave a truncated guard file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f".tmp.{os.getpid()}")
    temporary.write_text(
        json.dumps([stamp.isoformat() for stamp in stamps[-MAX_HISTORY:]]), encoding="utf-8"
    )
    os.replace(temporary, path)


def _launch() -> int:
    """Replace this process with the lane. Fixed argv, no shell, no input of any kind.

    execv propagates the lane's exit code by construction — this process IS the lane afterwards.
    """
    os.execv(LANE_ARGV[0], list(LANE_ARGV))


def main() -> int:
    os.chdir(REPO_ROOT)

    if KILL_SWITCH.exists():
        print("KILL_SWITCH present — refusing to start. The operator stopped this lane.")
        print(f"Clear it deliberately: rm {KILL_SWITCH}")
        _audit("refused: KILL_SWITCH present; supervised start must never resurrect a stopped lane")
        return REFUSED_STAY_DOWN

    now = datetime.now(tz=UTC)
    history = _read_history(START_HISTORY)
    recent = [stamp for stamp in history if now - stamp < WINDOW]
    if len(recent) >= MAX_STARTS:
        minutes = int(WINDOW.total_seconds() // 60)
        print(f"crash-loop guard: {len(recent)} supervised starts in {minutes}m — refusing.")
        print(f"Clear it: make lane-supervise-clear-guard  (deletes {START_HISTORY})")
        _audit(f"refused: crash-loop guard, {len(recent)} starts within {minutes}m")
        return REFUSED_STAY_DOWN

    # Both of the following FAIL CLOSED. An unattended start that cannot be counted or cannot be
    # audited is exactly the start nobody would ever find out about, so it does not happen: the
    # operator-facing claim is that a supervised start is never invisible, and that has to be a
    # guarantee rather than best effort. Refusals above stay best-effort — they launch nothing.
    try:
        _write_history(START_HISTORY, [*history, now])
    except OSError as error:
        print(f"cannot record this start ({error}) — refusing; the guard would be blind.")
        return REFUSED_STAY_DOWN

    if not _audit("accepted: launching the demo activity lane (fake money, authority NONE)"):
        print("cannot write the audit record — refusing; an unattended start must be visible.")
        return REFUSED_STAY_DOWN

    print("supervised start accepted — launching the demo activity lane.")
    return _launch()


if __name__ == "__main__":
    sys.exit(main())
