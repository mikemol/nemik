# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
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
    """Give the repo-relative directory an expression names, or None for an unknown base.

    Returns:
        '' for the repo root, 'tests' for the tests directory, else None.

    """
    if isinstance(node, ast.Name) and node.id == "ROOT":
        return ""
    text = ast.unparse(node)
    if re.fullmatch(r"Path\(__file__\)(\.resolve\(\))?\.parents\[1\]", text):
        return ""
    if re.fullmatch(r"Path\(__file__\)(\.resolve\(\))?\.parent", text):
        return "tests"
    return None


def _paths(source: str) -> set[str]:
    """Every repo-relative path a module builds from a known base and string parts.

    Returns:
        The paths found.

    """
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


def _strings(pattern: str, text: str) -> list[str]:
    """Give every match of a one-group pattern.

    Returns:
        The matched groups, as `re.findall` returns them.

    """
    found: list[str] = re.findall(pattern, text)
    return found


def _declared() -> tuple[set[str], list[str]]:
    """Give the test macro's data: exact files and directory prefixes (globs, fixtures).

    Returns:
        The exact files, and the directory prefixes.

    """
    build = (REPO / "BUILD.bazel").read_text()
    # only the test macro's own data list (up to its env): the venv's srcs glob is not test data
    data = build.split("data = [", 1)[1].split("env = {", 1)[0]
    files = set(_strings(r'"([\w./-]+\.[\w]+|[\w./-]+/[\w.-]+|Containerfile)"', data))
    # every pattern of every glob([...]): a trailing `**` covers a directory, any other pattern its
    # matches
    patterns = [
        item
        for group in _strings(r"glob\(\[([^\]]*)\]", data)
        for item in _strings(r'"([^"]+)"', group)
    ]
    prefixes = [item.split("*")[0] for item in patterns if item.endswith("**")]
    files |= {item for item in patterns if not item.endswith("**")}
    pkgs: list[tuple[str, str]] = re.findall(r'"//([\w/]+):([\w.-]+)"', data)
    prefixes += [f"{pkg}/{name}/" for pkg, name in pkgs]
    return files, prefixes


def _glob(pattern: str) -> re.Pattern[str]:
    """Translate a BUILD glob pattern to a regex.

    Returns:
        A pattern where `**` crosses directories and `*` stays within one.

    """
    return re.compile(re.escape(pattern).replace(r"\*\*", ".*").replace(r"\*", "[^/]*"))


def _covered(path: str, files: set[str], prefixes: list[str]) -> bool:
    if path in files or any(
        _glob(item).fullmatch(path) for item in files if "*" in item
    ):
        return True
    # a directory some declared glob reaches into
    if any(item.startswith(f"{path}/") for item in files):
        return True
    return any(f"{path}/".startswith(p) or path.startswith(p) for p in prefixes)


def test_paths_are_declared_inputs() -> None:
    """Paths are declared inputs."""
    files, prefixes = _declared()
    missing: list[str] = []
    for test in sorted(HERE.glob("test_*.py")):
        missing.extend(
            f"{test.name}: {path}"
            for path in sorted(_paths(test.read_text()))
            if not _covered(path, files, prefixes)
        )
    assert not missing, HINT + "\n".join(missing)


def test_the_reader_finds_the_index_html_case() -> None:
    """The reader finds the index html case."""
    # the expression that cost W467 its commit, before the fix
    src = 'PAGE = Path(__file__).parents[1] / "src" / "nemik" / "web" / "index.html"\n'
    assert _paths(src) == {"src/nemik/web/index.html"}
    files, prefixes = _declared()
    assert not _covered("src/nemik/web/index.html", files, prefixes)


# nemik:W1549: a test that imports a tools/ module by name needs the module in its bazel data.
# Direct pytest cannot see the gap (the repo's pytest pythonpath reaches tools/); the gate's
# sandbox holds only the declared data, so stack 915 was refused for it (R185).
GLOBAL_DATA = "data = [src,"  # the line of data every test target gets


def _tool_imports(source: str, tools: set[str]) -> set[str]:
    """Name the tools/ modules a test imports.

    Args:
        source: The test's text.
        tools: The stems of the files in tools/.

    Returns:
        The stems of the tools modules it imports, at any depth.

    """
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            names.add(node.module.split(".")[0])
    return names & tools


def _unfed(build: str, test: str, modules: set[str]) -> list[str]:
    """Name the tools modules a test imports that its bazel target does not carry.

    Args:
        build: BUILD.bazel's text.
        test: The test file, as `tests/test_x.py`.
        modules: The stems of the tools modules the test imports.

    Returns:
        The `tools/<stem>.py` paths neither on the global data line nor on a line that also names
        this test, sorted.

    """
    lines = build.splitlines()
    missing: list[str] = []
    for module in sorted(modules):
        tool = f'"tools/{module}.py"'
        fed = any(
            tool in line
            and (line.lstrip().startswith(GLOBAL_DATA) or f'"{test}"' in line)
            for line in lines
        )
        if not fed:
            missing.append(tool.strip('"'))
    return missing


def test_a_test_that_imports_a_tools_module_declares_it_as_data() -> None:
    """Every tools/ import in a test has a BUILD.bazel data entry under that test's name."""
    tools = {p.stem for p in (REPO / "tools").glob("*.py")} - {
        p.stem for p in HERE.glob("*.py")
    }
    build = (REPO / "BUILD.bazel").read_text()
    missing: list[str] = []
    for test in sorted(HERE.glob("test_*.py")):
        modules = _tool_imports(test.read_text(), tools)
        missing.extend(
            f"tests/{test.name}: {path}"
            for path in _unfed(build, f"tests/{test.name}", modules)
        )
    hint = "imports a tools module BUILD.bazel gives it no data for:\n"
    assert not missing, hint + "\n".join(missing)


def test_an_entry_removed_from_build_bazel_is_caught() -> None:
    """The planted case: an entry present passes, absent is named, a global one covers all."""
    entry = (
        '+ (["tools/diff_harness.py"] if src == "tests/test_diff_harness.py" else [])'
    )
    test = "tests/test_diff_harness.py"
    assert _unfed(f"x\n{entry}\ny\n", test, {"diff_harness"}) == []
    assert _unfed("x\ny\n", test, {"diff_harness"}) == ["tools/diff_harness.py"]
    other = entry.replace("test_diff_harness", "test_other")
    assert _unfed(other, test, {"diff_harness"}) == ["tools/diff_harness.py"]
    glob = 'data = [src, "tools/cpuline.py", "x"]'
    assert _unfed(glob, test, {"cpuline"}) == []


def test_the_reader_names_only_tools_modules_a_test_imports() -> None:
    """Both import forms count, a nested import counts, stdlib and package imports do not."""
    src = "import os\nfrom nemik import x\nfrom diff_harness import main\n"
    src += "def f():\n    import codon_census\n"
    found = _tool_imports(src, {"diff_harness", "codon_census", "unused"})
    assert found == {"diff_harness", "codon_census"}
