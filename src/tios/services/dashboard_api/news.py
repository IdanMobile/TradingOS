"""Optional, relevant-only CoinDesk metadata for the local cockpit."""

from __future__ import annotations

import fcntl
import hashlib
import io
import ipaddress
import json
import math
import os
import re
import socket
import unicodedata
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.message import Message
from email.utils import parsedate_to_datetime
from http.client import HTTPException, HTTPResponse, IncompleteRead
from pathlib import Path
from typing import Any, TextIO, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from tios.services.dashboard_api.audit import (
    AuditPathError,
    confined_atomic_write,
    confined_audit_handle,
)

API_URL = "https://data-api.coindesk.com/news/v1/article/list"
CACHE_PATH = Path("artifacts/news/coindesk.jsonl")
LOCK_PATH = Path("artifacts/news/coindesk.lock")
REFRESH_INTERVAL = timedelta(minutes=10)
MAX_RESPONSE_BYTES = 512 * 1024
MAX_CACHE_LINE_BYTES = 128 * 1024
MAX_CACHE_BYTES = 256 * 1024
MAX_CACHE_RECORDS = 32
MAX_CACHE_READ_BYTES = MAX_CACHE_BYTES
MAX_ITEMS = 20
TIMEOUT_SECONDS = 5.0
USER_AGENT = "TradingOS-Paper-Cockpit/1.0"
MAX_JSON_DEPTH = 8
MAX_JSON_NODES = 10_000


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(
        self,
        req: Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        return None


_NO_REDIRECT_OPENER = build_opener(_NoRedirectHandler)


def _no_redirect_open(request: Request, *, timeout: float) -> HTTPResponse:
    return cast(HTTPResponse, _NO_REDIRECT_OPENER.open(request, timeout=timeout))


_open: Callable[..., HTTPResponse] = _no_redirect_open
_SPACE = re.compile(r"\s+")
_THEMES = {
    "SECURITY": re.compile(
        r"\b(hack(?:ed|ing)?|exploit(?:ed)?|breach|vulnerabilit(?:y|ies)|"
        r"cyberattack|compromis(?:e|ed)|stolen|security incident)\b",
        re.IGNORECASE,
    ),
    "REGULATION": re.compile(
        r"\b(regulat(?:or|ion|ory)|legislation|lawmakers?|sec|cftc|"
        r"enforcement action|crypto ban|license revok(?:ed|ation))\b",
        re.IGNORECASE,
    ),
    "EXCHANGE_AVAILABILITY": re.compile(
        r"\b(outage|downtime|unavailable|withdr(?:aw(?:als?)?) (?:paused|suspended)|"
        r"trading (?:paused|suspended)|maintenance|delist(?:ed|ing)|insolvenc(?:y|ies))\b",
        re.IGNORECASE,
    ),
}


class NewsProviderError(ValueError):
    """External news cannot be safely fetched, parsed, or retained."""


def _iso(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise NewsProviderError("news timestamp must include a timezone")
    try:
        return value.astimezone(UTC).isoformat()
    except (OverflowError, ValueError) as error:
        raise NewsProviderError("news timestamp is outside the supported range") from error


def _text(value: object, *, maximum: int, required: bool = False) -> str:
    if not isinstance(value, str):
        if required:
            raise NewsProviderError("required news text is absent")
        return ""
    cleaned = _SPACE.sub(
        " ",
        "".join(
            character for character in value if not unicodedata.category(character).startswith("C")
        ),
    ).strip()
    if required and not cleaned:
        raise NewsProviderError("required news text is empty")
    return cleaned[:maximum]


def _safe_https_url(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 2048
        or value != value.strip()
        or any(
            character.isspace() or unicodedata.category(character).startswith("C")
            for character in value
        )
    ):
        raise NewsProviderError("news link is malformed")
    url = value
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as error:
        raise NewsProviderError("news link is malformed") from error
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 443}
    ):
        raise NewsProviderError("news link must be a public HTTPS URL")
    host = parsed.hostname.casefold()
    if host == "localhost" or host.endswith(".localhost"):
        raise NewsProviderError("news link must be a public HTTPS URL")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        try:
            ascii_host = host.encode("idna").decode("ascii")
        except UnicodeError as error:
            raise NewsProviderError("news link must be a public HTTPS URL") from error
        if "." not in ascii_host or ascii_host.endswith(
            (".home", ".internal", ".lan", ".local", ".localdomain", ".localhost")
        ):
            raise NewsProviderError("news link must be a public HTTPS URL") from None
        try:
            ipaddress.ip_address(ascii_host)
        except ValueError:
            pass
        else:
            raise NewsProviderError("news link must be a public HTTPS URL") from None
        try:
            socket.inet_aton(ascii_host)
        except OSError:
            pass
        else:
            raise NewsProviderError("news link must be a public HTTPS URL") from None
        labels = ascii_host.split(".")
        if len(ascii_host) > 253 or any(
            not label
            or len(label) > 63
            or label.startswith("-")
            or label.endswith("-")
            or re.fullmatch(r"[a-z0-9-]+", label) is None
            for label in labels
        ):
            raise NewsProviderError("news link must be a public HTTPS URL") from None
    else:
        raise NewsProviderError("news link must be a public HTTPS URL")
    return url


