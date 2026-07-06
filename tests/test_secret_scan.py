"""Secret scan over git-tracked files (T-003-04/T-003-05, AD §AB).

ponytail: regex scanner over tracked files; upgrade to gitleaks/detect-secrets
if pattern coverage proves insufficient.
"""

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# High-signal key formats. Built so this file itself never matches.
PATTERNS = [
    re.compile(p)
    for p in (
        r"AKIA[0-9A-Z]{16}",  # AWS access key
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----",  # PEM private key
        r"\bsk-[A-Za-z0-9_-]{20,}",  # OpenAI/Anthropic-style key
        r"ghp_[A-Za-z0-9]{36}",  # GitHub PAT
        r"xox[baprs]-[A-Za-z0-9-]{10,}",  # Slack token
        r"AIzaSy[A-Za-z0-9_-]{33}",  # Google API key
        r"\bsk_live_[A-Za-z0-9]{10,}",  # Stripe live key
        # DSN with embedded credentials
        r"\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|amqp)://[^\s/@]+:[^\s@]+@",
    )
]


def scan_text(name: str, text: str) -> list[str]:
    return [f"{name}: matches {p.pattern}" for p in PATTERNS if p.search(text)]


def tracked_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout
    return [ROOT / f for f in out.split("\0") if f]


def test_no_secrets_in_tracked_files() -> None:
    this_file = Path(__file__).resolve()
    hits: list[str] = []
    for f in tracked_files():
        if f == this_file or not f.is_file():
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # binary or unreadable: key formats above are text
        hits += scan_text(str(f.relative_to(ROOT)), text)
    assert hits == []


def test_scanner_detects_planted_secrets() -> None:
    """Prove the gate can fail. Fakes assembled at runtime so this file stays clean."""
    fake_aws = "AKIA" + "A" * 16
    fake_pem = "-----BEGIN " + "RSA PRIVATE" + " KEY-----"
    fake_sk = "sk-" + "a" * 24
    for fake in (fake_aws, fake_pem, fake_sk):
        assert scan_text("planted", f"x = '{fake}'"), f"scanner missed: {fake[:8]}..."
    assert scan_text("planted", "harmless text") == []
