"""Dependency-free local server for the Trading OS evidence dashboard."""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from tios.services.dashboard_api.ai_costs import build_ai_costs
from tios.services.dashboard_api.cockpit import (
    CockpitActionError,
    build_cockpit,
    perform_cockpit_action,
)
from tios.services.dashboard_api.demo_lane import (
    DemoLaneActionError,
    build_demo_lane,
    build_demo_status_view,
    build_demo_trades_view,
    build_equity_curve,
    build_live_feed,
    build_price_history,
    build_research_findings_view,
    build_wallet,
    perform_demo_lane_action,
)
from tios.services.dashboard_api.eth_signal import EthSignalCheckError, build_eth_signal_check
from tios.services.dashboard_api.market import build_market_snapshot
from tios.services.dashboard_api.open_work import build_open_work
from tios.services.dashboard_api.operations import build_operations, trigger_data_update
from tios.services.dashboard_api.orchestrator_view import build_orchestrator_view
from tios.services.dashboard_api.search import build_search_results
from tios.services.dashboard_api.signal_pollers import poll_all_sources
from tios.services.dashboard_api.signal_reliability import build_reliability
from tios.services.dashboard_api.signals_inbox import (
    SignalIngestError,
    build_signals,
    ingest_signal,
)
from tios.services.dashboard_api.skills import build_skills
from tios.services.dashboard_api.status import (
    build_dashboard_data,
    build_stage_gate_readiness,
    build_status,
    record_workspace_decision,
)

_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,199}$")


