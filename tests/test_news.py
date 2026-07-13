from __future__ import annotations

import json
import os
import stat
import threading
from datetime import UTC, datetime, timedelta
from email.message import Message
from http.client import IncompleteRead
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from types import TracebackType
from urllib.error import HTTPError
from urllib.request import Request

import pytest

from tios.services.dashboard_api import audit as audit_module
from tios.services.dashboard_api import cockpit as cockpit_module
from tios.services.dashboard_api import news
from tios.services.dashboard_api.news import build_external_news

NOW = datetime(2026, 7, 12, 12, tzinfo=UTC)


class _Response:
    def __init__(
        self, body: bytes, *, status: int = 200, headers: dict[str, str] | None = None
    ) -> None:
        self.body = body
        self.status = status
        self.headers = headers or {"Content-Length": str(len(body))}

    def __enter__(self) -> _Response:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    def read(self, amount: int = -1) -> bytes:
        return self.body if amount < 0 else self.body[:amount]


class _IncompleteResponse(_Response):
    def read(self, amount: int = -1) -> bytes:
        raise IncompleteRead(b'{"Data":[')


def _payload(*articles: dict[str, object]) -> bytes:
    return json.dumps({"Data": list(articles), "Err": {}}).encode()


def _article(**changes: object) -> dict[str, object]:
    article: dict[str, object] = {
        "ID": 42,
        "GUID": "news-fixture-42",
        "PUBLISHED_ON": int(NOW.timestamp()),
        "TITLE": "Bitcoin liquidity remains available on Binance",
        "SUBTITLE": "BTC markets continued operating after scheduled maintenance.",
        "BODY": "This full article body must never be retained.",
        "KEYWORDS": "BTC, Bitcoin, Binance",
        "URL": "https://www.coindesk.com/markets/2026/07/12/fixture/",
        "SOURCE_DATA": {"NAME": "CoinDesk"},
        "CATEGORY_DATA": [{"NAME": "Markets"}],
    }
    article.update(changes)
    return article


def test_news_is_credential_gated_and_creates_no_cache_without_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("TIOS_COINDESK_API_KEY", raising=False)
    monkeypatch.setattr(news, "_open", lambda *_args, **_kwargs: pytest.fail("network call"))

    snapshot = build_external_news(tmp_path, {"BTCUSDT"}, now=NOW)

    assert snapshot["items"] == []
    assert snapshot["freshness"]["status"] == "UNAVAILABLE"
    assert "not configured" in snapshot["freshness"]["detail"]
    assert not (tmp_path / "artifacts/news").exists()


