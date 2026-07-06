"""Architecture dependency-law test (MODULE_CATALOG dependency law; REQ-004).

Scans every module under src/tios with ast and fails on imports in a forbidden
direction. Rules for ports vs domain-internals tighten once ports exist.
"""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src" / "tios"

DOMAIN = {
    "core_types",
    "dataset",
    "strategy",
    "parity",
    "experiment",
    "validation",
    "evidence",
    "approval",
    "knowledge",
    "ai_eval",
    "memory",
    "security_ops",
}


def owner_of(path: Path) -> str:
    """Module identity relative to tios: 'dataset', 'adapters.freqtrade', ..."""
    rel = path.relative_to(SRC).parts[:-1]  # drop filename
    return ".".join(rel) if rel else "<root>"


def is_forbidden(owner: str, imported: str) -> str | None:
    """Return a reason if `owner` importing `imported` breaks the dependency law."""
    if imported.split(".")[0] == "engines":
        return "src/tios must never import from engines/ (license + isolation boundary)"
    if not imported.startswith("tios"):
        return None
    target = imported.removeprefix("tios").removeprefix(".")
    top = owner.split(".")[0]
    if top == "core_types" and target and not target.startswith("core_types"):
        return "core_types depends on nothing inside tios"
    if top in DOMAIN and (target.startswith("adapters") or target.startswith("services")):
        return "domain modules never depend on adapters or services"
    if top == "adapters":
        own_adapter = ".".join(owner.split(".")[:2])
        if target.startswith("adapters") and not target.startswith(own_adapter):
            return "adapters never import each other"
    if owner.startswith("services.dashboard_ui"):
        ok = ("core_types", "services.dashboard_ui", "services.dashboard_api")
        if target and not target.startswith(ok):
            return "dashboard_ui depends only on dashboard_api (+ core_types)"
    return None


def tios_level_imports(path: Path) -> list[str]:
    """Absolute-form names of all tios/engines imports, including resolved relatives."""
    out: list[str] = []
    tree = ast.parse(path.read_text())
    pkg_parts = ["tios", *path.relative_to(SRC).parts[:-1]]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out += [a.name for a in node.names if a.name.split(".")[0] in ("tios", "engines")]
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relative: resolve against this file's package
                base = pkg_parts[: len(pkg_parts) - (node.level - 1)]
                mod = ".".join(base + ([node.module] if node.module else []))
                out.append(mod)
            elif node.module and node.module.split(".")[0] in ("tios", "engines"):
                out.append(node.module)
    return out


def violations() -> list[str]:
    found = []
    for py in sorted(SRC.rglob("*.py")):
        owner = owner_of(py)
        for imported in tios_level_imports(py):
            reason = is_forbidden(owner, imported)
            if reason:
                found.append(f"{py.relative_to(SRC.parent)}: imports {imported}: {reason}")
    return found


def test_dependency_law_holds() -> None:
    assert violations() == []


def test_checker_detects_forbidden_edges() -> None:
    """Prove the gate can fail (T-003-04 acceptance)."""
    assert is_forbidden("dataset", "tios.adapters.freqtrade")
    assert is_forbidden("core_types", "tios.dataset")
    assert is_forbidden("adapters.freqtrade", "tios.adapters.nautilus")
    assert is_forbidden("validation", "tios.services.jobs")
    assert is_forbidden("dataset", "engines.freqtrade")
    assert is_forbidden("services.dashboard_ui", "tios.evidence")
    assert not is_forbidden("dataset", "tios.core_types")
    assert not is_forbidden("adapters.freqtrade", "tios.core_types")
    assert not is_forbidden("services.dashboard_ui", "tios.services.dashboard_api")