class Handler(BaseHTTPRequestHandler):
    root = Path.cwd()
    html = ""

    def do_GET(self) -> None:  # noqa: N802
        request = urlparse(self.path)
        path = request.path
        if path == "/api/v1/dashboard":
            body = json.dumps(build_dashboard_data(self.root)).encode()
            self._send(200, "application/json", body)
        elif path == "/api/v1/status":
            self._send(200, "application/json", json.dumps(build_status(self.root)).encode())
        elif path == "/api/v1/operations":
            self._send(200, "application/json", json.dumps(build_operations(self.root)).encode())
        elif path == "/api/v1/stage-gates":
            self._send(
                200,
                "application/json",
                json.dumps(build_stage_gate_readiness(self.root)).encode(),
            )
        elif path == "/api/v1/search":
            query = parse_qs(request.query)
            try:
                payload = build_search_results(
                    self.root,
                    query.get("q", [""])[0],
                    int(query.get("limit", ["25"])[0]),
                )
            except (ValueError, TypeError) as error:
                self._send(
                    400,
                    "application/json",
                    json.dumps({"schema_version": 1, "error": str(error)}).encode(),
                )
                return
            self._send(200, "application/json", json.dumps(payload).encode())
        elif path == "/api/v1/market":
            query = parse_qs(request.query)
            try:
                payload = build_market_snapshot(
                    self.root,
                    query.get("symbol", ["BTCUSDT"])[0],
                    query.get("interval", ["5m"])[0],
                    int(query.get("limit", ["240"])[0]),
                    query.get("anchor", ["evidence"])[0],
                )
            except (ValueError, TypeError) as error:
                self._send(
                    400,
                    "application/json",
                    json.dumps({"schema_version": 1, "error": str(error)}).encode(),
                )
                return
            self._send(200, "application/json", json.dumps(payload).encode())
        elif path == "/api/v1/cockpit":
            query = parse_qs(request.query)
            try:
                payload = build_cockpit(self.root, query.get("range", ["24h"])[0])
            except (ValueError, TypeError) as error:
                self._json_error(400, str(error))
                return
            self._send(200, "application/json", json.dumps(payload).encode())
        elif path == "/api/v1/signals":
            self._send(200, "application/json", json.dumps(build_signals(self.root)).encode())
        elif path == "/api/v1/signals/reliability":
            self._send(200, "application/json", json.dumps(build_reliability(self.root)).encode())
        elif path == "/api/v1/skills":
            self._send(200, "application/json", json.dumps(build_skills(self.root)).encode())
        elif path == "/api/v1/demo-lane":
            self._send(200, "application/json", json.dumps(build_demo_lane(self.root)).encode())
        elif path == "/api/v1/demo-trades":
            body = json.dumps(build_demo_trades_view(self.root)).encode()
            self._send(200, "application/json", body)
        elif path == "/api/v1/demo-status":
            body = json.dumps(build_demo_status_view(self.root)).encode()
            self._send(200, "application/json", body)
        elif path == "/api/v1/live-feed":
            self._send(200, "application/json", json.dumps(build_live_feed(self.root)).encode())
        elif path == "/api/v1/wallet":
            self._send(200, "application/json", json.dumps(build_wallet(self.root)).encode())
        elif path == "/api/v1/price-history":
            body = json.dumps(build_price_history(self.root)).encode()
            self._send(200, "application/json", body)
        elif path == "/api/v1/equity-curve":
            self._send(200, "application/json", json.dumps(build_equity_curve(self.root)).encode())
        elif path == "/api/v1/research-findings":
            body = json.dumps(build_research_findings_view(self.root)).encode()
            self._send(200, "application/json", body)
        elif path == "/api/v1/ai-costs":
            self._send(200, "application/json", json.dumps(build_ai_costs(self.root)).encode())
        elif path == "/api/v1/open-work":
            self._send(200, "application/json", json.dumps(build_open_work(self.root)).encode())
        elif path == "/api/v1/orchestrator":
            payload = build_orchestrator_view(self.root)
            self._send(200, "application/json", json.dumps(payload).encode())
        elif path == "/api/v1/eth-signal":
            try:
                payload = build_eth_signal_check(self.root)
            except EthSignalCheckError as error:
                self._json_error(503, str(error))
                return
            self._send(200, "application/json", json.dumps(payload).encode())
        elif path in {"/", "/index.html"}:
            self._send(200, "text/html; charset=utf-8", self.html.encode())
        elif path.startswith("/api/"):
            self._send(
                410,
                "application/json",
                json.dumps(
                    {
                        "schema_version": 1,
                        "error": "legacy API removed; use /api/v1",
                    }
                ).encode(),
            )
        else:
            self._send(404, "text/plain; charset=utf-8", b"not found\n")

    def do_POST(self) -> None:  # noqa: N802
        request = urlparse(self.path)
        if request.path == "/api/v1/signals/ingest":
            try:
                payload = self._read_same_origin_json()
                record = ingest_signal(self.root, payload)
            except CockpitActionError as error:
                self._json_error(error.status_code, str(error))
                return
            except SignalIngestError as error:
                self._json_error(error.status_code, str(error))
                return
            except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as error:
                self._json_error(400, str(error))
                return
            self._send(201, "application/json", json.dumps(record).encode())
            return
        if request.path == "/api/v1/signals/poll":
            try:
                self._read_same_origin_json()
            except CockpitActionError as error:
                self._json_error(error.status_code, str(error))
                return
            try:
                result = poll_all_sources(self.root)
            except SignalIngestError as error:
                self._json_error(500, f"poller produced an invalid signal: {error}")
                return
            self._send(200, "application/json", json.dumps(result).encode())
            return
        routes = {
            "/api/v1/workspace-actions/data-update",
            "/api/v1/workspace-actions/decision",
            "/api/v1/cockpit-actions",
            "/api/v1/demo-lane-actions",
        }
        if request.path not in routes:
            self._send(404, "application/json", b'{"schema_version":1,"error":"not found"}')
            return
        try:
            payload = self._read_same_origin_json()
            key = payload.get("idempotency_key")
            if not isinstance(key, str) or not _IDEMPOTENCY_KEY.fullmatch(key):
                raise ValueError("idempotency_key must be a bounded identifier")
            if request.path == "/api/v1/workspace-actions/data-update":
                if set(payload) != {"idempotency_key"}:
                    raise ValueError("data update accepts only idempotency_key")
                body = json.dumps(trigger_data_update(self.root, key)).encode()
                self._send(202, "application/json", body)
                return
            if request.path == "/api/v1/cockpit-actions":
                result = perform_cockpit_action(self.root, payload)
                self._send(201, "application/json", json.dumps(result).encode())
                return
            if request.path == "/api/v1/demo-lane-actions":
                lane_result = perform_demo_lane_action(self.root, payload)
                self._send(201, "application/json", json.dumps(lane_result).encode())
                return
            body = json.dumps(record_workspace_decision(self.root, payload)).encode()
        except (CockpitActionError, DemoLaneActionError) as error:
            self._json_error(error.status_code, str(error))
            return
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as error:
            self._json_error(400, str(error))
            return
        self._send(201, "application/json", body)

    def _read_same_origin_json(self) -> dict[str, object]:
        media_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if media_type != "application/json":
            raise _PostGuardError(415, "Content-Type must be application/json")
        fetch_site = self.headers.get("Sec-Fetch-Site")
        if fetch_site is not None and fetch_site.lower() not in {
            "same-origin",
            "same-site",
            "none",
        }:
            raise _PostGuardError(403, "cross-origin request rejected")
        origin = self.headers.get("Origin")
        if origin is not None:
            host = self.headers.get("Host", "")
            parsed = urlparse(origin)
            request_scheme = getattr(self.server, "url_scheme", "http")
            if (
                request_scheme not in {"http", "https"}
                or parsed.scheme != request_scheme
                or not host
                or parsed.netloc.casefold() != host.casefold()
                or parsed.path not in {"", "/"}
                or parsed.params
                or parsed.query
                or parsed.fragment
            ):
                raise _PostGuardError(403, "cross-origin request rejected")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise ValueError("invalid request size") from error
        if length <= 0 or length > 4096:
            raise ValueError("invalid request size")
        payload = json.loads(self.rfile.read(length).decode())
        if not isinstance(payload, dict):
            raise ValueError("request body must be an object")
        return payload

    def _json_error(self, code: int, message: str) -> None:
        self._send(
            code,
            "application/json",
            json.dumps({"schema_version": 1, "error": message}).encode(),
        )

    def _send(self, code: int, content_type: str, body: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


class _PostGuardError(CockpitActionError):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code


def _load_dotenv(root: Path) -> None:
    """Load KEY=VALUE lines from a local .env file; real env vars always win."""
    env_path = root / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip().strip('"').strip("'")


def is_loopback_host(host: str) -> bool:
    """Accept only literal loopback addresses and localhost."""
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the local Trading OS dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if not is_loopback_host(args.host):
        parser.error("non-loopback binding requires a future explicit authenticated mode")
    _load_dotenv(Path.cwd())
    Handler.root = Path.cwd()
    Handler.html = (Path(__file__).with_name("dashboard.html")).read_text()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Trading OS dashboard: http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
