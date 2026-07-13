#!/usr/bin/env python3
"""Checkpoint complete prospective windows on one bounded public WebSocket run."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from run_prospective_liquidation_observer import (
    AUTHORITY,
    DEFAULT_OUTPUT,
    EXPECTED_PAIR,
    EXPECTED_SYMBOL,
    WEBSOCKET_URL,
    CaptureResult,
    build_session,
    canonical_bytes,
    fetch_exchange_info,
    parse_utc,
    run_commit,
    session_history,
    sha256,
    utc_now,
    verify_directory,
    write_bytes_content_addressed,
)
from websockets.asyncio.client import connect

from tios.strategy.liquidation_stress import (
    LiquidationStressError,
    LiquidationWindow,
    parse_force_order_message,
    window_start,
)

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "research/PROSPECTIVE_BTC_LIQUIDATION_PERSISTENT_OBSERVATION_V1.yaml"
ROTATE_AFTER = timedelta(hours=23, minutes=30)
HEARTBEAT_SECONDS = 30
BACKOFF_SECONDS = (5, 15, 30, 60)
MAX_RECONNECTS = 10


@dataclass(slots=True)
class SourceConnection:
    websocket: Any
    opened_at: datetime
    connection_epoch: int
    exchange_info_hash: str
    contract_size: Decimal


def write_atomic_json(path: Path, payload: object) -> None:
    data = canonical_bytes(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def next_epochs(directory: Path) -> tuple[int, int]:
    connection = continuity = 0
    for path in directory.glob("session_*.json"):
        metadata = json.loads(path.read_text()).get("persistent_observation")
        if isinstance(metadata, dict):
            connection = max(connection, int(metadata["connection_epoch"]))
            continuity = max(continuity, int(metadata["continuity_epoch"]))
    return connection + 1, continuity + 1


def status_payload(
    *,
    commit: str,
    process_started_at: datetime,
    state: str,
    connection_epoch: int,
    continuity_epoch: int,
    finalized: int,
    last_window: datetime | None,
    last_failure_ref: str | None,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "operations_contract_sha256": sha256(CONTRACT.read_bytes()),
        "run_commit": commit,
        "process_started_at": process_started_at.isoformat(),
        "heartbeat_at": utc_now().isoformat(),
        "state": state,
        "connection_epoch": connection_epoch,
        "continuity_epoch": continuity_epoch,
        "finalized_window_count": finalized,
        "last_finalized_window_start": last_window.isoformat() if last_window else None,
        "last_failure_ref": last_failure_ref,
        "authority": AUTHORITY,
    }


def decorate_session(
    session: dict[str, Any],
    *,
    run_id: str,
    checkpoint_index: int,
    source: SourceConnection,
    continuity_epoch: int,
    checkpoint_status: str,
    planned_handoff: dict[str, object] | None,
) -> dict[str, Any]:
    session["schema_version"] = 5
    session["persistent_observation"] = {
        "operations_contract_sha256": sha256(CONTRACT.read_bytes()),
        "run_id": run_id,
        "checkpoint_index": checkpoint_index,
        "connection_epoch": source.connection_epoch,
        "continuity_epoch": continuity_epoch,
        "connection_opened_at": source.opened_at.isoformat(),
        "checkpoint_status": checkpoint_status,
        "planned_handoff": planned_handoff,
    }
    return session


def row_to_window(row: dict[str, object]) -> LiquidationWindow:
    return LiquidationWindow(
        start=parse_utc(row["start"]),
        complete=row["complete"] is True,
        event_count=int(str(row["event_count"])),
        gross_notional_usd=Decimal(str(row["gross_notional_usd"])),
        buy_notional_usd=Decimal(str(row["buy_notional_usd"])),
        sell_notional_usd=Decimal(str(row["sell_notional_usd"])),
    )


async def open_source(directory: Path, connection_epoch: int) -> SourceConnection:
    exchange_info, contract_size = await asyncio.to_thread(fetch_exchange_info)
    exchange_hash = sha256(exchange_info)
    write_bytes_content_addressed(directory / "raw", "exchange_info", exchange_info)
    websocket = await connect(
        WEBSOCKET_URL,
        open_timeout=15,
        close_timeout=5,
        ping_interval=20,
        max_size=1_000_000,
    )
    return SourceConnection(websocket, utc_now(), connection_epoch, exchange_hash, contract_size)


async def close_source(source: SourceConnection | None) -> None:
    if source is not None:
        await source.websocket.close()


def retain_session(directory: Path, session: dict[str, Any]) -> Path:
    path = write_bytes_content_addressed(directory, "session", canonical_bytes(session))
    if path.stem.removeprefix("session_") != sha256(path.read_bytes()):
        raise LiquidationStressError("checkpoint hash mismatch after atomic write")
    return path


async def run_checkpoints(directory: Path, requested: int) -> int:
    verify_directory(directory)
    history = list(session_history(directory))
    commit = run_commit()
    process_started_at = utc_now()
    run_id = sha256(f"{commit}|{process_started_at.isoformat()}".encode())[:24]
    connection_epoch, continuity_epoch = next_epochs(directory)
    status_path = directory / "operations" / "status.json"
    finalized = reconnects = 0
    last_window: datetime | None = None
    last_failure_ref: str | None = None
    source: SourceConnection | None = None
    replacement: SourceConnection | None = None
    planned_handoff: dict[str, object] | None = None

    def heartbeat(state: str) -> None:
        write_atomic_json(
            status_path,
            status_payload(
                commit=commit,
                process_started_at=process_started_at,
                state=state,
                connection_epoch=connection_epoch,
                continuity_epoch=continuity_epoch,
                finalized=finalized,
                last_window=last_window,
                last_failure_ref=last_failure_ref,
            ),
        )

    while finalized < requested:
        events_by_window: dict[datetime, list[dict[str, str]]] = {}
        rejected_event: dict[str, str] | None = None
        current_start = utc_now()
        try:
            heartbeat("CONNECTING")
            source = await open_source(directory, connection_epoch)
            current_start = window_start(source.opened_at) + timedelta(minutes=5)
            heartbeat("OBSERVING")
            while finalized < requested:
                current_end = current_start + timedelta(minutes=5)
                while utc_now() < current_end:
                    if replacement is None and utc_now() - source.opened_at >= ROTATE_AFTER:
                        replacement = await open_source(directory, connection_epoch + 1)
                    heartbeat("OBSERVING")
                    remaining = max(0.001, (current_end - utc_now()).total_seconds())
                    try:
                        async with asyncio.timeout(min(HEARTBEAT_SECONDS, remaining)):
                            message = await source.websocket.recv()
                    except TimeoutError:
                        continue
                    if not isinstance(message, str):
                        raise LiquidationStressError("binary websocket message is not accepted")
                    received_at = utc_now()
                    try:
                        snapshot = parse_force_order_message(
                            message,
                            received_at=received_at,
                            expected_symbol=EXPECTED_SYMBOL,
                            expected_pair=EXPECTED_PAIR,
                            contract_size_usd=source.contract_size,
                        )
                    except Exception:
                        rejected_event = {
                            "raw_message": message,
                            "received_at": received_at.isoformat(),
                        }
                        raise
                    event_window = window_start(snapshot.event_time)
                    if event_window >= current_start:
                        events_by_window.setdefault(event_window, []).append(
                            {"raw_message": message, "received_at": received_at.isoformat()}
                        )

                ended_at = current_end
                result = CaptureResult(
                    events_by_window.pop(current_start, []),
                    "COMPLETE",
                    current_start,
                    ended_at,
                )
                session = build_session(
                    started_at=current_start,
                    ended_at=ended_at,
                    requested_duration_seconds=None,
                    requested_complete_windows=1,
                    capture_result=result,
                    exchange_info_hash=source.exchange_info_hash,
                    contract_size=source.contract_size,
                    run_commit=commit,
                    prior_windows=tuple(history),
                )
                session = decorate_session(
                    session,
                    run_id=run_id,
                    checkpoint_index=finalized + 1,
                    source=source,
                    continuity_epoch=continuity_epoch,
                    checkpoint_status="FINALIZED",
                    planned_handoff=planned_handoff,
                )
                retain_session(directory, session)
                row = session["observation"]["complete_windows"]
                if len(row) != 1:
                    raise LiquidationStressError("checkpoint must finalize exactly one window")
                history.append(row_to_window(row[0]))
                finalized += 1
                reconnects = 0
                last_window = current_start
                heartbeat("CHECKPOINTED")
                current_start = current_end
                planned_handoff = None
                if replacement is not None:
                    old_epoch = source.connection_epoch
                    overlap_started_at = replacement.opened_at
                    await close_source(source)
                    source = replacement
                    replacement = None
                    connection_epoch = source.connection_epoch
                    planned_handoff = {
                        "from_connection_epoch": old_epoch,
                        "overlap_started_at": overlap_started_at.isoformat(),
                        "handoff_boundary": current_start.isoformat(),
                    }
                    events_by_window.clear()
            break
        except Exception as error:
            ended_at = utc_now()
            failure_start = (
                current_start if current_start <= ended_at or source is None else source.opened_at
            )
            error_type = type(error).__name__
            failure = CaptureResult(
                events_by_window.get(current_start, []),
                f"FAILED_{error_type}",
                failure_start,
                ended_at,
                error_type,
                str(error),
                rejected_event,
            )
            if source is not None:
                session = build_session(
                    started_at=failure_start,
                    ended_at=ended_at,
                    requested_duration_seconds=None,
                    requested_complete_windows=1,
                    capture_result=failure,
                    exchange_info_hash=source.exchange_info_hash,
                    contract_size=source.contract_size,
                    run_commit=commit,
                    prior_windows=tuple(history),
                )
                session = decorate_session(
                    session,
                    run_id=run_id,
                    checkpoint_index=finalized + 1,
                    source=source,
                    continuity_epoch=continuity_epoch,
                    checkpoint_status="FAILED_PARTIAL",
                    planned_handoff=planned_handoff,
                )
                last_failure_ref = retain_session(directory, session).name
            await close_source(replacement)
            await close_source(source)
            replacement = source = None
            heartbeat("FAILED_PARTIAL")
            if isinstance(error, LiquidationStressError):
                verify_directory(directory)
                return 1
            reconnects += 1
            if reconnects > MAX_RECONNECTS:
                verify_directory(directory)
                return 1
            continuity_epoch += 1
            connection_epoch += 1
            planned_handoff = None
            await asyncio.sleep(BACKOFF_SECONDS[min(reconnects - 1, len(BACKOFF_SECONDS) - 1)])

    await close_source(replacement)
    await close_source(source)
    verify_directory(directory)
    heartbeat("COMPLETED")
    return 0


def verify_status(directory: Path) -> None:
    path = directory / "operations" / "status.json"
    if not path.exists():
        return
    payload = json.loads(path.read_text())
    if payload.get("operations_contract_sha256") != sha256(CONTRACT.read_bytes()):
        raise LiquidationStressError("persistent status contract hash mismatch")
    if payload.get("authority") != AUTHORITY:
        raise LiquidationStressError("persistent status authority boundary changed")
    if payload.get("state") not in {
        "CONNECTING",
        "OBSERVING",
        "CHECKPOINTED",
        "FAILED_PARTIAL",
        "COMPLETED",
    }:
        raise LiquidationStressError("persistent status state is invalid")
    if not re.fullmatch(r"[0-9a-f]{40}", str(payload.get("run_commit"))):
        raise LiquidationStressError("persistent status commit is invalid")
    parse_utc(payload["process_started_at"])
    parse_utc(payload["heartbeat_at"])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint-windows", type=int)
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.verify_only == (args.checkpoint_windows is not None):
        parser.error("choose exactly one of --checkpoint-windows or --verify-only")
    if args.checkpoint_windows is not None and not 1 <= args.checkpoint_windows <= 8_640:
        parser.error("--checkpoint-windows must be between 1 and 8640")
    return args


def main() -> int:
    args = parse_args()
    if not CONTRACT.is_file():
        raise SystemExit("persistent observation contract is missing")
    verified = verify_directory(args.output_dir)
    verify_status(args.output_dir)
    if args.verify_only:
        print(f"verified {verified} prospective sessions and persistent status")
        return 0
    return asyncio.run(run_checkpoints(args.output_dir, args.checkpoint_windows))


if __name__ == "__main__":
    sys.exit(main())
