"""Multi-dataset Binance public-data acquirer (DS-CRYPTO-MULTI-V1).

Generalises the DS-CRYPTO-SPOT-BAKEOFF-V1 downloader to more pairs, more
timeframes, aggTrades ticks, and perp funding — all official-CHECKSUM-verified,
never-overwrite, resumable. Operator-approved scope (2026-07-12): top spot pairs
OHLCV (all timeframes) + BTC/ETH full-history aggTrades + funding.

Modes:
  plan   — HEAD every file, sum exact sizes, download nothing (answers "how many GB").
  fetch  — download + verify (resumable; safe to re-run / interrupt).

Reuses tios.dataset.download primitives (fetch, checksum, retries). Stdlib + no
payload is trusted until sha256 matches Binance's official .CHECKSUM.

Run: uv run python -m tios.dataset.acquire plan   (then: ... fetch)
"""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from tios.dataset.download import RETRIES, official_checksum, sha256_hex

BASE = "https://data.binance.vision/data"
RAW_ROOT = Path(__file__).resolve().parents[3] / "data" / "raw"
MANIFEST = RAW_ROOT / "multi_raw_manifest.json"
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
    status: str  # downloaded | reused | missing


def months() -> list[str]:
    out, (y, m) = [], START_MONTH
    while (y, m) <= END_MONTH:
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


def planned_files(kinds: tuple[str, ...]) -> list[FileSpec]:
    specs: list[FileSpec] = []
    if "klines" in kinds:
        specs += [_kline_spec(s, iv, mo) for s in TOP_PAIRS for iv in TIMEFRAMES for mo in months()]
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
        return Acquired(spec.rel, len(data), sha256_hex(data), True, "reused")
    try:
        with urllib.request.urlopen(spec.url, timeout=120) as r:
            data = r.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:  # symbol not listed yet that month — expected, not a failure
            return Acquired(spec.rel, 0, "", False, "missing")
        raise
    digest = sha256_hex(data)
    official = official_checksum(spec.url)
    if official is not None and official != digest:
        raise RuntimeError(f"CHECKSUM mismatch {spec.rel}: {digest} != {official}")
    tmp = dest.with_suffix(dest.suffix + ".part")
    tmp.write_bytes(data)
    tmp.rename(dest)
    return Acquired(spec.rel, len(data), digest, official is not None, "downloaded")


def plan(kinds: tuple[str, ...], workers: int) -> None:
    specs = planned_files(kinds)
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


def fetch(kinds: tuple[str, ...], workers: int) -> None:
    specs = planned_files(kinds)
    RAW_ROOT.mkdir(parents=True, exist_ok=True)
    print(f"fetching {len(specs)} files across {kinds} (resumable, checksum-verified)...")
    with ThreadPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(download_one, specs))
    by_status: dict[str, int] = {}
    nbytes = 0
    for r in results:
        by_status[r.status] = by_status.get(r.status, 0) + 1
        nbytes += r.size
    unverified = [r.rel for r in results if r.status == "downloaded" and not r.checksum_verified]
    MANIFEST.write_text(
        json.dumps(
            {
                "dataset_id": "DS-CRYPTO-MULTI-V1",
                "source": "Binance public data (data.binance.vision)",
                "generated_utc": datetime.now(tz=UTC).isoformat(),
                "window": {"start": "2021-01", "end": "2026-06"},
                "kinds": list(kinds),
                "files": [asdict(r) for r in results if r.status != "missing"],
            },
            indent=2,
        )
        + "\n"
    )
    print(f"  status: {by_status}   bytes: {nbytes / 1e9:.2f} GB")
    print(f"  checksum-unverified downloads: {len(unverified)}")
    print(f"  manifest: {MANIFEST}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Binance multi-dataset acquirer.")
    parser.add_argument("mode", choices=("plan", "fetch"))
    parser.add_argument(
        "--kinds",
        default="klines,aggTrades,fundingRate",
        help="comma list: klines,aggTrades,fundingRate",
    )
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    kinds = tuple(k.strip() for k in args.kinds.split(",") if k.strip())
    if args.mode == "plan":
        plan(kinds, args.workers)
    else:
        fetch(kinds, args.workers)


if __name__ == "__main__":
    main()