def test_provider_endpoint_is_fixed_to_coindesk_https(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(news, "API_URL", "https://attacker.example/news/v1/article/list")
    monkeypatch.setattr(news, "_open", lambda *_args, **_kwargs: pytest.fail("network call"))

    snapshot = build_external_news(tmp_path, {"BTCUSDT"}, now=NOW, api_key="server-secret")

    assert snapshot["items"] == []
    assert snapshot["freshness"]["status"] == "UNAVAILABLE"


def test_no_redirect_opener_never_forwards_api_key() -> None:
    hits: list[tuple[str, str | None]] = []

    class RedirectHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            hits.append((self.path, self.headers.get("x-api-key")))
            if self.path == "/start":
                self.send_response(302)
                self.send_header("Location", f"http://127.0.0.1:{self.server.server_port}/target")
                self.end_headers()
                return
            self.send_response(200)
            self.end_headers()

        def log_message(self, _format: str, *_args: object) -> None:
            return

    server = HTTPServer(("127.0.0.1", 0), RedirectHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    request = Request(
        f"http://127.0.0.1:{server.server_port}/start",
        headers={"x-api-key": "server-secret"},
    )
    try:
        with pytest.raises(HTTPError) as caught:
            news._no_redirect_open(request, timeout=1)
        caught.value.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert hits == [("/start", "server-secret")]


def test_relevant_metadata_is_bounded_cached_and_key_stays_in_header(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[Request] = []
    body = _payload(
        _article(),
        _article(
            ID=43,
            GUID="irrelevant-43",
            TITLE="A software company opens a new office",
            SUBTITLE="General business update.",
            KEYWORDS="software",
            URL="https://example.com/business/update",
        ),
    )

    def fake_open(request: Request, *, timeout: float) -> _Response:
        calls.append(request)
        assert timeout == 5.0
        return _Response(body)

    monkeypatch.setattr(news, "_open", fake_open)

    first = build_external_news(tmp_path, {"BTCUSDT"}, now=NOW, api_key="server-secret")
    cached = build_external_news(
        tmp_path, {"BTCUSDT"}, now=NOW + timedelta(minutes=5), api_key="server-secret"
    )

    assert len(calls) == 1
    assert calls[0].get_method() == "GET"
    assert calls[0].full_url == (
        "https://data-api.coindesk.com/news/v1/article/list?lang=EN&limit=50"
    )
    assert "server-secret" not in calls[0].full_url
    assert calls[0].get_header("X-api-key") == "server-secret"
    assert first == cached
    assert len(first["items"]) == 1
    assert first["items"][0]["kind"] == "EXTERNAL_NEWS"
    assert first["items"][0]["affected_subjects"] == [
        "BINANCE",
        "BTC",
        "EXCHANGE_AVAILABILITY",
    ]
    assert first["items"][0]["url"].startswith("https://")
    cache_text = (tmp_path / news.CACHE_PATH).read_text()
    assert "server-secret" not in cache_text
    assert "full article body" not in cache_text


def test_lone_surrogate_identity_and_retained_text_are_sanitized(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    body = _payload(
        _article(
            GUID="\ud800",
            TITLE="Bit\ud800coin remains available",
            SUBTITLE="BTC\ud800 metadata is bounded.",
            SOURCE_DATA={"NAME": "Coin\ud800Desk"},
        )
    )
    monkeypatch.setattr(news, "_open", lambda *_args, **_kwargs: _Response(body))

    snapshot = build_external_news(tmp_path, {"BTCUSDT"}, now=NOW, api_key="secret")

    assert len(snapshot["items"]) == 1
    assert snapshot["items"][0]["title"] == "Bitcoin remains available"
    assert snapshot["items"][0]["summary"] == "BTC metadata is bounded."
    assert snapshot["items"][0]["source"] == "CoinDesk"
    json.dumps(snapshot, ensure_ascii=False).encode("utf-8")
    assert "\\ud800" not in (tmp_path / news.CACHE_PATH).read_text()


def test_lone_surrogate_news_cannot_break_cockpit_serialization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    body = _payload(
        _article(
            GUID="\ud800",
            TITLE="Ethereum\ud800 research update",
            SUBTITLE="ETH metadata\ud800 remains informational.",
            SOURCE_DATA={"NAME": "Coin\ud800Desk"},
        )
    )
    internal = {"item_id": "internal-survives"}
    monkeypatch.setenv("TIOS_COINDESK_API_KEY", "server-secret")
    monkeypatch.setattr(news, "_open", lambda *_args, **_kwargs: _Response(body))
    monkeypatch.setattr(cockpit_module, "_internal_findings", lambda *_args: [internal])

    snapshot = cockpit_module.build_cockpit(tmp_path, now=NOW)

    assert snapshot["findings"][0] == internal
    assert snapshot["findings"][1]["title"] == "Ethereum research update"
    json.dumps(snapshot, ensure_ascii=False).encode("utf-8")


@pytest.mark.parametrize(
    "body,headers",
    [
        (b"not-json", None),
        (b"{}", None),
        (b"{}", {"Content-Length": str(news.MAX_RESPONSE_BYTES + 1)}),
    ],
)
def test_malformed_or_oversized_news_never_breaks_the_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    body: bytes,
    headers: dict[str, str] | None,
) -> None:
    monkeypatch.setattr(news, "_open", lambda *_args, **_kwargs: _Response(body, headers=headers))

    snapshot = build_external_news(tmp_path, {"ETHUSDT"}, now=NOW, api_key="secret")

    assert snapshot["items"] == []
    assert snapshot["freshness"]["status"] == "UNAVAILABLE"


def test_initial_fetch_failure_truthfully_reports_no_retained_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = 0

    def timed_out(*_args: object, **_kwargs: object) -> _Response:
        nonlocal calls
        calls += 1
        raise TimeoutError

    monkeypatch.setattr(news, "_open", timed_out)

    first = build_external_news(tmp_path, {"BTCUSDT"}, now=NOW, api_key="secret")
    cached = build_external_news(
        tmp_path, {"BTCUSDT"}, now=NOW + timedelta(minutes=5), api_key="secret"
    )

    assert calls == 1
    assert first == cached
    assert first["freshness"]["status"] == "UNAVAILABLE"
    assert "showing last-good" not in first["freshness"]["detail"]
    assert "no retained external metadata" in first["freshness"]["detail"]


@pytest.mark.parametrize(
    "body",
    [
        b'{"Data":' + b"[" * 2_000 + b"0" + b"]" * 2_000 + b"}",
        b'{"Data":[],"counter":' + b"9" * 10_000 + b"}",
    ],
)
def test_pathological_remote_json_is_contained(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: bytes
) -> None:
    monkeypatch.setattr(news, "_open", lambda *_args, **_kwargs: _Response(body))

    snapshot = build_external_news(tmp_path, {"BTCUSDT"}, now=NOW, api_key="secret")

    assert snapshot["items"] == []
    assert snapshot["freshness"]["status"] == "UNAVAILABLE"


def test_incomplete_http_body_is_contained_by_provider_and_cockpit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    internal = {"item_id": "internal-survives"}
    monkeypatch.setenv("TIOS_COINDESK_API_KEY", "server-secret")
    monkeypatch.setattr(news, "_open", lambda *_args, **_kwargs: _IncompleteResponse(b""))
    monkeypatch.setattr(cockpit_module, "_internal_findings", lambda *_args: [internal])

    snapshot = cockpit_module.build_cockpit(tmp_path, now=NOW)

    assert snapshot["findings"] == [internal]
    assert snapshot["freshness"][-1]["source"] == "COINDESK_DATA_NEWS"
    assert snapshot["freshness"][-1]["status"] == "UNAVAILABLE"


@pytest.mark.parametrize(
    "unsafe_url",
    [
        "http://example.com/bitcoin",
        "https://127.0.0.1/private",
        "https://user:password@example.com/bitcoin",
        "https://exa mple.com/bitcoin",
        "https://example.com/bitcoin\u202e",
        "https://example.com/bitcoin\ud800",
        "https://2130706433/bitcoin",
        "https://0177.0.0.1/bitcoin",
        "https://0x7f000001/bitcoin",
        "https://127.1/bitcoin",
        "https://127。0。0。1/bitcoin",
        "https://①②⑦.⓪.⓪.①/bitcoin",
        "https://intranet/bitcoin",
        "https://exchange.local/bitcoin",
    ],
)
def test_unsafe_links_are_discarded_without_discarding_safe_relevant_items(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, unsafe_url: str
) -> None:
    body = _payload(
        _article(GUID="unsafe", URL=unsafe_url),
        _article(GUID="safe", URL="https://example.com/bitcoin/update"),
    )
    monkeypatch.setattr(news, "_open", lambda *_args, **_kwargs: _Response(body))

    snapshot = build_external_news(tmp_path, {"BTCUSDT"}, now=NOW, api_key="secret")

    assert [item["url"] for item in snapshot["items"]] == ["https://example.com/bitcoin/update"]


def test_http_429_uses_backoff_and_preserves_last_good_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = 0

    def fake_open(request: Request, *, timeout: float) -> _Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return _Response(_payload(_article()))
        headers = Message()
        headers["Retry-After"] = "86400"
        raise HTTPError(request.full_url, 429, "rate limited", headers, None)

    monkeypatch.setattr(news, "_open", fake_open)
    first = build_external_news(tmp_path, {"BTCUSDT"}, now=NOW, api_key="secret")
    delayed = build_external_news(
        tmp_path, {"BTCUSDT"}, now=NOW + timedelta(minutes=11), api_key="secret"
    )
    within_backoff = build_external_news(
        tmp_path, {"BTCUSDT"}, now=NOW + timedelta(hours=2), api_key="secret"
    )

    assert calls == 2
    assert delayed["items"] == first["items"] == within_backoff["items"]
    assert delayed["freshness"]["status"] == "DELAYED"
    assert within_backoff["freshness"]["status"] == "STALE"


def test_retry_after_extreme_date_cannot_overflow_429_handling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_open(request: Request, *, timeout: float) -> _Response:
        headers = Message()
        headers["Retry-After"] = "Fri, 31 Dec 9999 23:59:59 -1200"
        raise HTTPError(request.full_url, 429, "rate limited", headers, None)

    monkeypatch.setattr(news, "_open", fake_open)

    snapshot = build_external_news(tmp_path, {"BTCUSDT"}, now=NOW, api_key="secret")

    assert snapshot["items"] == []
    assert snapshot["freshness"]["status"] == "UNAVAILABLE"
    record = json.loads((tmp_path / news.CACHE_PATH).read_text().splitlines()[-1])
    retry_at = datetime.fromisoformat(record["next_refresh_at"])
    assert NOW + timedelta(minutes=10) <= retry_at <= NOW + timedelta(days=1)


def test_truncated_cache_tail_is_replayed_from_last_complete_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = 0

    def fake_open(*_args: object, **_kwargs: object) -> _Response:
        nonlocal calls
        calls += 1
        return _Response(_payload(_article(GUID=f"article-{calls}", ID=calls)))

    monkeypatch.setattr(news, "_open", fake_open)
    build_external_news(tmp_path, {"BTCUSDT"}, now=NOW, api_key="secret")
    with (tmp_path / news.CACHE_PATH).open("ab") as cache:
        cache.write(b'{"partial":')

    snapshot = build_external_news(
        tmp_path, {"BTCUSDT"}, now=NOW + timedelta(minutes=11), api_key="secret"
    )

    assert calls == 2
    assert snapshot["items"][0]["item_id"] != ""
    for line in (tmp_path / news.CACHE_PATH).read_text().splitlines():
        assert isinstance(json.loads(line), dict)


def test_many_refreshes_keep_cache_bounded_and_compact_corrupt_tail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = 0

    def fake_open(*_args: object, **_kwargs: object) -> _Response:
        nonlocal calls
        calls += 1
        return _Response(_payload(_article(GUID=f"bounded-{calls}", ID=calls)))

    monkeypatch.setattr(news, "_open", fake_open)
    latest: dict[str, object] = {}
    iterations = news.MAX_CACHE_RECORDS * 3 + 5
    for index in range(iterations):
        latest = build_external_news(
            tmp_path,
            {"BTCUSDT"},
            now=NOW + timedelta(minutes=11 * index),
            api_key="secret",
        )
        cache = tmp_path / news.CACHE_PATH
        assert cache.stat().st_size <= news.MAX_CACHE_BYTES
        assert len(cache.read_bytes().splitlines()) <= news.MAX_CACHE_RECORDS

    assert calls == iterations
    cache = tmp_path / news.CACHE_PATH
    with cache.open("ab") as handle:
        handle.write(b"\xff\n")
    monkeypatch.setattr(news, "_open", lambda *_args, **_kwargs: pytest.fail("network call"))

    replayed = build_external_news(
        tmp_path,
        {"BTCUSDT"},
        now=NOW + timedelta(minutes=11 * (iterations - 1) + 5),
        api_key="secret",
    )

    assert replayed["items"] == latest["items"]
    assert cache.stat().st_size <= news.MAX_CACHE_BYTES
    assert len(cache.read_bytes().splitlines()) == 1
    cache.read_text()


def test_oversized_cache_has_bounded_replay_work_and_keeps_newest_valid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(news, "_open", lambda *_args, **_kwargs: _Response(_payload(_article())))
    first = build_external_news(tmp_path, {"BTCUSDT"}, now=NOW, api_key="secret")
    cache = tmp_path / news.CACHE_PATH
    record = cache.read_bytes()
    cache.write_bytes(record * 2_000 + b"\xff\n")
    parses = 0
    real_load = news._load_json

    def counted_load(value: bytes) -> object:
        nonlocal parses
        parses += 1
        return real_load(value)

    monkeypatch.setattr(news, "_load_json", counted_load)
    monkeypatch.setattr(news, "_open", lambda *_args, **_kwargs: pytest.fail("network call"))

    replayed = build_external_news(
        tmp_path, {"BTCUSDT"}, now=NOW + timedelta(minutes=5), api_key="secret"
    )

    assert replayed["items"] == first["items"]
    assert parses <= news.MAX_CACHE_RECORDS
    assert cache.stat().st_size <= news.MAX_CACHE_BYTES
    assert len(cache.read_bytes().splitlines()) == 1


def test_exact_tail_boundary_preserves_newest_valid_before_malformed_tail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(news, "_open", lambda *_args, **_kwargs: _Response(_payload(_article())))
    first = build_external_news(tmp_path, {"BTCUSDT"}, now=NOW, api_key="secret")
    cache = tmp_path / news.CACHE_PATH
    newest = cache.read_bytes()
    exact_size = news.MAX_CACHE_READ_BYTES + 2
    malformed_size = exact_size - 2 - len(newest)
    assert malformed_size > 0
    cache.write_bytes(b"x\n" + newest + b"{" + b"x" * (malformed_size - 1))
    assert cache.stat().st_size == 262_146 == exact_size
    parses = 0
    real_load = news._load_json

    def counted_load(value: bytes) -> object:
        nonlocal parses
        parses += 1
        return real_load(value)

    monkeypatch.setattr(news, "_load_json", counted_load)
    monkeypatch.setattr(news, "_open", lambda *_args, **_kwargs: pytest.fail("network call"))

    replayed = build_external_news(
        tmp_path, {"BTCUSDT"}, now=NOW + timedelta(minutes=5), api_key="secret"
    )

    assert replayed["items"] == first["items"]
    assert parses <= news.MAX_CACHE_RECORDS
    assert cache.stat().st_size <= news.MAX_CACHE_BYTES
    assert len(cache.read_bytes().splitlines()) == 1


def test_failed_atomic_compaction_preserves_last_good_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(news, "_open", lambda *_args, **_kwargs: _Response(_payload(_article())))
    first = build_external_news(tmp_path, {"BTCUSDT"}, now=NOW, api_key="secret")
    cache = tmp_path / news.CACHE_PATH
    with cache.open("ab") as handle:
        handle.write(b"\xff\n")
    retained = cache.read_bytes()
    real_replace = audit_module.os.replace

    def interrupted_replace(*_args: object, **_kwargs: object) -> None:
        raise OSError("simulated interruption before atomic replacement")

    monkeypatch.setattr(audit_module.os, "replace", interrupted_replace)
    interrupted = build_external_news(
        tmp_path, {"BTCUSDT"}, now=NOW + timedelta(minutes=5), api_key="secret"
    )
    monkeypatch.setattr(audit_module.os, "replace", real_replace)

    assert interrupted["items"] == []
    assert interrupted["freshness"]["status"] == "UNAVAILABLE"
    assert cache.read_bytes() == retained

    recovered = build_external_news(
        tmp_path, {"BTCUSDT"}, now=NOW + timedelta(minutes=5), api_key="secret"
    )

    assert recovered["items"] == first["items"]
    assert len(cache.read_bytes().splitlines()) == 1


@pytest.mark.parametrize("operation", ["atomic", "reader"])
def test_confined_special_file_validation_never_blocks_on_fifo(
    tmp_path: Path, operation: str
) -> None:
    fifo = tmp_path / news.CACHE_PATH
    fifo.parent.mkdir(parents=True)
    os.mkfifo(fifo)
    errors: list[BaseException] = []

    def attempt() -> None:
        try:
            if operation == "atomic":
                audit_module.confined_atomic_write(tmp_path, news.CACHE_PATH, b"safe\n")
            else:
                with audit_module.confined_audit_handle(tmp_path, news.CACHE_PATH, create=False):
                    pass
        except BaseException as error:
            errors.append(error)

    worker = threading.Thread(target=attempt, daemon=True)
    worker.start()
    worker.join(timeout=1)
    blocked = worker.is_alive()
    if blocked:
        writer = os.open(fifo, os.O_WRONLY | os.O_NONBLOCK)
        os.close(writer)
        worker.join(timeout=1)

    assert not blocked
    assert len(errors) == 1
    assert isinstance(errors[0], audit_module.AuditPathError)
    assert stat.S_ISFIFO(os.lstat(fifo).st_mode)


def test_malformed_utf8_cache_tail_preserves_last_good_cockpit_findings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(news, "_open", lambda *_args, **_kwargs: _Response(_payload(_article())))
    first = build_external_news(tmp_path, {"BTCUSDT"}, now=NOW, api_key="server-secret")
    with (tmp_path / news.CACHE_PATH).open("ab") as cache:
        cache.write(b"\xff\n")
    monkeypatch.setenv("TIOS_COINDESK_API_KEY", "server-secret")
    monkeypatch.setattr(news, "_open", lambda *_args, **_kwargs: pytest.fail("network call"))
    internal = {"item_id": "internal-first"}
    monkeypatch.setattr(cockpit_module, "_internal_findings", lambda *_args: [internal])

    snapshot = cockpit_module.build_cockpit(tmp_path, now=NOW + timedelta(minutes=5))

    assert snapshot["findings"] == [internal, *first["items"]]
    assert snapshot["freshness"][-1]["status"] == "LIVE"
    (tmp_path / news.CACHE_PATH).read_text()


@pytest.mark.parametrize(
    "bad_record",
    [
        b"[" * 2_000 + b"0" + b"]" * 2_000 + b"\n",
        b'{"counter":' + b"9" * 10_000 + b"}\n",
    ],
)
def test_pathological_cache_json_is_contained(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    bad_record: bytes,
) -> None:
    cache = tmp_path / news.CACHE_PATH
    cache.parent.mkdir(parents=True)
    cache.write_bytes(bad_record)
    monkeypatch.setattr(
        news, "_open", lambda *_args, **_kwargs: (_ for _ in ()).throw(TimeoutError())
    )

    snapshot = build_external_news(tmp_path, {"BTCUSDT"}, now=NOW, api_key="server-secret")

    assert snapshot["items"] == []
    assert snapshot["freshness"]["status"] == "UNAVAILABLE"


def test_news_cache_refuses_symlinked_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / "artifacts").mkdir()
    os.symlink(outside, tmp_path / "artifacts/news")
    monkeypatch.setattr(news, "_open", lambda *_args, **_kwargs: pytest.fail("network call"))

    snapshot = build_external_news(tmp_path, {"BTCUSDT"}, now=NOW, api_key="secret")

    assert snapshot["items"] == []
    assert snapshot["freshness"]["status"] == "UNAVAILABLE"
    assert list(outside.iterdir()) == []


def test_news_cache_refuses_symlinked_final_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    news_dir = tmp_path / "artifacts/news"
    news_dir.mkdir(parents=True)
    outside = tmp_path / "outside.jsonl"
    outside.write_text("do not replace")
    os.symlink(outside, news_dir / "coindesk.jsonl")
    monkeypatch.setattr(news, "_open", lambda *_args, **_kwargs: pytest.fail("network call"))

    snapshot = build_external_news(tmp_path, {"BTCUSDT"}, now=NOW, api_key="secret")

    assert snapshot["items"] == []
    assert snapshot["freshness"]["status"] == "UNAVAILABLE"
    assert outside.read_text() == "do not replace"


def test_cockpit_keeps_internal_findings_first_and_news_failure_isolated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    internal = {"item_id": "internal-first"}
    external = {"item_id": "external-second"}
    monkeypatch.setattr(cockpit_module, "_internal_findings", lambda *_args: [internal])
    monkeypatch.setattr(
        cockpit_module,
        "build_external_news",
        lambda *_args, **_kwargs: {
            "items": [external],
            "freshness": {
                "source": "COINDESK_DATA_NEWS",
                "status": "STALE",
                "observed_at": None,
                "detail": "fixture",
            },
        },
    )

    snapshot = cockpit_module.build_cockpit(tmp_path, now=NOW)

    assert snapshot["findings"] == [internal, external]
    assert snapshot["freshness"][-1]["source"] == "COINDESK_DATA_NEWS"
    assert snapshot["mode"] == "RESEARCH_ONLY"
    assert not (tmp_path / "artifacts/paper/paper.sqlite3").exists()


def test_env_template_documents_optional_informational_news_key() -> None:
    template = (Path(__file__).resolve().parents[1] / ".env.example").read_text()

    assert "# TIOS_COINDESK_API_KEY=" in template
    assert "Informational headlines only" in template
    assert "TIOS_COINDESK_API_KEY=server" not in template
