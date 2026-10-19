# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W718: every nemik module a module imports exists in the package the wheel is built from.

A half-updated install once had a blocks.py importing nemik.index, a module the install did not
carry (the fleet's warnings went dark). hatchling packages everything under src/nemik, so the
packaging itself holds; what this checks is the other side: that no module imports a nemik module
that is not in the tree, at the top of a file or inside a function.
"""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "nemik"


def _modules() -> set[str]:
    """List the module names the package carries.

    Returns:
        The stem of every .py file directly under src/nemik.

    """
    return {path.stem for path in SRC.glob("*.py")}


def _imported(tree: ast.AST) -> set[str]:
    """List the nemik submodules a parsed file imports.

    Args:
        tree: A parsed module.

    Returns:
        The first name after `nemik.` in each `import nemik.x` and `from nemik.x import y`, and
        each name `y` in `from nemik import y`.

    """
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            parts = (node.module or "").split(".")
            if parts[0] == "nemik" and node.level == 0:
                if len(parts) > 1:
                    found.add(parts[1])
                else:
                    found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                if parts[0] == "nemik" and len(parts) > 1:
                    found.add(parts[1])
    return found


def test_every_imported_nemik_module_exists() -> None:
    """No file imports a nemik module the tree does not carry."""
    have = _modules()
    missing = {
        f"{path.name} imports nemik.{name}"
        for path in sorted(SRC.glob("*.py"))
        for name in _imported(ast.parse(path.read_text(encoding="utf-8")))
        if name not in have and not (SRC / name).is_dir()
    }
    assert not missing, "\n".join(sorted(missing))


def test_a_missing_import_is_named() -> None:
    """The scan sees an import inside a function, as the failing one was."""
    tree = ast.parse("def f():\n    from nemik.index import index\n")
    assert _imported(tree) == {"index"}
