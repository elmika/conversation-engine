"""Architecture layer enforcement.

Scans every app/**/*.py file and fails if a lower layer imports from a higher one.

Layer order (lowest → highest):

  L1a   app/domain/
        app/application/ports.py
        app/application/use_cases.py

  L1b   app/application/services.py
        app/infra/

  L2    app/learning/

  API   app/api/
        app/main.py

Rule: a file in layer N may only import app.* modules that belong to layers ≤ N.
      The API / composition layer is unconstrained.

To add a new module to a layer, update _file_layer() and _module_layer() below.
"""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
APP = ROOT / "app"


# ── Layer assignment ─────────────────────────────────────────────────────────

def _file_layer(path: Path) -> str | None:
    """Return the layer label for a source file, or None if unconstrained."""
    try:
        rel = path.relative_to(APP)
    except ValueError:
        return None

    parts = rel.parts

    if parts[0] == "domain":
        return "L1a"

    if parts[0] == "application":
        stem = Path(parts[-1]).stem
        if stem in ("ports", "use_cases"):
            return "L1a"
        if stem == "services":
            return "L1b"
        return "L1a"  # any other application/ file (e.g. __init__)

    if parts[0] == "infra":
        return "L1b"

    if parts[0] == "learning":
        return "L2"

    if parts[0] == "api":
        return "API"

    if str(rel) == "main.py":
        return "API"

    return None  # settings.py, root __init__.py, etc. — unconstrained


def _module_layer(module: str) -> str | None:
    """Return the layer label for an app.* import path, or None if unconstrained."""
    if not module.startswith("app."):
        return None
    parts = module[4:].split(".")  # strip leading "app."
    if not parts or not parts[0]:
        return None

    pkg = parts[0]

    if pkg == "domain":
        return "L1a"

    if pkg == "application":
        if len(parts) < 2:
            return "L1a"
        sub = parts[1]
        if sub in ("ports", "use_cases"):
            return "L1a"
        if sub == "services":
            return "L1b"
        return "L1a"

    if pkg == "infra":
        return "L1b"

    if pkg == "learning":
        return "L2"

    if pkg == "api":
        return "API"

    return None  # settings, etc.


# ── Rules ────────────────────────────────────────────────────────────────────

ALLOWED: dict[str, set[str]] = {
    "L1a": {"L1a"},
    "L1b": {"L1a", "L1b"},
    "L2":  {"L1a", "L1b", "L2"},
    "API": {"L1a", "L1b", "L2", "API"},
}


# ── Import extraction ────────────────────────────────────────────────────────

def _app_imports(path: Path) -> list[tuple[int, str]]:
    """Return (line_no, module_path) for every app.* import in a file."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return []

    results: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("app."):
                    results.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith("app."):
                results.append((node.lineno, node.module))
    return results


# ── Test ─────────────────────────────────────────────────────────────────────

def test_layer_dependencies() -> None:
    """No lower layer may import from a higher layer."""
    violations: list[str] = []

    for py_file in sorted(APP.rglob("*.py")):
        if "__pycache__" in str(py_file):
            continue

        source_layer = _file_layer(py_file)
        if source_layer is None:
            continue

        allowed = ALLOWED[source_layer]

        for lineno, module in _app_imports(py_file):
            target_layer = _module_layer(module)
            if target_layer is None:
                continue
            if target_layer not in allowed:
                rel = py_file.relative_to(ROOT)
                violations.append(
                    f"  {rel}:{lineno}  [{source_layer}] → [{target_layer}]  import {module}"
                )

    if violations:
        pytest.fail(
            "Architecture violations — lower layers must not import from upper layers:\n"
            + "\n".join(violations)
        )
