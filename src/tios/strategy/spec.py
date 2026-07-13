"""CanonicalStrategySpec model (T-005-01, REQ-011; TYPE_AND_CONTRACT_CATALOG §2).

Framework-neutral strategy spec: rule trees are `all:`/`any:` boolean composition
over comparison expressions. Parsing is strict — any structural problem raises
SpecError with a precise path. Hashing is canonical-JSON sha256.
"""

from __future__ import annotations

import hashlib
import json
import math
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
    "calendar",
    "funding_pressure",
    "transaction_activity",
    "carry",
    "market_making",
    "arbitrage",
    "buy_and_hold",
    "other",
)
SIZING_TYPES = ("fixed_fraction", "fixed_amount", "all_in")
LEG_SIDES = ("LONG", "SHORT")


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
class StrategyLeg:
    """Research description of one leg; it carries no order semantics."""

    instrument: str
    side: str
    role: str
    notional_fraction: float | int
    execution_assumptions: tuple[str, ...]

    def to_obj(self) -> dict[str, Any]:
        return {
            "instrument": self.instrument,
            "side": self.side,
            "role": self.role,
            "notional_fraction": self.notional_fraction,
            "execution_assumptions": list(self.execution_assumptions),
        }


@dataclass(frozen=True)
class MultiLegResearchSpec:
    """Non-executable shared eligibility and leg descriptions for research."""

    research_only: bool
    shared_entry_eligibility: RuleTree
    shared_exit_eligibility: RuleTree | None
    legs: tuple[StrategyLeg, ...]

    def to_obj(self) -> dict[str, Any]:
        return {
            "research_only": self.research_only,
            "shared_entry_eligibility": self.shared_entry_eligibility.to_obj(),
            "shared_exit_eligibility": (
                self.shared_exit_eligibility.to_obj() if self.shared_exit_eligibility else None
            ),
            "legs": [leg.to_obj() for leg in self.legs],
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
    multi_leg: MultiLegResearchSpec | None = None

    def available_identifiers(self) -> set[str]:
        out = set(self.inputs)
        for ind in self.indicators:
            out |= set(ind.outputs)
        return out

    def to_obj(self) -> dict[str, Any]:
        obj = {
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
        # Preserve the canonical JSON (and therefore hashes) of legacy specs.
        if self.multi_leg is not None:
            obj["multi_leg"] = self.multi_leg.to_obj()
        return obj

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


def _parse_multi_leg(data: dict[str, Any]) -> MultiLegResearchSpec | None:
    raw = data.get("multi_leg")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise SpecError("$.multi_leg", "must be a mapping")
    if raw.get("research_only") is not True:
        raise SpecError("$.multi_leg.research_only", "must be true")

    raw_legs = _require(raw, "legs", list, "$.multi_leg")
    if len(raw_legs) < 2:
        raise SpecError("$.multi_leg.legs", "must contain at least two legs")
    legs: list[StrategyLeg] = []
    roles: set[str] = set()
    for index, raw_leg in enumerate(raw_legs):
        path = f"$.multi_leg.legs[{index}]"
        if not isinstance(raw_leg, dict):
            raise SpecError(path, "leg must be a mapping")
        instrument = _require(raw_leg, "instrument", str, path)
        if not instrument.strip():
            raise SpecError(f"{path}.instrument", "must be non-empty")
        side = _require(raw_leg, "side", str, path)
        if side not in LEG_SIDES:
            raise SpecError(f"{path}.side", f"must be one of {LEG_SIDES}")
        role = _require(raw_leg, "role", str, path)
        if not re.fullmatch(_IDENT, role):
            raise SpecError(f"{path}.role", "must be a lower_snake identifier")
        if role in roles:
            raise SpecError(f"{path}.role", f"duplicate role {role!r}")
        roles.add(role)
        notional = raw_leg.get("notional_fraction")
        if (
            isinstance(notional, bool)
            or not isinstance(notional, (float, int))
            or not math.isfinite(float(notional))
            or notional <= 0
        ):
            raise SpecError(f"{path}.notional_fraction", "must be a positive finite number")
        assumptions = _str_list(raw_leg, "execution_assumptions", path)
        if not assumptions or any(not assumption.strip() for assumption in assumptions):
            raise SpecError(f"{path}.execution_assumptions", "must contain non-empty strings")
        legs.append(StrategyLeg(instrument, side, role, notional, assumptions))

    return MultiLegResearchSpec(
        research_only=True,
        shared_entry_eligibility=RuleTree.parse(
            _require(raw, "shared_entry_eligibility", dict, "$.multi_leg"),
            "$.multi_leg.shared_entry_eligibility",
        ),
        shared_exit_eligibility=(
            RuleTree.parse(raw["shared_exit_eligibility"], "$.multi_leg.shared_exit_eligibility")
            if raw.get("shared_exit_eligibility") is not None
            else None
        ),
        legs=tuple(legs),
    )


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

    multi_leg = _parse_multi_leg(data)
    always_in = bool(data.get("always_in_market", False))
    entry = RuleTree.parse(data["entry_long"], "$.entry_long") if data.get("entry_long") else None
    exit_ = RuleTree.parse(data["exit_long"], "$.exit_long") if data.get("exit_long") else None
    if multi_leg is not None:
        if always_in:
            raise SpecError("$.always_in_market", "cannot be true for a multi-leg research spec")
        if entry is not None or exit_ is not None:
            raise SpecError(
                "$.multi_leg",
                "cannot be combined with directional entry_long or exit_long rules",
            )
    elif not always_in and entry is None:
        raise SpecError("$.entry_long", "required unless always_in_market or multi_leg is set")

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
        multi_leg=multi_leg,
    )
