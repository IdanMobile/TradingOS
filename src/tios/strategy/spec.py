"""CanonicalStrategySpec model (T-005-01, REQ-011; TYPE_AND_CONTRACT_CATALOG §2).

Framework-neutral strategy spec: rule trees are `all:`/`any:` boolean composition
over comparison expressions. Parsing is strict — any structural problem raises
SpecError with a precise path. Hashing is canonical-JSON sha256.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

COMPARISON_OPS = ("<=", ">=", "==", "!=", "<", ">")  # longest first for parsing
_IDENT = r"[a-z_][a-z0-9_]*"
_NUMBER = r"-?\d+(?:\.\d+)?"
_OPERAND = rf"(?:{_IDENT}|{_NUMBER})"
_COMPARISON_RE = re.compile(rf"^\s*({_OPERAND})\s*(<=|>=|==|!=|<|>)\s*({_OPERAND})\s*$")

FAMILIES = (
    "trend_following",
    "mean_reversion",
    "breakout",
    "carry",
    "market_making",
    "arbitrage",
    "buy_and_hold",
    "other",
)
SIZING_TYPES = ("fixed_fraction", "fixed_amount", "all_in")


class SpecError(ValueError):
    """Structural/semantic spec problem with a precise location path."""

    def __init__(self, path: str, message: str) -> None:
        self.path = path
        super().__init__(f"{path}: {message}")


@dataclass(frozen=True)
class Comparison:
    left: str
    op: str
    right: str

    @classmethod
    def parse(cls, expr: str, path: str) -> Comparison:
        m = _COMPARISON_RE.match(expr)
        if not m:
            raise SpecError(
                path,
                f"not a valid comparison {expr!r} (expected '<operand> <op> <operand>' "
                f"with op in {COMPARISON_OPS}, operands lower_snake identifiers or numbers)",
            )
        return cls(m.group(1), m.group(2), m.group(3))

    def identifiers(self) -> set[str]:
        return {s for s in (self.left, self.right) if not re.fullmatch(_NUMBER, s)}

    def to_obj(self) -> str:
        return f"{self.left} {self.op} {self.right}"


@dataclass(frozen=True)
class RuleTree:
    """`all` (AND) or `any` (OR) over children; leaves are comparisons."""

    kind: str  # "all" | "any"
    comparisons: tuple[Comparison, ...]
    subtrees: tuple[RuleTree, ...] = ()

    @classmethod
    def parse(cls, node: object, path: str) -> RuleTree:
        if not isinstance(node, dict) or len(node) != 1:
            raise SpecError(path, "rule node must be a single-key mapping 'all:' or 'any:'")
        kind, children = next(iter(node.items()))
        if kind not in ("all", "any"):
            raise SpecError(path, f"unknown rule combinator {kind!r} (must be 'all' or 'any')")
        if not isinstance(children, list) or not children:
            raise SpecError(f"{path}.{kind}", "must be a non-empty list")
        comparisons: list[Comparison] = []
        subtrees: list[RuleTree] = []
        for i, child in enumerate(children):
            cpath = f"{path}.{kind}[{i}]"
            if isinstance(child, str):
                comparisons.append(Comparison.parse(child, cpath))
            else:
                subtrees.append(cls.parse(child, cpath))
        return cls(kind, tuple(comparisons), tuple(subtrees))

    def identifiers(self) -> set[str]:
        out: set[str] = set()
        for c in self.comparisons:
            out |= c.identifiers()
        for t in self.subtrees:
            out |= t.identifiers()
        return out

    def to_obj(self) -> dict[str, list[Any]]:
        return {
            self.kind: [c.to_obj() for c in self.comparisons] + [t.to_obj() for t in self.subtrees]
        }


@dataclass(frozen=True)
class Indicator:
    name: str
    parameters: dict[str, float | int | str]
    outputs: tuple[str, ...]  # identifiers this indicator makes available to rules

    def to_obj(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "parameters": dict(self.parameters),
            "outputs": list(self.outputs),
        }


@dataclass(frozen=True)
class CanonicalStrategySpec:
    strategy_id: str
    family: str
    inputs: tuple[str, ...]
    indicators: tuple[Indicator, ...]
    entry_long: RuleTree | None
    exit_long: RuleTree | None
    position_sizing: dict[str, Any]
    risk: dict[str, Any]
    assumptions: tuple[str, ...] = ()
    ambiguities: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()
    license_ref: str | None = None
    always_in_market: bool = False  # buy-and-hold style: no rule trees required

    def available_identifiers(self) -> set[str]:
        out = set(self.inputs)
        for ind in self.indicators:
            out |= set(ind.outputs)
        return out

    def to_obj(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "family": self.family,
            "inputs": list(self.inputs),
            "indicators": [i.to_obj() for i in self.indicators],
            "entry_long": self.entry_long.to_obj() if self.entry_long else None,
            "exit_long": self.exit_long.to_obj() if self.exit_long else None,
            "position_sizing": self.position_sizing,
            "risk": self.risk,
            "assumptions": list(self.assumptions),
            "ambiguities": list(self.ambiguities),
            "source_refs": list(self.source_refs),
            "license_ref": self.license_ref,
            "always_in_market": self.always_in_market,
        }

    def spec_hash(self) -> str:
        canonical = json.dumps(self.to_obj(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()


def _require(data: dict[str, Any], key: str, typ: type, path: str) -> Any:
    if key not in data:
        raise SpecError(f"{path}.{key}", "missing required field")
    val = data[key]
    if not isinstance(val, typ):
        raise SpecError(f"{path}.{key}", f"expected {typ.__name__}, got {type(val).__name__}")
    return val


def _str_list(data: dict[str, Any], key: str, path: str, required: bool = True) -> tuple[str, ...]:
    if key not in data:
        if required:
            raise SpecError(f"{path}.{key}", "missing required field")
        return ()
    val = data[key]
    if not isinstance(val, list) or any(not isinstance(x, str) for x in val):
        raise SpecError(f"{path}.{key}", "must be a list of strings")
    return tuple(val)


def parse_spec(data: object) -> CanonicalStrategySpec:
    """Strict structural parse of a spec mapping (already YAML-loaded)."""
    if not isinstance(data, dict):
        raise SpecError("$", "spec must be a mapping")
    path = "$"
    strategy_id = _require(data, "strategy_id", str, path)
    if not re.fullmatch(r"STRAT-[A-Za-z0-9_-]+", strategy_id):
        raise SpecError("$.strategy_id", f"must match 'STRAT-<slug>', got {strategy_id!r}")
    family = _require(data, "family", str, path)
    if family not in FAMILIES:
        raise SpecError("$.family", f"unknown family {family!r} (allowed: {FAMILIES})")

    indicators = []
    for i, raw in enumerate(_require(data, "indicators", list, path)):
        ipath = f"$.indicators[{i}]"
        if not isinstance(raw, dict):
            raise SpecError(ipath, "indicator must be a mapping")
        name = _require(raw, "name", str, ipath)
        params = _require(raw, "parameters", dict, ipath)
        outputs = _str_list(raw, "outputs", ipath)
        indicators.append(Indicator(name, params, outputs))

    always_in = bool(data.get("always_in_market", False))
    entry = RuleTree.parse(data["entry_long"], "$.entry_long") if data.get("entry_long") else None
    exit_ = RuleTree.parse(data["exit_long"], "$.exit_long") if data.get("exit_long") else None
    if not always_in and entry is None:
        raise SpecError("$.entry_long", "required unless always_in_market: true")

    sizing = _require(data, "position_sizing", dict, path)
    if sizing.get("type") not in SIZING_TYPES:
        raise SpecError("$.position_sizing.type", f"must be one of {SIZING_TYPES}")

    return CanonicalStrategySpec(
        strategy_id=strategy_id,
        family=family,
        inputs=_str_list(data, "inputs", path),
        indicators=tuple(indicators),
        entry_long=entry,
        exit_long=exit_,
        position_sizing=sizing,
        risk=_require(data, "risk", dict, path),
        assumptions=_str_list(data, "assumptions", path),
        ambiguities=_str_list(data, "ambiguities", path, required=False),
        source_refs=_str_list(data, "source_refs", path, required=False),
        license_ref=data.get("license_ref"),
        always_in_market=always_in,
    )
