"""Dependency-free local server for the Trading OS evidence dashboard."""

from __future__ import annotations

import argparse
import ipaddress
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from tios.services.dashboard_api.market import build_market_snapshot
from tios.services.dashboard_api.status import (
    build_dashboard_data,
    build_status,
    record_workspace_decision,
)


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
        if request.path != "/api/v1/workspace-actions/decision":
            self._send(404, "application/json", b'{"schema_version":1,"error":"not found"}')
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 4096:
                raise ValueError("invalid request size")
            payload = json.loads(self.rfile.read(length).decode())
            if not isinstance(payload, dict):
                raise ValueError("request body must be an object")
            body = json.dumps(record_workspace_decision(self.root, payload)).encode()
        except (ValueError, json.JSONDecodeError) as error:
            self._send(
                400,
                "application/json",
                json.dumps({"schema_version": 1, "error": str(error)}).encode(),
            )
            return
        self._send(201, "application/json", body)

    def _send(self, code: int, content_type: str, body: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


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
