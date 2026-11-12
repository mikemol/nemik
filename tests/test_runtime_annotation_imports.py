# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2125: a module whose annotations are read at run time is never imported only for typing.

At 3.14 an annotation is evaluated lazily, and inspect.signature evaluates it when asked. Pluggy
does that for a pytest hook and Playwright does it for a route or event handler, so a name those
libraries meet in an annotation must be a real import. ruff-house.toml lists such modules in
[lint.flake8-type-checking] exempt-modules, so the lint never moves their imports under
`if TYPE_CHECKING:`; this test holds the files that hand callables to them to it, so a hand edit
cannot put one back. The first instance: a route handler typed `route: Route` with Route under the
guard raised NameError inside Playwright's dispatch and test_layout shard 2 waited the whole 900 s
(measured 2026-11-10). The files are named, and so are the BUILD inputs: a new file that passes a
handler to Playwright is added to HANDLERS and to the target's data in the same change.
"""

import ast
import tomllib
from pathlib import Path

from nemik.tomlview import strings, table

HERE = Path(__file__).absolute().parents[1]
HANDLERS = (
    "tests/test_layout.py",
    "tests/test_pdf_load_retry.py",
    "tests/webpage.py",
    "tests/conftest.py",
)


def _exempt() -> list[str]:
    """Read the exempt modules from the house lint config.

    Returns:
        The module names ruff-house.toml never moves under TYPE_CHECKING.

    """
    doc: dict[str, object] = tomllib.loads(
        (HERE / "ruff-house.toml").read_text(encoding="utf-8")
    )
    lint = table(doc.get("lint"))
    return strings(table(lint.get("flake8-type-checking")).get("exempt-modules"))


def _guarded(tree: ast.Module) -> list[str]:
    """Name every module imported inside a module-level `if TYPE_CHECKING:`.

    Returns:
        The top-level package of each import in such a block.

    """
    names: list[str] = []
    for node in tree.body:
        if not (isinstance(node, ast.If) and isinstance(node.test, ast.Name)):
            continue
        if node.test.id != "TYPE_CHECKING":
            continue
        for stmt in node.body:
            if isinstance(stmt, ast.ImportFrom):
                names.append((stmt.module or "").split(".")[0])
            elif isinstance(stmt, ast.Import):
                names.extend(a.name.split(".")[0] for a in stmt.names)
    return names


def test_the_exempt_modules_name_the_libraries_that_read_annotations() -> None:
    """Keep playwright and pytest on the list, with typing."""
    assert {"typing", "pytest", "playwright"} <= set(_exempt())


def test_no_run_time_reader_sees_a_name_that_exists_only_for_the_type_checker() -> None:
    """Find no named file that guards playwright, or pytest in the conftest that holds the hooks.

    Pytest reads a test function's annotations without evaluating them (the suite passes with
    `pytest` guarded in many tests), so only its hooks in conftest.py are held to this.
    """
    found: list[str] = []
    for name in HANDLERS:
        path = HERE / name
        tree = ast.parse(path.read_text(encoding="utf-8"))
        found.extend(
            f"{name}: {module}"
            for module in _guarded(tree)
            if module == "playwright"
            or (module == "pytest" and path.name == "conftest.py")
        )
    assert found == []