def _published(value: object) -> datetime:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise NewsProviderError("news publication time is invalid")
    try:
        return datetime.fromtimestamp(value, tz=UTC)
    except (OverflowError, OSError, ValueError) as error:
        raise NewsProviderError("news publication time is invalid") from error


def _json_int(value: str) -> int:
    if len(value.removeprefix("-")) > 19:
        raise ValueError("JSON integer is too large")
    parsed = int(value)
    if not -(2**63) <= parsed <= 2**63 - 1:
        raise ValueError("JSON integer is too large")
    return parsed


def _json_float(value: str) -> float:
    if len(value) > 100:
        raise ValueError("JSON number is too large")
    parsed = float(value)
    if not math.isfinite(parsed) or abs(parsed) > 1e100:
        raise ValueError("JSON number is invalid")
    return parsed


def _json_constant(_value: str) -> None:
    raise ValueError("JSON constant is invalid")


def _validate_json_tree(value: object) -> None:
    nodes = 0
    pending: list[tuple[object, int]] = [(value, 0)]
    while pending:
        item, depth = pending.pop()
        nodes += 1
        if nodes > MAX_JSON_NODES or depth > MAX_JSON_DEPTH:
            raise NewsProviderError("JSON structure exceeds its safety limit")
        if item is None or isinstance(item, bool):
            continue
        if isinstance(item, str):
            if len(item) > MAX_RESPONSE_BYTES:
                raise NewsProviderError("JSON string exceeds its safety limit")
            continue
        if isinstance(item, int):
            if not -(2**63) <= item <= 2**63 - 1:
                raise NewsProviderError("JSON integer exceeds its safety limit")
            continue
        if isinstance(item, float):
            if not math.isfinite(item) or abs(item) > 1e100:
                raise NewsProviderError("JSON number exceeds its safety limit")
            continue
        if isinstance(item, list):
            if len(item) > 200:
                raise NewsProviderError("JSON list exceeds its safety limit")
            pending.extend((child, depth + 1) for child in item)
            continue
        if isinstance(item, dict):
            if len(item) > 200 or any(not isinstance(key, str) or len(key) > 200 for key in item):
                raise NewsProviderError("JSON object exceeds its safety limit")
            pending.extend((child, depth + 1) for child in item.values())
            continue
        raise NewsProviderError("JSON value has an unsupported type")


def _load_json(value: bytes) -> object:
    try:
        decoded = json.loads(
            value.decode("utf-8"),
            parse_int=_json_int,
            parse_float=_json_float,
            parse_constant=_json_constant,
        )
    except (UnicodeDecodeError, ValueError, RecursionError) as error:
        raise NewsProviderError("JSON payload is malformed") from error
    _validate_json_tree(decoded)
    return decoded


