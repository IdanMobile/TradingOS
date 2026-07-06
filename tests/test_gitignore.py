"""Gitignore audit (T-003-05, AD §AB): secret paths ignored, .env.example tracked."""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

MUST_IGNORE = [
    ".env",
    ".env.local",
    ".env.prod.local",
    "secrets/k.pem",
    "x-credentials.json",
    "engines/build.log",
    ".dvc/cache/x",
    ".dvc/tmp/x",
]
MUST_NOT_IGNORE = [".env.example"]


def is_ignored(path: str) -> bool:
    r = subprocess.run(["git", "check-ignore", "-q", path], cwd=ROOT)
    return r.returncode == 0


def test_secret_paths_are_ignored() -> None:
    missing = [p for p in MUST_IGNORE if not is_ignored(p)]
    assert missing == [], f"gitignore does not cover: {missing}"


def test_env_example_is_not_ignored() -> None:
    wrongly = [p for p in MUST_NOT_IGNORE if is_ignored(p)]
    assert wrongly == [], f"wrongly ignored: {wrongly}"


def test_no_env_file_tracked() -> None:
    out = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    bad = [f for f in out if f == ".env" or f.startswith(".env.") and f != ".env.example"]
    assert bad == [], f"secret env files tracked in git: {bad}"
