# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""codon_closure: per codon-baseline module, the Codon-blocked features in its import closure.

A probe compile stops at the first error, so a baseline row's listed error hides what else blocks
it. This reads each nemik module's own blockers with `ast` and unions them over the nemik modules it
imports, directly or not (docs/codon-walls.md, nemik:W1411). A row whose closure holds few kinds is
cheap; one that reaches `rdflib` or the `mikemol` libraries is behind a wall. It writes nothing.

Run from the repo root: `python3 tools/codon_closure.py`.
"""

import ast
import json
import sys
from pathlib import Path

BLOCKED = frozenset(
    {
        "rdflib",
        "argparse",
        "tomllib",
        "shlex",
        "shutil",
        "subprocess",
        "dataclasses",
        "fractions",
        "hashlib",
        "weakref",
        "contextlib",
        "http",
        "xml",
        "pyshacl",
        "importlib",
        "mikemol",
        "google",
    }
)
UNSUPPORTED_NAMES = {"typing": "TYPE_CHECKING", "datetime": "UTC"}
Row = tuple[set[str], set[str]]


def _blocker_of(module: str, names: list[str]) -> str:
    """Name the blocker a `from module import names` carries, or nothing.

    Returns:
        The blocked top-level module or unsupported name, else an empty string.

    """
    top = module.split(".", 1)[0]
    if module == "collections.abc":
        return module
    if top in BLOCKED:
        return top
    unsupported = UNSUPPORTED_NAMES.get(top, "")
    if unsupported and unsupported in names:
        return f"{top}.{unsupported}"
    return ""


def own_row(text: str) -> Row:
    """Read one module's own blockers and the nemik modules it imports.

    Returns:
        (the blockers it carries itself, the nemik module names it imports).

    """
    blockers: set[str] = set()
    nemik: set[str] = set()
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.ImportFrom) and node.module:
            names = [alias.name for alias in node.names]
            if node.module == "nemik":
                nemik.update(names)
            elif node.module.startswith("nemik."):
                nemik.add(node.module.split(".")[1])
            elif found := _blocker_of(node.module, names):
                blockers.add(found)
        elif isinstance(node, ast.Import):
            blockers.update(
                alias.name.split(".")[0]
                for alias in node.names
                if alias.name.split(".")[0] in BLOCKED
            )
        elif isinstance(node, ast.ClassDef) and any(
            ast.unparse(dec).startswith(("dataclass", "dataclasses"))
            for dec in node.decorator_list
        ):
            blockers.add("@dataclass")
    return blockers, nemik


def closure(rows: dict[str, Row], start: str) -> set[str]:
    """Union the blockers of `start` and every nemik module it reaches.

    Returns:
        The blocker kinds anywhere in the import closure of `start`.

    """
    seen: set[str] = set()
    kinds: set[str] = set()
    todo = [start]
    while todo:
        name = todo.pop()
        if name in seen or name not in rows:
            continue
        seen.add(name)
        own, deps = rows[name]
        kinds.update(own)
        todo.extend(sorted(deps))
    return kinds


def report(rows: dict[str, Row], listed: list[str]) -> list[str]:
    """Say each listed module with the blockers of its closure, fewest first.

    Returns:
        One line per module: the count, the name and the kinds.

    """
    found = sorted(
        (len(kinds := closure(rows, name)), name, sorted(kinds)) for name in listed
    )
    return [f"{count} {name}: {', '.join(kinds)}" for count, name, kinds in found]


def main() -> int:
    """Print the closure report for the modules in codon-baseline.json.

    Returns:
        0, always; 2 when the baseline or the source tree is missing.

    """
    src, baseline = Path("src/nemik"), Path("codon-baseline.json")
    if not src.is_dir() or not baseline.is_file():
        sys.stderr.write("codon_closure: run from the repo root\n")
        return 2
    rows = {
        p.stem: own_row(p.read_text(encoding="utf-8"))
        for p in src.glob("*.py")
        if p.stem != "__init__"
    }
    parsed: object = json.loads(baseline.read_text(encoding="utf-8"))
    listed = sorted(str(name) for name in parsed) if isinstance(parsed, dict) else []
    sys.stdout.write("\n".join(report(rows, listed)) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