def _subject_tokens(subjects: set[str]) -> set[str]:
    retained = {"BTC", "ETH", "BINANCE"}
    for subject in subjects:
        token = subject.strip().upper()
        if re.fullmatch(r"[A-Z0-9]{2,20}", token):
            retained.add(token)
            if token.endswith("USDT") and len(token) > 4:
                retained.add(token[:-4])
    return retained


def _matches(haystack: str, subjects: set[str]) -> tuple[list[str], str] | None:
    affected: set[str] = set()
    reasons: list[str] = []
    patterns = {
        "BTC": r"\b(?:BTC|BITCOIN|BTCUSDT)\b",
        "ETH": r"\b(?:ETH|ETHEREUM|ETHER|ETHUSDT)\b",
        "BINANCE": r"\bBINANCE\b",
    }
    for subject in sorted(_subject_tokens(subjects)):
        subject_pattern = patterns.get(subject, rf"\b{re.escape(subject)}\b")
        if re.search(subject_pattern, haystack, re.IGNORECASE):
            affected.add(subject)
            reasons.append(f"matched {subject}")
    for theme, theme_pattern in _THEMES.items():
        if theme_pattern.search(haystack):
            affected.add(theme)
            reasons.append(theme.lower().replace("_", " "))
    if not affected:
        return None
    return sorted(affected), "; ".join(reasons)


def _source(article: Mapping[str, object]) -> str:
    source_data = article.get("SOURCE_DATA")
    if isinstance(source_data, Mapping):
        for field in ("NAME", "SOURCE_KEY"):
            source = _text(source_data.get(field), maximum=120)
            if source:
                return source
    return "CoinDesk Data API"


def _article_identity(article: Mapping[str, object], published: datetime, url: str) -> str:
    guid = _text(article.get("GUID"), maximum=512)
    if guid:
        return f"guid:{guid}"
    article_id = article.get("ID")
    if isinstance(article_id, int) and not isinstance(article_id, bool):
        return f"id:{article_id}"
    text_id = _text(article_id, maximum=128)
    if text_id:
        return f"id:{text_id}"
    return f"url:{published.timestamp()}:{url}"


def _article(article: object, subjects: set[str]) -> dict[str, Any] | None:
    if not isinstance(article, Mapping):
        raise NewsProviderError("news article is not an object")
    title = _text(article.get("TITLE"), maximum=300, required=True)
    summary = _text(article.get("SUBTITLE"), maximum=500)
    keywords = _text(article.get("KEYWORDS"), maximum=1000)
    categories = article.get("CATEGORY_DATA")
    category_names: list[str] = []
    if isinstance(categories, list) and len(categories) <= 100:
        for category in categories:
            if isinstance(category, Mapping):
                name = _text(category.get("NAME"), maximum=100)
                if name:
                    category_names.append(name)
    source = _source(article)
    match = _matches(" ".join((title, summary, keywords, source, *category_names)), subjects)
    if match is None:
        return None
    affected, reason = match
    published = _published(article.get("PUBLISHED_ON"))
    url = _safe_https_url(article.get("URL"))
    identity = _article_identity(article, published, url)
    return {
        "item_id": f"coindesk-{hashlib.sha256(identity.encode()).hexdigest()[:20]}",
        "kind": "EXTERNAL_NEWS",
        "title": title,
        "summary": summary,
        "source": source,
        "published_at": _iso(published),
        "affected_subjects": affected,
        "match_reason": reason,
        "url": url,
    }


def _read_bounded(response: HTTPResponse) -> bytes:
    content_length = response.headers.get("Content-Length")
    if content_length is not None:
        try:
            announced = int(content_length)
        except ValueError as error:
            raise NewsProviderError("news response length is invalid") from error
        if announced < 0 or announced > MAX_RESPONSE_BYTES:
            raise NewsProviderError("news response is too large")
    try:
        payload = response.read(MAX_RESPONSE_BYTES + 1)
    except (HTTPException, IncompleteRead) as error:
        raise NewsProviderError("news response was truncated") from error
    if len(payload) > MAX_RESPONSE_BYTES:
        raise NewsProviderError("news response is too large")
    return payload


