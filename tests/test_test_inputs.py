"""nemik:W475: every repo file a test opens by path is a declared input of the bazel test.

A test that opens `src/nemik/web/index.html` by path passes on the host and fails in the gate, whose
sandbox holds only the declared data (nemik:W467 lost a commit to it). This reads each test's path
expressions (`ROOT / "a/b"`, `Path(__file__).parent / "x" / "y"`) and checks each against the data
list in BUILD.bazel. A package file is read through importlib.resources instead.
"""

import ast
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
HINT = (
    "not a declared bazel input (add it to BUILD.bazel's data, or read a package file"
    " with importlib.resources):\n"
)


def _base(node: ast.expr) -> str | None:
    """The repo-relative directory an expression names, or None when it is not a known base."""
    if isinstance(node, ast.Name) and node.id == "ROOT":
        return ""
    text = ast.unparse(node)
    if re.fullmatch(r"Path\(__file__\)(\.resolve\(\))?\.parents\[1\]", text):
        return ""
    if re.fullmatch(r"Path\(__file__\)(\.resolve\(\))?\.parent", text):
        return "tests"
    return None


def _paths(source: str) -> set[str]:
    """Every repo-relative path a module builds from a known base and string parts."""
    found: set[str] = set()
    inner: set[int] = (
        set()
    )  # the left operand of a longer chain: read as part of that chain only
    for node in ast.walk(ast.parse(source)):
        if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)):
            continue
        inner.add(id(node.left))
        if id(node) in inner:
            continue
        parts: list[str] = []
        left: ast.expr = node
        while isinstance(left, ast.BinOp) and isinstance(left.op, ast.Div):
            right = left.right
            if not (isinstance(right, ast.Constant) and isinstance(right.value, str)):
                parts = []
                break
            parts.insert(0, right.value)
            left = left.left
        base = _base(left)
        if parts and base is not None:
            found.add("/".join(p for p in (base, *parts) if p))
    return found


def _declared() -> tuple[set[str], list[str]]:
    """The test macro's data: exact files, and directory prefixes (globs and fixture packages)."""
    build = (REPO / "BUILD.bazel").read_text()
    # only the test macro's own data list (up to its env): the venv's srcs glob is not test data
    data = build.split("data = [", 1)[1].split("env = {", 1)[0]
    files = set(re.findall(r'"([\w./-]+\.[\w]+|[\w./-]+/[\w.-]+|Containerfile)"', data))
    # every pattern of every glob([...]): its directory part, up to the first wildcard, is a covered prefix
    prefixes = [
        item.split("*")[0]
        for group in re.findall(r"glob\(\[([^\]]*)\]", data)
        for item in re.findall(r'"([^"]+)"', group)
    ]
    pkgs = re.findall(r'"//([\w/]+):(\w+)"', data)
    prefixes += [f"{pkg}/{name}/" for pkg, name in pkgs]
    return files, prefixes


def _covered(path: str, files: set[str], prefixes: list[str]) -> bool:
    if path in files:
        return True
    return any(f"{path}/".startswith(p) or path.startswith(p) for p in prefixes)


def test_paths_are_declared_inputs() -> None:
    files, prefixes = _declared()
    missing = []
    for test in sorted(HERE.glob("test_*.py")):
        for path in sorted(_paths(test.read_text())):
            if not _covered(path, files, prefixes):
                missing.append(f"{test.name}: {path}")
    assert not missing, HINT + "\n".join(missing)


def test_the_reader_finds_the_index_html_case() -> None:
    # the expression that cost W467 its commit, before the fix
    src = 'PAGE = Path(__file__).parents[1] / "src" / "nemik" / "web" / "index.html"\n'
    assert _paths(src) == {"src/nemik/web/index.html"}
    files, prefixes = _declared()
    assert not _covered("src/nemik/web/index.html", files, prefixes)
