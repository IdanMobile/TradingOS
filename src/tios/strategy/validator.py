"""Canonical spec validator (T-005-01; SKILL_CANONICAL_SPEC_VALIDATOR steps 1–2).

Step 1 (schema) is `parse_spec` — mechanical structure. Step 2 (completeness)
lives here. Verdicts: VALID / VALID_WITH_AMBIGUITIES / INVALID. The validator
never fixes a spec (validator ≠ author).
"""

from __future__ import annotations

from dataclasses import dataclass

import yaml

from tios.strategy.spec import CanonicalStrategySpec, SpecError, parse_spec

# Canonical dataset columns rules may reference (spec §schema) besides indicator outputs
DATASET_IDENTIFIERS = frozenset(
    {"open", "high", "low", "close", "volume_base", "quote_volume", "trade_count"}
)


@dataclass(frozen=True)
class ValidationReport:
    verdict: str  # VALID | VALID_WITH_AMBIGUITIES | INVALID
    errors: tuple[str, ...]
    ambiguities: tuple[str, ...]


def completeness_errors(spec: CanonicalStrategySpec) -> list[str]:
    errors: list[str] = []

    for ind in spec.indicators:
        if not ind.parameters:
            errors.append(f"indicator {ind.name!r}: parameters must be explicit (non-empty)")
        if not ind.outputs:
            errors.append(f"indicator {ind.name!r}: outputs must be declared")

    if spec.entry_long is not None and spec.exit_long is None and not _has_risk_exit(spec):
        errors.append("entry_long has no exit path: define exit_long or a risk stop/take-profit")

    available = spec.available_identifiers() | DATASET_IDENTIFIERS
    for tree_name in ("entry_long", "exit_long"):
        tree = getattr(spec, tree_name)
        if tree is None:
            continue
        unknown = sorted(tree.identifiers() - available)
        if unknown:
            errors.append(
                f"{tree_name} references unresolvable identifiers {unknown} "
                f"(not in inputs, indicator outputs, or dataset schema)"
            )

    unknown_inputs = sorted(set(spec.inputs) - DATASET_IDENTIFIERS)
    if unknown_inputs:
        errors.append(f"inputs not resolvable against dataset schema: {unknown_inputs}")

    if not any("warm-up" in a or "warmup" in a for a in spec.assumptions):
        errors.append("assumptions must state indicator warm-up handling explicitly")
    if not any("bar close" in a or "bar open" in a for a in spec.assumptions):
        errors.append("assumptions must state signal timing (evaluated at bar close/open)")

    return errors


def _has_risk_exit(spec: CanonicalStrategySpec) -> bool:
    return any(spec.risk.get(k) not in (None, "null") for k in ("stop_loss", "take_profit"))


def validate(data: object) -> ValidationReport:
    try:
        spec = parse_spec(data)
    except SpecError as e:
        return ValidationReport("INVALID", (str(e),), ())
    errors = completeness_errors(spec)
    if errors:
        return ValidationReport("INVALID", tuple(errors), spec.ambiguities)
    if spec.ambiguities:
        return ValidationReport("VALID_WITH_AMBIGUITIES", (), spec.ambiguities)
    return ValidationReport("VALID", (), ())


def validate_yaml(text: str) -> ValidationReport:
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        return ValidationReport("INVALID", (f"$: YAML parse error: {e}",), ())
    return validate(data)
