"""Multi-dataset Binance public-data acquirer (DS-CRYPTO-MULTI-V1).

Generalises the DS-CRYPTO-SPOT-BAKEOFF-V1 downloader to more pairs, more
timeframes, aggTrades ticks, and perp funding — exact official CHECKSUM evidence
retained when available, never-overwrite, resumable. Operator-approved scope
(2026-07-12): top spot pairs OHLCV (all timeframes) + BTC/ETH full-history
aggTrades + funding.

Modes:
  plan   — HEAD every file, sum exact sizes, download nothing (answers "how many GB").
  fetch  — download + verify (resumable; safe to re-run / interrupt).

Reuses tios.dataset.download primitives (fetch, checksum, retries). Stdlib + no
payload is trusted until sha256 matches Binance's official .CHECKSUM.

Run: uv run python -m tios.dataset.acquire plan   (then: ... fetch)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from tios.dataset.download import RETRIES, official_checksum, sha256_hex

BASE = "https://data.binance.vision/data"
RAW_ROOT = Path(__file__).resolve().parents[3] / "data" / "raw"
START_MONTH = (2021, 1)
END_MONTH = (2026, 6)

# Top liquid USDT spot pairs (curated; symbol-months that predate a listing 404 and
# are skipped, not failed). Order is stable so the manifest is deterministic.
TOP_PAIRS = (
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT",
    "AVAXUSDT", "DOTUSDT", "LINKUSDT", "MATICUSDT", "LTCUSDT", "TRXUSDT", "ATOMUSDT",
    "UNIUSDT", "ETCUSDT", "XLMUSDT", "BCHUSDT", "FILUSDT", "APTUSDT", "NEARUSDT",
    "ARBUSDT", "OPUSDT", "INJUSDT", "AAVEUSDT", "SUIUSDT", "SEIUSDT", "TIAUSDT",
    "RUNEUSDT", "ALGOUSDT", "GRTUSDT", "SANDUSDT", "MANAUSDT", "AXSUSDT", "FTMUSDT",
    "EGLDUSDT", "THETAUSDT", "XTZUSDT", "EOSUSDT", "FLOWUSDT", "CHZUSDT", "ENJUSDT",
    "ZECUSDT", "DASHUSDT", "KSMUSDT", "COMPUSDT", "YFIUSDT", "SNXUSDT", "MKRUSDT",
    "CRVUSDT",
)  # fmt: skip
TIMEFRAMES = ("1m", "5m", "15m", "1h", "4h", "1d")
TICK_PAIRS = ("BTCUSDT", "ETHUSDT")  # full-history aggTrades (the ~55 GB)
# Pairs for spot-vs-perp basis modelling of the funding carry (8h spot + 8h perp klines).
BASIS_PAIRS = (
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT",
    "DOGEUSDT", "AVAXUSDT", "LINKUSDT", "LTCUSDT", "DOTUSDT", "MATICUSDT",
)  # fmt: skip


@dataclass(frozen=True)
class FileSpec:
    kind: str  # klines | aggTrades | fundingRate
    symbol: str
    interval: str | None
    month: str
    rel: str  # local path under RAW_ROOT
    url: str


@dataclass
class Acquired:
    rel: str
    size: int
    sha256: str
    checksum_verified: bool
    official_sha256: str | None
    status: str  # downloaded | reused | missing


def _month(value: str) -> tuple[int, int]:
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", value):
        raise ValueError(f"invalid month: {value!r}; expected YYYY-MM")
    return int(value[:4]), int(value[5:])


def months(start: tuple[int, int] = START_MONTH, end: tuple[int, int] = END_MONTH) -> list[str]:
    if start > end:
        raise ValueError("start month must not be after end month")
    out, (y, m) = [], start
    while (y, m) <= end:
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def _kline_spec(symbol: str, interval: str, month: str) -> FileSpec:
    name = f"{symbol}-{interval}-{month}.zip"
    return FileSpec(
        "klines",
        symbol,
        interval,
        month,
        f"klines/{symbol}/{interval}/{name}",
        f"{BASE}/spot/monthly/klines/{symbol}/{interval}/{name}",
    )


def _simple_spec(market: str, kind: str, symbol: str, month: str) -> FileSpec:
    name = f"{symbol}-{kind}-{month}.zip"
    return FileSpec(
        kind,
        symbol,
        None,
        month,
        f"{kind}/{symbol}/{name}",
        f"{BASE}/{market}/monthly/{kind}/{symbol}/{name}",
    )


def _basis_spec(market: str, local_kind: str, symbol: str, month: str) -> FileSpec:
    """8h klines for spot-vs-perp basis modelling — market 'spot' or 'futures/um'."""
    name = f"{symbol}-8h-{month}.zip"
    return FileSpec(
        local_kind, symbol, "8h", month,
        f"{local_kind}/{symbol}/{name}",
        f"{BASE}/{market}/monthly/klines/{symbol}/8h/{name}",
    )  # fmt: skip


def validate_scope(
    kinds: tuple[str, ...],
    *,
    symbols: tuple[str, ...] | None = None,
    timeframes: tuple[str, ...] | None = None,
    start_month: str | None = None,
    end_month: str | None = None,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[int, int], tuple[int, int]]:
    """Validate optional kline-only selectors and return their canonical scope."""
    allowed_kinds = {"klines", "aggTrades", "fundingRate", "basis"}
    if not kinds or len(set(kinds)) != len(kinds) or not set(kinds) <= allowed_kinds:
        raise ValueError(f"invalid acquisition kinds: {kinds!r}")
    filtered = any(v is not None for v in (symbols, timeframes, start_month, end_month))
    if filtered and kinds != ("klines",):
        raise ValueError("symbols/timeframes/month filters are supported only for --kinds klines")
    selected_symbols = symbols if symbols is not None else TOP_PAIRS
    selected_timeframes = timeframes if timeframes is not None else TIMEFRAMES
    if not selected_symbols or len(set(selected_symbols)) != len(selected_symbols):
        raise ValueError("symbols must be a non-empty unique list")
    if not selected_timeframes or len(set(selected_timeframes)) != len(selected_timeframes):
        raise ValueError("timeframes must be a non-empty unique list")
    unknown_symbols = sorted(set(selected_symbols) - set(TOP_PAIRS))
    unknown_timeframes = sorted(set(selected_timeframes) - set(TIMEFRAMES))
    if unknown_symbols:
        raise ValueError(f"unsupported symbols: {unknown_symbols}")
    if unknown_timeframes:
        raise ValueError(f"unsupported timeframes: {unknown_timeframes}")
    start = _month(start_month) if start_month is not None else START_MONTH
    end = _month(end_month) if end_month is not None else END_MONTH
    if start < START_MONTH or end > END_MONTH:
        raise ValueError("month selectors must stay within 2021-01..2026-06")
    if start > end:
        raise ValueError("start month must not be after end month")
    return selected_symbols, selected_timeframes, start, end


def planned_files(
    kinds: tuple[str, ...],
    *,
    symbols: tuple[str, ...] | None = None,
    timeframes: tuple[str, ...] | None = None,
    start_month: str | None = None,
    end_month: str | None = None,
) -> list[FileSpec]:
    selected_symbols, selected_timeframes, start, end = validate_scope(
        kinds,
        symbols=symbols,
        timeframes=timeframes,
        start_month=start_month,
        end_month=end_month,
    )
    selected_months = months(start, end)
    specs: list[FileSpec] = []
    if "klines" in kinds:
        specs += [
            _kline_spec(s, iv, mo)
            for s in selected_symbols
            for iv in selected_timeframes
            for mo in selected_months
        ]
    if "aggTrades" in kinds:
        specs += [_simple_spec("spot", "aggTrades", s, mo) for s in TICK_PAIRS for mo in months()]
    if "fundingRate" in kinds:
        specs += [
            _simple_spec("futures/um", "fundingRate", s, mo) for s in TOP_PAIRS for mo in months()
        ]
    if "basis" in kinds:  # 8h spot + 8h perp klines for the carry basis model
        for s in BASIS_PAIRS:
            for mo in months():
                specs.append(_basis_spec("spot", "spot8h", s, mo))
                specs.append(_basis_spec("futures/um", "perp8h", s, mo))
    return specs


def head_size(url: str) -> int | None:
    """Content-Length via HEAD; None if the file does not exist (404) or is blocked."""
    req = urllib.request.Request(url, method="HEAD")
    for attempt in range(RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                length = r.headers.get("Content-Length")
                return int(length) if length is not None else None
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if attempt == RETRIES - 1:
                return None
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if attempt == RETRIES - 1:
                return None
    return None


def download_one(spec: FileSpec) -> Acquired:
    dest = RAW_ROOT / spec.rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():  # never overwrite (resumable)
        data = dest.read_bytes()
        status = "reused"
    else:
        try:
            with urllib.request.urlopen(spec.url, timeout=120) as r:
                data = r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:  # symbol not listed yet that month — expected, not a failure
                return Acquired(spec.rel, 0, "", False, None, "missing")
            raise
        status = "downloaded"
    digest = sha256_hex(data)
    official = official_checksum(spec.url)
    if official is not None and official != digest:
        raise RuntimeError(f"CHECKSUM mismatch {spec.rel}: {digest} != {official}")
    if status == "downloaded":
        tmp = dest.with_suffix(dest.suffix + ".part")
        tmp.write_bytes(data)
        tmp.rename(dest)
    return Acquired(spec.rel, len(data), digest, official is not None, official, status)


def write_manifest(
    kinds: tuple[str, ...],
    results: list[Acquired],
    *,
    symbols: tuple[str, ...] | None = None,
    timeframes: tuple[str, ...] | None = None,
    start_month: str | None = None,
    end_month: str | None = None,
    require_official_checksums: bool = False,
) -> Path:
    """Retain a content-addressed manifest; acquisition kinds never overwrite each other."""
    generated = datetime.now(tz=UTC).isoformat()
    selected_symbols, selected_timeframes, start, end = validate_scope(
        kinds,
        symbols=symbols,
        timeframes=timeframes,
        start_month=start_month,
        end_month=end_month,
    )
    planned = planned_files(
        kinds,
        symbols=symbols,
        timeframes=timeframes,
        start_month=start_month,
        end_month=end_month,
    )
    planned_rels = [item.rel for item in planned]
    result_rels = [item.rel for item in results]
    if len(result_rels) != len(set(result_rels)):
        raise ValueError("acquisition results contain duplicate paths")
    if set(result_rels) != set(planned_rels) or len(result_rels) != len(planned_rels):
        missing = sorted(set(planned_rels) - set(result_rels))
        extra = sorted(set(result_rels) - set(planned_rels))
        raise ValueError(
            f"acquisition results do not match planned scope: missing={missing} extra={extra}"
        )
    retained = [r for r in results if r.status != "missing"]
    if require_official_checksums and any(
        not item.checksum_verified or item.official_sha256 != item.sha256 for item in retained
    ):
        raise ValueError("manifest requires exact official checksum proof for every retained file")
    payload = {
        "schema_version": 3,
        "dataset_id": "DS-CRYPTO-MULTI-V1",
        "source": "Binance public data (data.binance.vision)",
        "generated_utc": generated,
        "window": {
            "start": f"{start[0]:04d}-{start[1]:02d}",
            "end": f"{end[0]:04d}-{end[1]:02d}",
        },
        "kinds": list(kinds),
        "scope": {
            "symbols": list(selected_symbols),
            "timeframes": list(selected_timeframes),
            "planned_file_count": len(planned),
            "require_official_checksums": require_official_checksums,
        },
        "files": [asdict(r) for r in retained],
    }
    encoded = (json.dumps(payload, indent=2) + "\n").encode()
    kind_key = "-".join(sorted(kinds))
    root = RAW_ROOT / "manifests" / kind_key
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"raw_manifest_{hashlib.sha256(encoded).hexdigest()}.json"
    if not path.exists():
        path.write_bytes(encoded)
    return path


def plan(
    kinds: tuple[str, ...],
    workers: int,
    *,
    symbols: tuple[str, ...] | None = None,
    timeframes: tuple[str, ...] | None = None,
    start_month: str | None = None,
    end_month: str | None = None,
) -> None:
    specs = planned_files(
        kinds,
        symbols=symbols,
        timeframes=timeframes,
        start_month=start_month,
        end_month=end_month,
    )
    print(f"planning {len(specs)} files across {kinds} (HEAD only, no download)...")
    with ThreadPoolExecutor(max_workers=workers) as ex:
        sizes = list(ex.map(lambda s: (s.kind, head_size(s.url)), specs))
    totals: dict[str, list[int]] = {}
    for kind, size in sizes:
        bucket = totals.setdefault(kind, [0, 0])
        if size is not None:
            bucket[0] += size
            bucket[1] += 1
    grand = 0
    for kind, (nbytes, present) in sorted(totals.items()):
        grand += nbytes
        print(f"  {kind:<14} {present:>5} files present  {nbytes / 1e9:8.2f} GB")
    print(f"  {'TOTAL':<14} {'':>5}                {grand / 1e9:8.2f} GB (compressed download)")


def fetch(
    kinds: tuple[str, ...],
    workers: int,
    *,
    symbols: tuple[str, ...] | None = None,
    timeframes: tuple[str, ...] | None = None,
    start_month: str | None = None,
    end_month: str | None = None,
    require_official_checksums: bool = False,
) -> None:
    specs = planned_files(
        kinds,
        symbols=symbols,
        timeframes=timeframes,
        start_month=start_month,
        end_month=end_month,
    )
    RAW_ROOT.mkdir(parents=True, exist_ok=True)
    print(f"fetching {len(specs)} files across {kinds} (resumable, checksum-verified)...")
    with ThreadPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(download_one, specs))
    by_status: dict[str, int] = {}
    nbytes = 0
    for r in results:
        by_status[r.status] = by_status.get(r.status, 0) + 1
        nbytes += r.size
    unverified = [r.rel for r in results if r.status != "missing" and not r.checksum_verified]
    if require_official_checksums and unverified:
        raise RuntimeError(
            f"official checksum required but unavailable for {len(unverified)} retained files"
        )
    manifest = write_manifest(
        kinds,
        results,
        symbols=symbols,
        timeframes=timeframes,
        start_month=start_month,
        end_month=end_month,
        require_official_checksums=require_official_checksums,
    )
    print(f"  status: {by_status}   bytes: {nbytes / 1e9:.2f} GB")
    print(f"  checksum-unverified files: {len(unverified)}")
    print(f"  manifest: {manifest}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Binance multi-dataset acquirer.")
    parser.add_argument("mode", choices=("plan", "fetch"))
    parser.add_argument(
        "--kinds",
        default="klines,aggTrades,fundingRate",
        help="comma list: klines,aggTrades,fundingRate",
    )
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--symbols", help="comma list; valid only for a klines-only run")
    parser.add_argument("--timeframes", help="comma list; valid only for a klines-only run")
    parser.add_argument("--start-month", help="inclusive YYYY-MM; valid only for klines")
    parser.add_argument("--end-month", help="inclusive YYYY-MM; valid only for klines")
    parser.add_argument(
        "--require-official-checksums",
        action="store_true",
        help="fail without publishing a manifest unless every retained file is officially verified",
    )
    args = parser.parse_args()
    kinds = tuple(k.strip() for k in args.kinds.split(",") if k.strip())

    def selector(value: str | None, name: str) -> tuple[str, ...] | None:
        if value is None:
            return None
        selected = tuple(item.strip() for item in value.split(",") if item.strip())
        if not selected:
            parser.error(f"--{name} must contain at least one value")
        return selected

    symbols = selector(args.symbols, "symbols")
    timeframes = selector(args.timeframes, "timeframes")
    kwargs = {
        "symbols": symbols,
        "timeframes": timeframes,
        "start_month": args.start_month,
        "end_month": args.end_month,
    }
    if args.mode == "plan":
        if args.require_official_checksums:
            parser.error("--require-official-checksums is valid only in fetch mode")
        plan(kinds, args.workers, **kwargs)
    else:
        fetch(
            kinds,
            args.workers,
            **kwargs,
            require_official_checksums=args.require_official_checksums,
        )


if __name__ == "__main__":
    main()
