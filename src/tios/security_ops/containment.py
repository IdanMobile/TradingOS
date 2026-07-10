"""Subprocess containment for untrusted ingested Python code."""

from __future__ import annotations

import platform
import subprocess
from dataclasses import dataclass
from pathlib import Path


class ContainmentError(ValueError):
    """Raised when an untrusted execution request violates containment policy."""


@dataclass(frozen=True)
class ContainedResult:
    returncode: int
    stdout: str
    stderr: str
    network_denied: bool


SANDBOX_EXEC = Path("/usr/bin/sandbox-exec")


def run_untrusted_python(
    script: Path,
    *,
    interpreter: Path,
    working_dir: Path,
    timeout_seconds: int = 30,
) -> ContainedResult:
    """Run a local script out-of-process with no inherited credentials or network."""
    root = working_dir.resolve()
    source = script.resolve()
    if not source.is_relative_to(root):
        raise ContainmentError("script must be inside the isolated working directory")
    if ".venv" not in interpreter.parts or not interpreter.is_file():
        raise ContainmentError("an isolated .venv interpreter is required")
    environment = {
        "HOME": str(root),
        "PATH": str(interpreter.parent),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        "TMPDIR": str(root),
    }
    command = [str(interpreter), str(source)]
    if platform.system() != "Darwin" or not SANDBOX_EXEC.is_file():
        raise ContainmentError("network isolation is unavailable; refusing untrusted execution")
    command = [
        str(SANDBOX_EXEC),
        "-p",
        "(version 1)(allow default)(deny network*)",
        *command,
    ]
    process = subprocess.run(
        command,
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    return ContainedResult(process.returncode, process.stdout, process.stderr, True)