def _fetch(api_key: str, subjects: set[str]) -> list[dict[str, Any]]:
    try:
        endpoint = urlsplit(API_URL)
        endpoint_port = endpoint.port
    except ValueError as error:
        raise NewsProviderError("news provider endpoint is invalid") from error
    if (
        endpoint.scheme != "https"
        or endpoint.hostname != "data-api.coindesk.com"
        or endpoint_port not in {None, 443}
        or endpoint.path != "/news/v1/article/list"
        or endpoint.username is not None
        or endpoint.password is not None
        or endpoint.query
        or endpoint.fragment
    ):
        raise NewsProviderError("news provider endpoint is invalid")
    url = f"{API_URL}?{urlencode({'lang': 'EN', 'limit': 50})}"
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
            "x-api-key": api_key,
        },
        method="GET",
    )
    with _open(request, timeout=TIMEOUT_SECONDS) as response:
        if response.status != 200:
            raise NewsProviderError("news service returned a non-success status")
        decoded = _load_json(_read_bounded(response))
    if not isinstance(decoded, dict) or not isinstance(decoded.get("Data"), list):
        raise NewsProviderError("news response is malformed")
    articles = decoded["Data"]
    if len(articles) > 100:
        raise NewsProviderError("news response has too many articles")
    items: list[dict[str, Any]] = []
    for raw in articles:
        try:
            item = _article(raw, subjects)
        except NewsProviderError:
            continue
        if item is not None:
            items.append(item)
    items.sort(key=lambda item: str(item["published_at"]), reverse=True)
    unique: dict[str, dict[str, Any]] = {}
    for item in items:
        unique.setdefault(str(item["item_id"]), item)
    return list(unique.values())[:MAX_ITEMS]


def _retry_after(headers: Mapping[str, str] | Message[str, str] | None, now: datetime) -> datetime:
    ceiling = datetime.max.replace(tzinfo=UTC)

    def add(delta: timedelta) -> datetime:
        try:
            return now + delta
        except OverflowError:
            return ceiling

    minimum = add(REFRESH_INTERVAL)
    maximum = add(timedelta(days=1))
    if headers is None:
        return minimum
    value = headers.get("Retry-After")
    if value is None:
        return minimum
    try:
        seconds = int(value)
        candidate = add(timedelta(seconds=max(0, min(seconds, 86_400))))
    except ValueError:
        try:
            candidate = parsedate_to_datetime(value)
            if candidate.tzinfo is None or candidate.utcoffset() is None:
                return minimum
            candidate = candidate.astimezone(UTC)
        except (TypeError, ValueError, OverflowError):
            return minimum
    return max(minimum, min(maximum, candidate))


def _validated_item(value: object) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "item_id",
        "kind",
        "title",
        "summary",
        "source",
        "published_at",
        "affected_subjects",
        "match_reason",
        "url",
    }:
        raise NewsProviderError("news cache item is malformed")
    if value.get("kind") != "EXTERNAL_NEWS":
        raise NewsProviderError("news cache item is malformed")
    item_id = _text(value.get("item_id"), maximum=100, required=True)
    title = _text(value.get("title"), maximum=300, required=True)
    summary = _text(value.get("summary"), maximum=500)
    source = _text(value.get("source"), maximum=120, required=True)
    match_reason = _text(value.get("match_reason"), maximum=500, required=True)
    try:
        published = datetime.fromisoformat(str(value.get("published_at")))
    except ValueError as error:
        raise NewsProviderError("news cache timestamp is malformed") from error
    published_at = _iso(published)
    url = _safe_https_url(value.get("url"))
    subjects = value.get("affected_subjects")
    if (
        not isinstance(subjects, list)
        or not subjects
        or len(subjects) > 20
        or any(not isinstance(subject, str) or len(subject) > 30 for subject in subjects)
    ):
        raise NewsProviderError("news cache subjects are malformed")
    normalized_subjects = sorted(
        {_text(subject, maximum=30, required=True) for subject in subjects}
    )
    return {
        "item_id": item_id,
        "kind": "EXTERNAL_NEWS",
        "title": title,
        "summary": summary,
        "source": source,
        "published_at": published_at,
        "affected_subjects": normalized_subjects,
        "match_reason": match_reason,
        "url": url,
    }


