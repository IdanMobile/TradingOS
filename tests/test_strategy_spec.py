"""T-005-01/02 acceptance: property tests on rule trees, malformed fixtures
rejected with precise errors, spec-hash stability, SV immutability."""

import dataclasses

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tios.strategy.spec import Comparison, RuleTree, SpecError, parse_spec
from tios.strategy.validator import validate, validate_yaml
from tios.strategy.version import create_version

VALID_SPEC: dict[str, object] = {
    "strategy_id": "STRAT-test-ma-cross",
    "family": "trend_following",
    "inputs": ["close"],
    "indicators": [
        {
            "name": "sma",
            "parameters": {"window": 3},
            "outputs": ["sma_fast"],
        },
        {
            "name": "sma",
            "parameters": {"window": 5},
            "outputs": ["sma_slow"],
        },
    ],
    "entry_long": {"all": ["sma_fast > sma_slow"]},
    "exit_long": {"any": ["sma_fast < sma_slow"]},
    "position_sizing": {"type": "fixed_fraction", "fraction": 1.0},
    "risk": {"stop_loss": None, "take_profit": None},
    "assumptions": [
        "signal evaluated at bar close; execution at next bar open",
        "warm-up: first 5 bars produce no signals (longest indicator window)",
    ],
    "ambiguities": [],
}


# ---------- property tests: rule trees ----------

identifiers = st.from_regex(r"[a-z_][a-z0-9_]{0,10}", fullmatch=True)
numbers = st.integers(-1000, 1000).map(str)
operands = st.one_of(identifiers, numbers)
ops = st.sampled_from(["<", "<=", ">", ">=", "==", "!="])
comparison_strs = st.builds(lambda a, o, b: f"{a} {o} {b}", operands, ops, operands)


def rule_nodes() -> st.SearchStrategy[dict[str, list[object]]]:
    return st.recursive(
        st.builds(
            lambda kind, kids: {kind: kids},
            st.sampled_from(["all", "any"]),
            st.lists(comparison_strs, min_size=1, max_size=4),
        ),
        lambda children: st.builds(
            lambda kind, kids: {kind: kids},
            st.sampled_from(["all", "any"]),
            st.lists(st.one_of(comparison_strs, children), min_size=1, max_size=4),
        ),
        max_leaves=12,
    )


@given(rule_nodes())
def test_rule_tree_roundtrip(node: dict[str, list[object]]) -> None:
    tree = RuleTree.parse(node, "$")
    again = RuleTree.parse(tree.to_obj(), "$")
    assert again == tree


@given(comparison_strs)
def test_comparison_parse_never_crashes_on_generated(expr: str) -> None:
    c = Comparison.parse(expr, "$")
    assert c.op in ("<", "<=", ">", ">=", "==", "!=")
    assert Comparison.parse(c.to_obj(), "$") == c


@pytest.mark.parametrize(
    ("bad", "path_fragment"),
    [
        ({"nor": ["a < b"]}, "unknown rule combinator"),
        ({"all": []}, "non-empty"),
        ({"all": ["close <> open"]}, "not a valid comparison"),
        ({"all": ["close < open"], "any": ["a < b"]}, "single-key"),
        ("close < open", "single-key mapping"),
    ],
)
def test_malformed_rule_trees_rejected_precisely(bad: object, path_fragment: str) -> None:
    with pytest.raises(SpecError, match=path_fragment):
        RuleTree.parse(bad, "$.entry_long")


# ---------- schema/completeness fixtures ----------


def test_valid_spec_passes() -> None:
    assert validate(VALID_SPEC).verdict == "VALID"


def test_ambiguities_change_verdict() -> None:
    spec = dict(VALID_SPEC, ambiguities=["source did not state order type"])
    assert validate(spec).verdict == "VALID_WITH_AMBIGUITIES"


@pytest.mark.parametrize(
    ("mutation", "error_fragment"),
    [
        ({"strategy_id": "bogus"}, "STRAT-"),
        ({"family": "astrology"}, "unknown family"),
        ({"entry_long": None, "always_in_market": False}, "entry_long"),
        ({"position_sizing": {"type": "martingale"}}, "position_sizing.type"),
        ({"inputs": ["sentiment_score"]}, "not resolvable against dataset schema"),
        ({"entry_long": {"all": ["mystery_signal > 0"]}}, "unresolvable identifiers"),
        ({"assumptions": ["warm-up: 5 bars"]}, "signal timing"),
        ({"assumptions": ["signal evaluated at bar close"]}, "warm-up"),
        (
            {"indicators": [{"name": "sma", "parameters": {}, "outputs": ["sma_fast"]}]},
            "parameters must be explicit",
        ),
    ],
)
def test_broken_specs_rejected_with_precise_errors(
    mutation: dict[str, object], error_fragment: str
) -> None:
    report = validate(dict(VALID_SPEC, **mutation))
    assert report.verdict == "INVALID"
    assert any(error_fragment in e for e in report.errors), report.errors


def test_exit_path_required_unless_risk_exit() -> None:
    no_exit = dict(VALID_SPEC)
    del no_exit["exit_long"]
    no_exit["exit_long"] = None
    assert validate(no_exit).verdict == "INVALID"
    with_stop = dict(no_exit, risk={"stop_loss": 0.05, "take_profit": None})
    assert validate(with_stop).verdict == "VALID"


def test_yaml_entrypoint_rejects_garbage() -> None:
    assert validate_yaml(": not: valid: yaml: [").verdict == "INVALID"


# ---------- hashing + SV immutability ----------


def test_spec_hash_stable_and_sensitive() -> None:
    a = parse_spec(VALID_SPEC)
    b = parse_spec(VALID_SPEC)
    assert a.spec_hash() == b.spec_hash()
    changed = parse_spec(dict(VALID_SPEC, family="mean_reversion"))
    assert changed.spec_hash() != a.spec_hash()


def test_strategy_version_is_immutable() -> None:
    sv = create_version(parse_spec(VALID_SPEC), {"window_fast": 3, "window_slow": 5})
    with pytest.raises(dataclasses.FrozenInstanceError):
        sv.spec_hash = "tampered"  # type: ignore[misc]
    with pytest.raises(TypeError):
        sv.resolved_parameters["window_fast"] = 99  # type: ignore[index]


def test_same_content_same_sv_id_new_params_new_sv() -> None:
    spec = parse_spec(VALID_SPEC)
    a = create_version(spec, {"w": 3})
    b = create_version(spec, {"w": 3})
    c = create_version(spec, {"w": 4})
    assert a.sv_id == b.sv_id  # identity is content
    assert a.sv_id != c.sv_id  # any change => new SV
