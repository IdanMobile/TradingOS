"""Evidence-producer driver: the scheduler D-100's map was always specifying.

`PROSPECTIVE_SIGNAL_EVIDENCE_PRODUCER_MAP_V1.yaml` maps every eligibility blocker to its
owning producer, its verifier, its release condition, and the earliest point it may
lawfully be evaluated. That is a dependency graph with executable nodes — it was simply
never wired to anything that walks it.

This module walks it. For each blocker it runs the declared verifier, records whether the
blocker released, and reports which producers are now dispatchable. Prose release
conditions are not machine-evaluable; the verifier is their executable form, and its exit
status is the only signal this driver trusts.

Three safety properties, all load-bearing for something that runs unattended:

*Verifiers are allowlisted, never shell.* The map is a config file. Executing arbitrary
strings from config with a shell is a command-injection surface, and an autonomous process
reading its own instructions from disk is exactly where that matters. Only `scripts/*.py`
invoked through the interpreter are dispatchable.

*Declared prohibitions are enforced.* A map's `semantic_boundaries` may prohibit warm-up
analysis or sealed-holdout access. The driver refuses to dispatch anything under a map
carrying an active prohibition rather than trusting each producer to police itself.

*Future work is not fabricated.* Many verifiers read `future ...` — they name work that
does not exist yet. Those are reported as PENDING, never as passing, and never invented.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

SCHEMA_VERSION = 1
REPORT_DIR = Path("artifacts") / "driver"
PARKED_FILENAME = "parked_items.jsonl"
VERIFIER_TIMEOUT_SECONDS = 900
MAX_PARALLEL_VERIFIERS = 4

# A verifier is dispatchable only if it names a real project script. Anything else -
# prose, a future plan, an arbitrary command - is reported, not executed.
DISPATCHABLE_VERIFIER = re.compile(r"^(scripts/[A-Za-z0-9_./-]+\.py)((?:\s+[-A-Za-z0-9_=./]+)*)$")

# Boundaries that, when declared true or PROHIBITED, stop the driver from dispatching
# anything under that map.
PROHIBITION_KEYS = ("warmup_analysis", "sealed_v2_holdout_access", "sealed_holdout_access")


class DriverError(RuntimeError):
    """Raised when a map is malformed or a dispatch would violate a declared boundary."""


@dataclass(frozen=True)
class BlockerNode:
    code: str
    producer: str
    verifier: str
    release_condition: str
    earliest: str
    contributes_to: tuple[str, ...]
    prohibition: str | None = None


@dataclass(frozen=True)
class BlockerStatus:
    code: str
    state: str  # RELEASED | BLOCKED | PENDING | PROHIBITED
    detail: str
    contributes_to: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "state": self.state,
            "detail": self.detail,
            "contributes_to": list(self.contributes_to),
        }


@dataclass(frozen=True)
class DriverReport:
    map_id: str
    subject_ref: str
    statuses: tuple[BlockerStatus, ...]
    prohibitions: tuple[str, ...] = ()
    generated_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))

    @property
    def released(self) -> tuple[str, ...]:
        return tuple(status.code for status in self.statuses if status.state == "RELEASED")

    @property
    def blocked(self) -> tuple[str, ...]:
        return tuple(status.code for status in self.statuses if status.state != "RELEASED")

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "map_id": self.map_id,
            "subject_ref": self.subject_ref,
            "generated_at": self.generated_at.isoformat(),
            "prohibitions": list(self.prohibitions),
            "released": list(self.released),
            "blocked": list(self.blocked),
            "statuses": [status.as_dict() for status in self.statuses],
        }


def load_map(path: Path) -> tuple[str, str, tuple[BlockerNode, ...], tuple[str, ...]]:
    """Parse a producer map into its id, subject, blocker nodes, and active prohibitions."""
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise DriverError(f"{path} is not a mapping")

    boundaries = payload.get("semantic_boundaries") or {}
    prohibitions = tuple(
        key
        for key in PROHIBITION_KEYS
        if str(boundaries.get(key, "")).upper() in {"PROHIBITED", "TRUE"}
    )

    nodes: list[BlockerNode] = []
    for raw in payload.get("blockers") or ():
        if not isinstance(raw, dict) or not raw.get("code"):
            raise DriverError(f"{path} contains a blocker without a code")
        nodes.append(
            BlockerNode(
                code=str(raw["code"]),
                producer=str(raw.get("producer", "")),
                verifier=str(raw.get("verifier", "")),
                release_condition=str(raw.get("release_condition", "")),
                earliest=str(raw.get("earliest", "")),
                contributes_to=tuple(raw.get("contributes_to") or ()),
                prohibition=raw.get("prohibition"),
            )
        )

    return (
        str(payload.get("map_id", path.stem)),
        str(payload.get("subject_ref", "")),
        tuple(nodes),
        prohibitions,
    )


def dispatchable(verifier: str) -> tuple[str, ...] | None:
    """Return the argv for a verifier, or None when it is not safely dispatchable.

    Prose like "future campaign preflight" names work that does not exist yet; executing
    it is impossible and pretending otherwise would fabricate evidence.

    The `scripts/` prefix alone is not containment: `scripts/../../../etc/evil.py` matches
    a naive prefix check while pointing anywhere on the filesystem. Traversal segments are
    rejected outright here, and `check_blocker` independently confirms the resolved path
    stays inside the project. Two checks because this executes code from a config file.
    """
    match = DISPATCHABLE_VERIFIER.match(verifier.strip())
    if not match:
        return None
    script, arguments = match.group(1), match.group(2).split()
    if ".." in PurePosixPath(script).parts:
        return None
    return (sys.executable, script, *arguments)


def check_blocker(root: Path, node: BlockerNode, *, prohibited: bool = False) -> BlockerStatus:
    """Run one blocker's verifier and classify the result."""
    if prohibited:
        return BlockerStatus(
            node.code,
            "PROHIBITED",
            "map declares an active prohibition; dispatch withheld",
            node.contributes_to,
        )

    argv = dispatchable(node.verifier)
    if argv is None:
        return BlockerStatus(
            node.code,
            "PENDING",
            f"verifier is not an executable project script: {node.verifier!r}",
            node.contributes_to,
        )

    # Independent containment check: resolve symlinks and confirm the target is genuinely
    # inside this project before executing it.
    script_path = (root / argv[1]).resolve()
    scripts_root = (root / "scripts").resolve()
    if not script_path.is_relative_to(scripts_root):
        return BlockerStatus(
            node.code,
            "PENDING",
            f"verifier escapes the project scripts directory: {argv[1]}",
            node.contributes_to,
        )

    if not script_path.is_file():
        return BlockerStatus(
            node.code, "PENDING", f"verifier script absent: {argv[1]}", node.contributes_to
        )

    try:
        result = subprocess.run(  # noqa: S603
            argv,
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            timeout=VERIFIER_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return BlockerStatus(
            node.code,
            "BLOCKED",
            f"verifier exceeded {VERIFIER_TIMEOUT_SECONDS}s",
            node.contributes_to,
        )

    if result.returncode == 0:
        return BlockerStatus(node.code, "RELEASED", "verifier passed", node.contributes_to)
    tail = (result.stderr or result.stdout or "").strip().splitlines()
    return BlockerStatus(
        node.code,
        "BLOCKED",
        tail[-1][:400] if tail else f"verifier exited {result.returncode}",
        node.contributes_to,
    )


def run_cycle(root: Path, map_path: Path) -> DriverReport:
    """Evaluate every blocker in one map, in parallel where safe."""
    map_id, subject_ref, nodes, prohibitions = load_map(map_path)
    blocked_by_prohibition = bool(prohibitions)

    with ThreadPoolExecutor(max_workers=MAX_PARALLEL_VERIFIERS) as pool:
        statuses = tuple(
            pool.map(
                lambda node: check_blocker(root, node, prohibited=blocked_by_prohibition),
                nodes,
            )
        )

    report = DriverReport(map_id, subject_ref, statuses, prohibitions)
    _write_report(root, report)
    return report


def park(root: Path, *, item: str, cause: str, phase: str = "") -> None:
    """Record work that cannot proceed, with the reason, and move on.

    A parked item is not a failure and not a silent skip: it is a durable statement that
    something is genuinely unreachable, so the next cycle does not retry it blindly and a
    reader can see why the pipeline stopped short.
    """
    target = root / REPORT_DIR / PARKED_FILENAME
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "schema_version": SCHEMA_VERSION,
                    "item": item,
                    "cause": cause,
                    "phase": phase,
                    "parked_at": datetime.now(tz=UTC).isoformat(),
                },
                sort_keys=True,
            )
            + "\n"
        )


def parked_items(root: Path) -> tuple[dict[str, Any], ...]:
    target = root / REPORT_DIR / PARKED_FILENAME
    if not target.is_file():
        return ()
    return tuple(
        json.loads(line) for line in target.read_text(encoding="utf-8").splitlines() if line.strip()
    )


def _write_report(root: Path, report: DriverReport) -> None:
    target = root / REPORT_DIR / f"{report.map_id}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report.as_dict(), indent=2) + "\n", encoding="utf-8")
