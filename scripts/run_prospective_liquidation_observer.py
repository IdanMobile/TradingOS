#!/usr/bin/env python3
"""Capture and verify bounded public BTC liquidation-snapshot sessions."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from websockets.asyncio.client import connect

from tios.strategy.liquidation_stress import (
    LiquidationSnapshot,
    LiquidationStressError,
    LiquidationStressState,
    LiquidationWindow,
    aggregate_window,
    classify_window,
    complete_window_starts,
    consecutive_baseline,
    parse_force_order_message,
    window_start,
)

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "research/PROSPECTIVE_BTC_LIQUIDATION_STRESS_SIGNAL_V1.yaml"
PERSISTENT_SPEC = ROOT / "research/PROSPECTIVE_BTC_LIQUIDATION_PERSISTENT_OBSERVATION_V1.yaml"
DEFAULT_OUTPUT = ROOT / "artifacts/prospective/BTC-LIQUIDATION-STRESS-V1"
EXCHANGE_INFO_URL = "https://dapi.binance.com/dapi/v1/exchangeInfo"
WEBSOCKET_URL = "wss://dstream.binance.com/ws/btcusd_perp@forceOrder"
EXPECTED_SYMBOL = "BTCUSD_PERP"
EXPECTED_PAIR = "BTCUSD"
AUTHORITY = {
    "execution_authority": "NONE",
    "venue_connection": "NONE",
    "market_data_transport": "PUBLIC_READ_ONLY",
    "paper_orders": "DISABLED",
    "live_orders": "DISABLED",
    "credentials_used": False,
}
KNOWN_TOP_LEVEL_ST_DEFECT_COMMIT = "8c5ee6035439f884ea3f282616939fd4cd795939"


@dataclass(frozen=True, slots=True)
class CaptureResult:
    events: list[dict[str, str]]
    status: str
    coverage_started_at: datetime
    coverage_ended_at: datetime
    error_type: str | None = None
    error_message: str | None = None
    rejected_event: dict[str, str] | None = None


def utc_now() -> datetime:
    return datetime.now(UTC)


def canonical_bytes(payload: object) -> bytes:
    return (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_utc(value: object) -> datetime:
    if not isinstance(value, str):
        raise LiquidationStressError("timestamp must be an ISO UTC string")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise LiquidationStressError("timestamp must be UTC-aware")
    return parsed


def fetch_exchange_info() -> tuple[bytes, Decimal]:
    request = urllib.request.Request(
        EXCHANGE_INFO_URL,
        headers={"Accept": "application/json", "User-Agent": "TradingOS-Prospective-Observer/2"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310 - fixed HTTPS URL
        body = response.read()
    payload = json.loads(body)
    matches = [item for item in payload["symbols"] if item.get("symbol") == EXPECTED_SYMBOL]
    if len(matches) != 1:
        raise LiquidationStressError("exchange info must contain exactly one BTCUSD_PERP")
    symbol = matches[0]
    if (
        symbol.get("pair") != EXPECTED_PAIR
        or symbol.get("contractType") != "PERPETUAL"
        or symbol.get("contractStatus") != "TRADING"
    ):
        raise LiquidationStressError("BTCUSD_PERP exchange identity is not active and exact")
    contract_size = Decimal(str(symbol["contractSize"]))
    if contract_size <= 0 or not contract_size.is_finite():
        raise LiquidationStressError("BTCUSD_PERP contract size is invalid")
    return body, contract_size


async def capture(
    *,
    duration_seconds: int | None,
    requested_complete_windows: int | None,
    contract_size: Decimal,
) -> CaptureResult:
    events: list[dict[str, str]] = []
    status = "COMPLETE"
    coverage_started_at = coverage_ended_at = utc_now()
    error_type = error_message = None
    rejected_event = None
    try:
        async with connect(
            WEBSOCKET_URL,
            open_timeout=15,
            close_timeout=5,
            ping_interval=20,
            max_size=1_000_000,
        ) as websocket:
            coverage_started_at = utc_now()
            if requested_complete_windows is None:
                assert duration_seconds is not None
                deadline = time.monotonic() + duration_seconds
            else:
                first = window_start(coverage_started_at) + timedelta(minutes=5)
                target = first + timedelta(minutes=5 * requested_complete_windows)
                deadline = time.monotonic() + (target - coverage_started_at).total_seconds()
            while (remaining := deadline - time.monotonic()) > 0:
                try:
                    async with asyncio.timeout(remaining):
                        message = await websocket.recv()
                except TimeoutError:
                    break
                if not isinstance(message, str):
                    raise LiquidationStressError("binary websocket message is not accepted")
                received_at = utc_now()
                try:
                    parse_force_order_message(
                        message,
                        received_at=received_at,
                        expected_symbol=EXPECTED_SYMBOL,
                        expected_pair=EXPECTED_PAIR,
                        contract_size_usd=contract_size,
                    )
                except Exception:
                    rejected_event = {
                        "raw_message": message,
                        "received_at": received_at.isoformat(),
                    }
                    raise
                events.append({"raw_message": message, "received_at": received_at.isoformat()})
            coverage_ended_at = utc_now()
    except Exception as error:
        error_type = type(error).__name__
        error_message = str(error)
        status = f"FAILED_{error_type}"
        coverage_ended_at = utc_now()
    return CaptureResult(
        events,
        status,
        coverage_started_at,
        coverage_ended_at,
        error_type,
        error_message,
        rejected_event,
    )


def write_content_addressed(directory: Path, prefix: str, payload: object) -> Path:
    return write_bytes_content_addressed(directory, prefix, canonical_bytes(payload))


def write_bytes_content_addressed(directory: Path, prefix: str, data: bytes) -> Path:
    digest = sha256(data)
    destination = directory / f"{prefix}_{digest}.json"
    directory.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if destination.read_bytes() != data:
            raise LiquidationStressError("content-addressed artifact collision")
        return destination
    fd, temporary = tempfile.mkstemp(prefix=f".{prefix}-", dir=directory)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return destination


def parse_events(
    events: list[dict[str, str]], *, contract_size: Decimal
) -> tuple[LiquidationSnapshot, ...]:
    return tuple(
        parse_force_order_message(
            event["raw_message"],
            received_at=parse_utc(event["received_at"]),
            expected_symbol=EXPECTED_SYMBOL,
            expected_pair=EXPECTED_PAIR,
            contract_size_usd=contract_size,
        )
        for event in events
    )


def serialize_window(window: LiquidationWindow, state: LiquidationStressState) -> dict[str, Any]:
    return {
        "start": window.start.isoformat(),
        "complete": window.complete,
        "event_count": window.event_count,
        "gross_notional_usd": str(window.gross_notional_usd),
        "buy_notional_usd": str(window.buy_notional_usd),
        "sell_notional_usd": str(window.sell_notional_usd),
        "sell_share": str(window.sell_share),
        "state": state.value,
    }


def assemble_complete_windows(
    *,
    events: list[dict[str, str]],
    contract_size: Decimal,
    source_status: str,
    coverage_started_at: datetime,
    coverage_ended_at: datetime,
    prior_windows: tuple[LiquidationWindow, ...],
) -> tuple[tuple[LiquidationWindow, LiquidationStressState], ...]:
    if source_status != "COMPLETE":
        return ()
    snapshots = parse_events(events, contract_size=contract_size)
    history = list(prior_windows)
    assembled: list[tuple[LiquidationWindow, LiquidationStressState]] = []
    for start in complete_window_starts(coverage_started_at, coverage_ended_at):
        relevant = tuple(item for item in snapshots if window_start(item.event_time) == start)
        window = aggregate_window(relevant, start=start, complete=True)
        baseline = consecutive_baseline(tuple(history), current_start=start)
        state = classify_window(window, prior_complete_gross_notional=baseline)
        history.append(window)
        assembled.append((window, state))
    return tuple(assembled)


def build_session(
    *,
    started_at: datetime,
    ended_at: datetime,
    requested_duration_seconds: int | None,
    requested_complete_windows: int | None,
    capture_result: CaptureResult,
    exchange_info_hash: str,
    contract_size: Decimal,
    run_commit: str,
    prior_windows: tuple[LiquidationWindow, ...],
) -> dict[str, Any]:
    spec_hash = sha256(SPEC.read_bytes())
    complete = assemble_complete_windows(
        events=capture_result.events,
        contract_size=contract_size,
        source_status=capture_result.status,
        coverage_started_at=capture_result.coverage_started_at,
        coverage_ended_at=capture_result.coverage_ended_at,
        prior_windows=prior_windows,
    )
    if complete:
        latest_window, latest_state = complete[-1]
        observed_start = latest_window.start
        window_complete = True
    else:
        latest_state = LiquidationStressState.SOURCE_WINDOW_INCOMPLETE
        observed_start = window_start(capture_result.coverage_started_at)
        window_complete = False
    signal_digest = sha256(f"{spec_hash}|{started_at.isoformat()}|{latest_state.value}".encode())[
        :24
    ]
    return {
        "schema_version": 4,
        "signal_spec_id": "PROSPECTIVE-BTC-LIQUIDATION-STRESS-V1",
        "signal_spec_sha256": spec_hash,
        "run_commit": run_commit,
        "started_at": started_at.isoformat(),
        "ended_at": ended_at.isoformat(),
        "requested_duration_seconds": requested_duration_seconds,
        "requested_complete_windows": requested_complete_windows,
        "source": {
            "exchange_info_url": EXCHANGE_INFO_URL,
            "websocket_url": WEBSOCKET_URL,
            "authentication": "NONE",
            "status": capture_result.status,
            "coverage_started_at": capture_result.coverage_started_at.isoformat(),
            "coverage_ended_at": capture_result.coverage_ended_at.isoformat(),
            "exchange_info_sha256": exchange_info_hash,
            "symbol": EXPECTED_SYMBOL,
            "pair": EXPECTED_PAIR,
            "contract_size_usd": str(contract_size),
            "publication_semantics": "LATEST_ONE_PER_SYMBOL_PER_1000MS_SNAPSHOT",
            "complete_liquidation_tape": False,
        },
        "raw_events": capture_result.events,
        "source_failure": (
            None
            if capture_result.status == "COMPLETE"
            else {
                "error_type": capture_result.error_type,
                "error_message": capture_result.error_message,
                "rejected_event": capture_result.rejected_event,
            }
        ),
        "observation": {
            "event_count": len(capture_result.events),
            "window_start": observed_start.isoformat(),
            "window_complete": window_complete,
            "state": latest_state.value,
            "complete_windows": [serialize_window(window, state) for window, state in complete],
        },
        "signal": {
            "signal_id": f"SIG-{signal_digest}",
            "side": "FLAT",
            "rationale_code": f"PROSPECTIVE_{latest_state.value}",
            "metric_eligible": False,
            "scorecard_eligible": False,
            "promotion_eligible": False,
        },
        "risk_decision": {
            "decision": "BLOCK",
            "reason": f"NOT_PROMOTION_ELIGIBLE_AND_{latest_state.value}",
            "independent": True,
        },
        "authority": AUTHORITY,
    }


def session_history(directory: Path) -> tuple[LiquidationWindow, ...]:
    history: list[LiquidationWindow] = []
    for path in sorted(directory.glob("session_*.json")):
        payload = json.loads(path.read_text())
        rows = payload.get("observation", {}).get("complete_windows", [])
        for row in rows:
            history.append(
                LiquidationWindow(
                    start=parse_utc(row["start"]),
                    complete=row["complete"] is True,
                    event_count=int(row["event_count"]),
                    gross_notional_usd=Decimal(row["gross_notional_usd"]),
                    buy_notional_usd=Decimal(row["buy_notional_usd"]),
                    sell_notional_usd=Decimal(row["sell_notional_usd"]),
                )
            )
    ordered = sorted(history, key=lambda item: item.start)
    if len({item.start for item in ordered}) != len(ordered):
        raise LiquidationStressError("prospective complete windows overlap")
    return tuple(ordered)


def verify_directory(directory: Path) -> int:
    if not directory.exists():
        return 0
    spec_hash = sha256(SPEC.read_bytes())
    history: list[LiquidationWindow] = []
    sessions = sorted(
        directory.glob("session_*.json"),
        key=lambda path: parse_utc(json.loads(path.read_text())["started_at"]),
    )
    for path in sessions:
        expected_hash = path.stem.removeprefix("session_")
        if expected_hash != sha256(path.read_bytes()):
            raise LiquidationStressError(f"session hash mismatch: {path.name}")
        payload = json.loads(path.read_text())
        schema_version = payload.get("schema_version")
        if schema_version not in {1, 2, 3, 4, 5}:
            raise LiquidationStressError("unsupported prospective session schema")
        if payload.get("signal_spec_sha256") != spec_hash:
            raise LiquidationStressError("prospective session spec hash mismatch")
        if not re.fullmatch(r"[0-9a-f]{40}", str(payload.get("run_commit"))):
            raise LiquidationStressError("prospective session commit is invalid")
        source = payload["source"]
        if (
            source.get("exchange_info_url") != EXCHANGE_INFO_URL
            or source.get("websocket_url") != WEBSOCKET_URL
            or source.get("authentication") != "NONE"
            or source.get("symbol") != EXPECTED_SYMBOL
            or source.get("pair") != EXPECTED_PAIR
            or source.get("complete_liquidation_tape") is not False
        ):
            raise LiquidationStressError("prospective session source contract changed")
        if schema_version == 5:
            metadata = payload.get("persistent_observation")
            if not isinstance(metadata, dict):
                raise LiquidationStressError("persistent checkpoint metadata is missing")
            if metadata.get("operations_contract_sha256") != sha256(PERSISTENT_SPEC.read_bytes()):
                raise LiquidationStressError("persistent checkpoint contract hash mismatch")
            if not re.fullmatch(r"[0-9a-f]{24}", str(metadata.get("run_id"))):
                raise LiquidationStressError("persistent checkpoint run identity is invalid")
            if any(
                not isinstance(metadata.get(key), int) or metadata[key] < 1
                for key in ("checkpoint_index", "connection_epoch", "continuity_epoch")
            ):
                raise LiquidationStressError("persistent checkpoint counters are invalid")
            parse_utc(metadata["connection_opened_at"])
            expected_checkpoint_status = (
                "FINALIZED" if source["status"] == "COMPLETE" else "FAILED_PARTIAL"
            )
            if metadata.get("checkpoint_status") != expected_checkpoint_status:
                raise LiquidationStressError("persistent checkpoint status mismatch")
            handoff = metadata.get("planned_handoff")
            if handoff is not None:
                if (
                    not isinstance(handoff, dict)
                    or not isinstance(handoff.get("from_connection_epoch"), int)
                    or handoff["from_connection_epoch"] >= metadata["connection_epoch"]
                ):
                    raise LiquidationStressError("persistent handoff identity is invalid")
                overlap = parse_utc(handoff["overlap_started_at"])
                boundary = parse_utc(handoff["handoff_boundary"])
                if overlap > boundary or boundary != parse_utc(payload["started_at"]):
                    raise LiquidationStressError("persistent handoff coverage is invalid")
        if schema_version in {3, 4, 5}:
            failure = payload.get("source_failure")
            if source["status"] == "COMPLETE":
                if failure is not None:
                    raise LiquidationStressError("complete source cannot retain a failure")
            else:
                if not isinstance(failure, dict):
                    raise LiquidationStressError("failed source must retain failure evidence")
                error_type = failure.get("error_type")
                error_message = failure.get("error_message")
                if source["status"] != f"FAILED_{error_type}" or not isinstance(error_message, str):
                    raise LiquidationStressError("source failure identity mismatch")
                rejected = failure.get("rejected_event")
                if rejected is not None:
                    try:
                        parse_force_order_message(
                            rejected["raw_message"],
                            received_at=parse_utc(rejected["received_at"]),
                            expected_symbol=EXPECTED_SYMBOL,
                            expected_pair=EXPECTED_PAIR,
                            contract_size_usd=Decimal(source["contract_size_usd"]),
                        )
                    except Exception as error:
                        if type(error).__name__ != error_type or str(error) != error_message:
                            raise LiquidationStressError(
                                "rejected source event failure mismatch"
                            ) from error
                    else:
                        legacy_st_defect = False
                        if (
                            schema_version == 3
                            and payload["run_commit"] == KNOWN_TOP_LEVEL_ST_DEFECT_COMMIT
                            and error_type == "LiquidationStressError"
                            and error_message == "invalid force-order snapshot schema"
                        ):
                            raw_payload = json.loads(rejected["raw_message"])
                            legacy_st_defect = (
                                "st" not in raw_payload
                                and isinstance(raw_payload.get("o"), dict)
                                and "st" in raw_payload["o"]
                            )
                        if not legacy_st_defect:
                            raise LiquidationStressError("rejected source event is valid")
        raw_hash = source["exchange_info_sha256"]
        raw_path = directory / "raw" / f"exchange_info_{raw_hash}.json"
        if not raw_path.is_file() or sha256(raw_path.read_bytes()) != raw_hash:
            raise LiquidationStressError("exchange-info raw hash mismatch")
        contract_size = Decimal(source["contract_size_usd"])
        events = payload["raw_events"]
        if payload["observation"]["event_count"] != len(events):
            raise LiquidationStressError("prospective event count mismatch")
        coverage_start = parse_utc(source.get("coverage_started_at", payload["started_at"]))
        coverage_end = parse_utc(source.get("coverage_ended_at", payload["ended_at"]))
        expected = assemble_complete_windows(
            events=events,
            contract_size=contract_size,
            source_status=source["status"],
            coverage_started_at=coverage_start,
            coverage_ended_at=coverage_end,
            prior_windows=tuple(history),
        )
        recorded = payload["observation"].get("complete_windows", [])
        if recorded != [serialize_window(window, state) for window, state in expected]:
            raise LiquidationStressError("prospective complete-window reconstruction mismatch")
        for window, _ in expected:
            if any(item.start == window.start for item in history):
                raise LiquidationStressError("prospective complete windows overlap")
            history.append(window)
        state = expected[-1][1] if expected else LiquidationStressState.SOURCE_WINDOW_INCOMPLETE
        started_at = parse_utc(payload["started_at"])
        signal_digest = sha256(f"{spec_hash}|{started_at.isoformat()}|{state.value}".encode())[:24]
        signal = payload["signal"]
        if signal != {
            "signal_id": f"SIG-{signal_digest}",
            "side": "FLAT",
            "rationale_code": f"PROSPECTIVE_{state.value}",
            "metric_eligible": False,
            "scorecard_eligible": False,
            "promotion_eligible": False,
        }:
            raise LiquidationStressError("prospective signal reconstruction mismatch")
        if payload["risk_decision"] != {
            "decision": "BLOCK",
            "reason": f"NOT_PROMOTION_ELIGIBLE_AND_{state.value}",
            "independent": True,
        }:
            raise LiquidationStressError("prospective risk decision mismatch")
        if payload["authority"] != AUTHORITY:
            raise LiquidationStressError("prospective authority boundary changed")
    return len(sessions)


def run_commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--duration-seconds", type=int)
    mode.add_argument("--complete-windows", type=int)
    mode.add_argument("--verify-only", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.duration_seconds is None and args.complete_windows is None and not args.verify_only:
        args.duration_seconds = 30
    if args.duration_seconds is not None and not 1 <= args.duration_seconds <= 3600:
        parser.error("--duration-seconds must be between 1 and 3600")
    if args.complete_windows is not None and not 1 <= args.complete_windows <= 12:
        parser.error("--complete-windows must be between 1 and 12")
    return args


def main() -> int:
    args = parse_args()
    if not SPEC.is_file():
        raise SystemExit("prospective signal spec is missing")
    verified = verify_directory(args.output_dir)
    if args.verify_only:
        print(f"verified {verified} prospective sessions")
        return 0
    prior_windows = session_history(args.output_dir)
    started_at = utc_now()
    exchange_info, contract_size = fetch_exchange_info()
    exchange_info_hash = sha256(exchange_info)
    write_bytes_content_addressed(args.output_dir / "raw", "exchange_info", exchange_info)
    result = asyncio.run(
        capture(
            duration_seconds=args.duration_seconds,
            requested_complete_windows=args.complete_windows,
            contract_size=contract_size,
        )
    )
    ended_at = utc_now()
    session = build_session(
        started_at=started_at,
        ended_at=ended_at,
        requested_duration_seconds=args.duration_seconds,
        requested_complete_windows=args.complete_windows,
        capture_result=result,
        exchange_info_hash=exchange_info_hash,
        contract_size=contract_size,
        run_commit=run_commit(),
        prior_windows=prior_windows,
    )
    path = write_content_addressed(args.output_dir, "session", session)
    print(path)
    verify_directory(args.output_dir)
    return 0 if result.status == "COMPLETE" else 1


if __name__ == "__main__":
    sys.exit(main())