def _record(value: object) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "schema_version",
        "attempted_at",
        "next_refresh_at",
        "last_success_at",
        "status",
        "items",
    }:
        raise NewsProviderError("news cache record is malformed")
    if value.get("schema_version") != 1 or value.get("status") not in {
        "LIVE",
        "ERROR",
        "RATE_LIMITED",
    }:
        raise NewsProviderError("news cache record is malformed")
    for field in ("attempted_at", "next_refresh_at"):
        try:
            stamp = datetime.fromisoformat(str(value[field]))
        except (KeyError, ValueError) as error:
            raise NewsProviderError("news cache timestamp is malformed") from error
        _iso(stamp)
    last_success = value.get("last_success_at")
    if last_success is not None:
        try:
            _iso(datetime.fromisoformat(str(last_success)))
        except ValueError as error:
            raise NewsProviderError("news cache timestamp is malformed") from error
    items = value.get("items")
    if not isinstance(items, list) or len(items) > MAX_ITEMS:
        raise NewsProviderError("news cache items are malformed")
    value["items"] = [_validated_item(item) for item in items]
    return value


@dataclass(frozen=True, slots=True)
class _CacheState:
    latest: dict[str, Any] | None
    byte_count: int
    record_count: int
    needs_compaction: bool


def _latest(handle: TextIO) -> _CacheState:
    if not isinstance(handle, io.TextIOWrapper):
        raise NewsProviderError("news cache handle is invalid")
    handle.flush()
    binary = handle.buffer
    byte_count = os.fstat(binary.fileno()).st_size
    read_count = min(byte_count, MAX_CACHE_READ_BYTES)
    start = byte_count - read_count
    preceding = b"\n"
    if start:
        binary.seek(start - 1)
        preceding = binary.read(1)
        if len(preceding) != 1:
            raise NewsProviderError("news cache boundary read was incomplete")
    binary.seek(start)
    retained = binary.read(read_count)
    if len(retained) != read_count:
        raise NewsProviderError("news cache read was incomplete")
    if start and preceding != b"\n":
        first_newline = retained.find(b"\n")
        if first_newline < 0:
            return _CacheState(None, byte_count, MAX_CACHE_RECORDS + 1, True)
        retained = retained[first_newline + 1 :]
    parts = retained.split(b"\n")
    complete = parts[:-1]
    partial = parts[-1]
    record_count = len(complete) + bool(partial) if start == 0 else MAX_CACHE_RECORDS + 1
    needs_compaction = (
        byte_count > MAX_CACHE_BYTES
        or record_count > MAX_CACHE_RECORDS
        or bool(partial)
        or start > 0
    )
    latest: dict[str, Any] | None = None
    for line in reversed(complete[-MAX_CACHE_RECORDS:]):
        if len(line) + 1 > MAX_CACHE_LINE_BYTES:
            needs_compaction = True
            continue
        try:
            latest = _record(_load_json(line + b"\n"))
        except NewsProviderError:
            needs_compaction = True
            continue
        break
    return _CacheState(latest, byte_count, record_count, needs_compaction)


def _encoded_record(record: dict[str, Any]) -> bytes:
    encoded = json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
    payload = encoded.encode()
    if len(payload) > MAX_CACHE_LINE_BYTES:
        raise NewsProviderError("news cache record is too large")
    return payload


def _read_cache(root: Path) -> _CacheState:
    with confined_audit_handle(root, CACHE_PATH, create=True) as cache:
        assert cache is not None
        return _latest(cache)


