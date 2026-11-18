# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2261: no test builds a stdlib socket server; the page server's backlog is the one used.

socketserver listens with a backlog of 5, which a page's fan-out of piece fetches can exceed on a
loaded host (nemik:W846, W2260). nemik.serve.PageServer has the backlog the live server uses. This
reads every python file under tests/ (helpers and conftest included) with ast, resolves what each
name means through its imports from http.server and socketserver, and refuses a call to, or a
subclass of, any server class those modules export (the names ending in Server). An alias,
`from http.server import HTTPServer as S`, a module alias and `import http.server` are resolved the
same way; the text of the name is never the test. tests/fixtures/*.py is not read: it is data (a
generator script and corpus files, no server code) in a bazel package of its own, which a label
from the root package cannot name (BUILD.bazel leaves it out of the guard's inputs).
"""

import ast
import importlib
from pathlib import Path
from typing import Protocol, cast


class _Exports(Protocol):
    """A module as far as its public names are read (the stdlib types a module's attributes Any)."""

    __all__: list[str]


HERE = Path(__file__).parent
MODULES = ("http.server", "socketserver")
Meaning = dict[
    str, tuple[str, str]
]  # a bound name -> (module, attr), attr empty for a module
PLANTED = "from http.server import HTTPServer as Plain\n\nserver = Plain(('127.0.0.1', 0), None)\n"


def _servers() -> set[tuple[str, str]]:
    """List the server classes http.server and socketserver export.

    Both modules export their servers by the stdlib's own naming (HTTPServer, TCPServer,
    ThreadingHTTPServer, ForkingUDPServer, UnixStreamServer ...): every public name of the two
    modules that ends in Server, read from `__all__`, so a class the standard library adds is
    covered without a list here.

    Returns:
        (module, class name) pairs.

    """
    found: set[tuple[str, str]] = set()
    for module in MODULES:
        names = cast("_Exports", importlib.import_module(module)).__all__
        found |= {(module, name) for name in names if name.endswith("Server")}
    return found


def _stdlib_server(module: str, attr: str) -> bool:
    """Say whether `module.attr` is a stdlib server class (see _servers).

    Returns:
        True for such a class from http.server or socketserver, False for anything else.

    """
    return (module, attr) in _servers()


def _imported(tree: ast.Module) -> Meaning:
    """Map each name an import of http.server or socketserver binds, aliases included.

    Returns:
        The meaning of every such name.

    """
    meaning: Meaning = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in MODULES:
            for item in node.names:
                meaning[item.asname or item.name] = (str(node.module), item.name)
        elif isinstance(node, ast.Import):
            for item in node.names:
                if item.name in MODULES:
                    meaning[item.asname or item.name] = (item.name, "")
    return meaning


def _alias_of(
    node: ast.stmt, meaning: Meaning
) -> tuple[list[str], tuple[str, str]] | None:
    """Read a module-level `Name = Name` where the right side is a bound stdlib name.

    Returns:
        The assigned names and the meaning they take, or None for any other statement.

    """
    if not (isinstance(node, ast.Assign) and isinstance(node.value, ast.Name)):
        return None
    if node.value.id not in meaning:
        return None
    names = [t.id for t in node.targets if isinstance(t, ast.Name)]
    return names, meaning[node.value.id]


def _bindings(tree: ast.Module) -> Meaning:
    """Map every name that means a stdlib module or class: imports, then simple aliases of them.

    Returns:
        The meaning of each bound name.

    """
    meaning = _imported(tree)
    for node in tree.body:
        alias = _alias_of(node, meaning)
        if alias is not None:
            for name in alias[0]:
                meaning[name] = alias[1]
    return meaning


def _refers_to(node: ast.expr, meaning: Meaning) -> tuple[str, str] | None:
    """Resolve a Name or a module-attribute chain to (module, attr), or None when not ours.

    Returns:
        The stdlib (module, attr) the expression names, None otherwise.

    """
    if isinstance(node, ast.Name):
        return meaning.get(node.id)
    if isinstance(node, ast.Attribute):
        base = meaning.get(ast.unparse(node.value))
        if base is not None and not base[1]:
            return (base[0], node.attr)
    return None


def _used(node: ast.AST) -> list[ast.expr]:
    """Give the expressions a node builds a server from: a call's function, a class's bases.

    Returns:
        The expressions to resolve, empty for any other node.

    """
    if isinstance(node, ast.Call):
        return [node.func]
    if isinstance(node, ast.ClassDef):
        return list(node.bases)
    return []


def offenders_in(source: str) -> list[str]:
    """Name each stdlib socket server a source builds or subclasses, with its line.

    Returns:
        One `line N: module.Class` per call or subclass of a stdlib server class.

    """
    tree = ast.parse(source)
    meaning = _bindings(tree)
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call | ast.ClassDef):
            continue
        for target in _used(node):
            ref = _refers_to(target, meaning)
            if ref is not None and ref[1] and _stdlib_server(*ref):
                found.add(f"line {node.lineno}: {ref[0]}.{ref[1]}")
    return sorted(found)


def offenders(root: Path) -> dict[str, list[str]]:
    """Scan every python file under `root` for stdlib socket servers.

    Returns:
        The offending lines by file name; empty when none builds one.

    """
    bad: dict[str, list[str]] = {}
    for path in sorted(root.rglob("*.py")):
        found = offenders_in(path.read_text(encoding="utf-8"))
        if found:
            bad[str(path.relative_to(root))] = found
    return bad


def test_no_test_builds_a_stdlib_socket_server() -> None:
    """Every server a test starts is nemik.serve.PageServer: helpers and conftest are read too."""
    bad = offenders(HERE)
    assert not bad, f"use nemik.serve.PageServer: {bad}"


def test_an_aliased_import_a_module_attribute_and_a_subclass_are_caught(
    tmp_path: Path,
) -> None:
    """The planted offenders a text match would miss: an alias, a module attribute, a subclass."""
    (tmp_path / "aliased.py").write_text(PLANTED, encoding="utf-8")
    (tmp_path / "attribute.py").write_text(
        "import http.server as hs\n\nserver = hs.ThreadingHTTPServer(('', 0), None)\n",
        encoding="utf-8",
    )
    (tmp_path / "subclass.py").write_text(
        "from socketserver import TCPServer\n\n\nclass Mine(TCPServer):\n    pass\n",
        encoding="utf-8",
    )
    (tmp_path / "fine.py").write_text(
        "from http.server import BaseHTTPRequestHandler\n\nhandler = BaseHTTPRequestHandler\n",
        encoding="utf-8",
    )
    assert sorted(offenders(tmp_path)) == ["aliased.py", "attribute.py", "subclass.py"]
