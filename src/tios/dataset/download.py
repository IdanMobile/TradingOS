"""Raw snapshot downloader for DS-CRYPTO-SPOT-BAKEOFF-V1 (T-004-01, REQ-006).

Downloads Binance public Spot monthly kline zips + official CHECKSUMs into
data/raw/binance_spot/, verifies sha256, never overwrites, writes a manifest.
Stdlib only. Run: uv run python -m tios.dataset.download
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

BASE_URL = "https://data.binance.vision/data/spot/monthly/klines"
INSTRUMENTS = ("BTCUSDT", "ETHUSDT")
INTERVALS = ("5m", "15m", "1h")
# Spec preferred window: 2021-01-01 .. 2026-06-30 (monthly file coverage verified 2026-07-06)
START_MONTH = (2021, 1)
END_MONTH = (2026, 6)
RETRIES = 3
RAW_ROOT = Path(__file__).resolve().parents[3] / "data" / "raw" / "binance_spot"
MANIFEST_PATH = RAW_ROOT / "raw_manifest.json"


@dataclass
class RawFile:
    file: str  # path relative to RAW_ROOT
    url: str
    sha256: str
    size: int
    downloaded_utc: str
    checksum_verified: bool  # against Binance's official .CHECKSUM file


def months() -> list[str]:
    out = []
    y, m = START_MONTH
    while (y, m) <= END_MONTH:
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def expected_files() -> list[tuple[str, str]]:
    """(relative path, url) for every required monthly zip."""
    out = []
    for sym in INSTRUMENTS:
        for iv in INTERVALS:
            for month in months():
                name = f"{sym}-{iv}-{month}.zip"
                out.append((f"{sym}/{iv}/{name}", f"{BASE_URL}/{sym}/{iv}/{name}"))
    return out


def fetch(url: str) -> bytes:
    last: Exception | None = None
    for attempt in range(RETRIES):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return r.read()  # type: ignore[no-any-return]
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = e
            time.sleep(2**attempt)
    raise RuntimeError(f"unreachable after {RETRIES} attempts: {url}") from last


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def official_checksum(url: str) -> str | None:
    """Binance publishes '<sha256>  <filename>' next to each zip."""
    try:
        return fetch(url + ".CHECKSUM").decode().split()[0]
    except (RuntimeError, UnicodeDecodeError, IndexError):
        return None


def download_one(rel: str, url: str) -> RawFile:
    dest = RAW_ROOT / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():  # never overwrite raw files (spec rule 6)
        data = dest.read_bytes()
        stamp = datetime.fromtimestamp(dest.stat().st_mtime, tz=UTC).isoformat()
    else:
        data = fetch(url)
        tmp = dest.with_suffix(".part")
        tmp.write_bytes(data)
        tmp.rename(dest)
        stamp = datetime.now(tz=UTC).isoformat()
    digest = sha256_hex(data)
    official = official_checksum(url)
    if official is not None and official != digest:
        raise RuntimeError(f"CHECKSUM mismatch for {rel}: local {digest} != official {official}")
    return RawFile(rel, url, digest, len(data), stamp, official is not None)


def main() -> None:
    todo = expected_files()
    pre_existing = sum(1 for rel, _ in todo if (RAW_ROOT / rel).exists())
    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(lambda t: download_one(*t), todo))
    results.sort(key=lambda r: r.file)
    MANIFEST_PATH.write_text(
        json.dumps(
            {
                "dataset_id": "DS-CRYPTO-SPOT-BAKEOFF-V1",
                "source": "Binance public Spot data (data.binance.vision)",
                "window": {"start_month": "2021-01", "end_month": "2026-06"},
                "files": [asdict(r) for r in results],
            },
            indent=2,
        )
        + "\n"
    )
    unverified = [r.file for r in results if not r.checksum_verified]
    print(f"files: {len(results)} (pre-existing {pre_existing}, new {len(results) - pre_existing})")
    print(f"official CHECKSUM verified: {len(results) - len(unverified)}/{len(results)}")
    for f in unverified:
        print(f"  no official checksum: {f}")
    print(f"manifest: {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