def _retain_cache(root: Path, state: _CacheState, record: dict[str, Any]) -> None:
    encoded = _encoded_record(record)
    if (
        state.needs_compaction
        or state.record_count + 1 > MAX_CACHE_RECORDS
        or state.byte_count + len(encoded) > MAX_CACHE_BYTES
    ):
        confined_atomic_write(root, CACHE_PATH, encoded)
        return
    with confined_audit_handle(root, CACHE_PATH, create=True) as handle:
        assert handle is not None
        handle.seek(0, os.SEEK_END)
        handle.write(encoded.decode("utf-8"))
        handle.flush()
        os.fsync(handle.fileno())


def _compact_cache(root: Path, record: dict[str, Any]) -> None:
    confined_atomic_write(root, CACHE_PATH, _encoded_record(record))


def _freshness(record: dict[str, Any] | None, now: datetime, detail: str) -> dict[str, Any]:
    last_success = (
        datetime.fromisoformat(str(record["last_success_at"]))
        if record is not None and record.get("last_success_at") is not None
        else None
    )
    if record is not None and record["status"] == "LIVE":
        status = "LIVE"
    elif last_success is None:
        status = "UNAVAILABLE"
    elif now - last_success <= timedelta(hours=1):
        status = "DELAYED"
    else:
        status = "STALE"
    return {
        "source": "COINDESK_DATA_NEWS",
        "status": status,
        "observed_at": _iso(last_success) if last_success is not None else None,
        "detail": detail,
    }


def _failure_detail(last_success: object) -> str:
    if isinstance(last_success, str) and last_success:
        return "External news refresh is delayed; showing last-good metadata."
    return "External news is unavailable; no retained external metadata exists yet."


def build_external_news(
    root: Path,
    subjects: set[str],
    *,
    now: datetime | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Return cached relevant metadata, refreshing lazily only when configured."""
    at = (now or datetime.now(tz=UTC)).astimezone(UTC)
    key = (api_key if api_key is not None else os.environ.get("TIOS_COINDESK_API_KEY", "")).strip()
    if (
        not key
        or len(key) > 512
        or not key.isascii()
        or any(character.isspace() for character in key)
        or any(not 32 <= ord(character) <= 126 for character in key)
    ):
        return {
            "items": [],
            "freshness": _freshness(None, at, "Optional external news is not configured."),
        }
    try:
        with confined_audit_handle(root, LOCK_PATH, create=True) as lock:
            assert lock is not None
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            state = _read_cache(root)
            latest = state.latest
            if latest is not None:
                next_refresh = datetime.fromisoformat(str(latest["next_refresh_at"]))
                if at < next_refresh:
                    if state.needs_compaction:
                        _compact_cache(root, latest)
                    detail = (
                        "Relevant external news metadata is current."
                        if latest["status"] == "LIVE"
                        else _failure_detail(latest.get("last_success_at"))
                    )
                    return {
                        "items": latest["items"],
                        "freshness": _freshness(latest, at, detail),
                    }
            retained_items = latest["items"] if latest is not None else []
            last_success = latest.get("last_success_at") if latest is not None else None
            status = "LIVE"
            next_refresh = at + REFRESH_INTERVAL
            try:
                items = _fetch(key, subjects)
                last_success = _iso(at)
                detail = "Relevant external news metadata is current."
            except HTTPError as error:
                items = retained_items
                status = "RATE_LIMITED" if error.code == 429 else "ERROR"
                next_refresh = (
                    _retry_after(error.headers, at) if error.code == 429 else at + REFRESH_INTERVAL
                )
                detail = _failure_detail(last_success)
                error.close()
            except (HTTPException, OSError, TimeoutError, URLError, NewsProviderError):
                items = retained_items
                status = "ERROR"
                detail = _failure_detail(last_success)
            record = {
                "schema_version": 1,
                "attempted_at": _iso(at),
                "next_refresh_at": _iso(next_refresh),
                "last_success_at": last_success,
                "status": status,
                "items": items,
            }
            _retain_cache(root, state, record)
            return {"items": items, "freshness": _freshness(record, at, detail)}
    except (OSError, AuditPathError, NewsProviderError):
        return {
            "items": [],
            "freshness": _freshness(None, at, "External news metadata is unavailable."),
        }
