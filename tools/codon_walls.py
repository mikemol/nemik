# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2077: the wall incidence of src/nemik, the ratchet that lets a codon paydown be counted.

codon-baseline.json falls only when a whole module compiles, so a change that removes one of the
many things Codon refuses lowers nothing it counts. This pass measures at the grain the work
removes. A WALL is something the pinned Codon refuses: an import it cannot compile, or one of a few
constructs. Each module's walls are the walls in its own text and in the static import closure of
the nemik modules it imports (function-level and relative imports included, subpackages included).
`codon-walls.json` lists them as {module: {wall: "reached"}}, so the ratchet's value, the leaves of
that file, is the number of (module, wall) pairs. Removing a wall from a module many others reach
lowers many modules' pairs; a wall moved into an adapter that is still reached lowers nothing for
the modules reaching it. A module is named by its dotted path under src/nemik (`core.x`); a
package's `__init__` is the package's name, and the root `__init__` is `nemik`.

THE TABLE (codon-wall-table.json) holds the import lines the compiler accepted. An import line not
in it counts as a wall, so an unprobed line can only raise the incidence, never hide a wall. The
compiler probes every distinct import line (`probe`), and the test refuses a table that disagrees.

THE RATCHET IS THE ONLY GATE. codon-walls.json is a registered ratchet (ratchets.json), so the
ratchet machinery refuses a rise against HEAD, and a rise is allowed only as a declared rebaseline
(rebaselines.json: ratchet, old, new, reason, and the operator's record). A wall found hidden
behind another (the table grew) is such a rise. This tool keeps no second record of its own and
only says whether the file matches a fresh measurement. A gain in one module that nets to zero
against a fall in another claims no fall, so the total stays honest (github-14, 2026-11-08).

Run `python3 tools/codon_walls.py` to check, `--write` to record, `--probe CODON` to rebuild the
table with the pinned compiler. It lives in tools/, not src/nemik, so the census does not count it
as a module that fails to compile.
"""

import argparse
import ast
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import NamedTuple, cast

from mikemol.procrun.proc import capture

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "nemik"
WALLS_FILE = "codon-walls.json"
TABLE_FILE = "codon-wall-table.json"
DYNAMIC = "dynamic import call"
BARE_STAR = "bare '*,' keyword-only marker"
CLASS_CALL = "class decorator with arguments"
TYPE_CHECKING = "TYPE_CHECKING"
STDLIB_SPLIT = {"importlib", "urllib", "collections", "xml", "http", "dataclasses"}
FAMILY = "mikemol.* (third-party)"
NAME_PARTS = 2
DYNAMIC_NAMES = {"__import__", "import_module"}

Ref = tuple[str, str]
Pairs = dict[str, dict[str, str]]
Measured = dict[str, list[str]]


class Facts(NamedTuple):
    """What one module's text says: its external import lines, nemik references and constructs."""

    imports: frozenset[str]
    nemik: frozenset[Ref]
    constructs: frozenset[str]


class Options(argparse.Namespace):
    """The parsed command line of tools/codon_walls.py."""

    root: Path
    write: bool
    probe: Path | None


def group(line: str) -> str:
    """Name the wall an import line belongs to: the package, not each name from it.

    Args:
        line: An import line such as `from importlib.metadata import version`.

    Returns:
        The wall's label.

    """
    parts = line.split()
    module = parts[1]
    top = module.split(".")[0]
    if module == "typing":
        label = TYPE_CHECKING if parts[-1] == TYPE_CHECKING else f"typing.{parts[-1]}"
    elif top in STDLIB_SPLIT:
        dotted = ".".join(module.split(".")[:NAME_PARTS])
        label = dotted if "." in module else f"{module}.{parts[-1]}"
        label = label if parts[0] == "from" or "." in module else module
    elif top == "mikemol":
        label = FAMILY
    else:
        label = top
    return label


def _from_base(node: ast.ImportFrom, pkg: tuple[str, ...]) -> tuple[str, ...] | None:
    # The package path a from-import names under src/nemik; None when it leaves the package.
    module = tuple(node.module.split(".")) if node.module else ()
    if node.level:
        if node.level - 1 > len(pkg):
            return None
        return pkg[: len(pkg) - (node.level - 1)] + module
    if module[:1] == (PACKAGE,):
        return module[1:]
    return None


def _imports(node: ast.AST, pkg: tuple[str, ...]) -> tuple[set[str], set[Ref]]:
    # The external import lines and the nemik (base, name) references one statement holds.
    external: set[str] = set()
    inside: set[Ref] = set()
    if isinstance(node, ast.Import):
        for alias in node.names:
            parts = alias.name.split(".")
            if parts[0] == PACKAGE:
                inside.add((".".join(parts[1:]), ""))
            else:
                external.add(f"import {alias.name}")
    elif isinstance(node, ast.ImportFrom):
        base = _from_base(node, pkg)
        if base is not None:
            inside.update((".".join(base), alias.name) for alias in node.names)
        elif node.module and node.module != "__future__":
            external.update(
                f"from {node.module} import {alias.name}" for alias in node.names
            )
    return external, inside


def _is_dynamic(node: ast.Call) -> bool:
    # A call that imports by a computed name: __import__(), import_module(), x.import_module().
    func = node.func
    named = isinstance(func, ast.Name) and func.id in DYNAMIC_NAMES
    return named or (isinstance(func, ast.Attribute) and func.attr == "import_module")


def _constructs(node: ast.AST) -> set[str]:
    # The constructs on the wall list that one node is.
    found: set[str] = set()
    if isinstance(node, ast.ClassDef):
        found.update(CLASS_CALL for d in node.decorator_list if isinstance(d, ast.Call))
    elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
        if node.args.kwonlyargs and node.args.vararg is None:
            found.add(BARE_STAR)
    elif isinstance(node, ast.Call) and _is_dynamic(node):
        found.add(DYNAMIC)
    return found


def _guarded(tree: ast.AST) -> tuple[set[int], set[str]]:
    # The ids of every node in the body of `if TYPE_CHECKING:`, and the guard itself as a wall.
    # The else branch runs at run time, so it is read like any other code.
    skipped: set[int] = set()
    walls: set[str] = set()
    names = {TYPE_CHECKING, f"typing.{TYPE_CHECKING}"}
    for node in ast.walk(tree):
        if isinstance(node, ast.If) and ast.unparse(node.test) in names:
            walls.add(TYPE_CHECKING)
            skipped.update(id(inner) for s in node.body for inner in ast.walk(s))
    return skipped, walls


def read_facts(path: Path, pkg: tuple[str, ...] = ()) -> Facts:
    """Read one module's imports, nemik references and constructs.

    Args:
        path: The module's file.
        pkg: The module's package, as a path under src/nemik; `()` for the root.

    Returns:
        Its facts. Code under `if TYPE_CHECKING:` is skipped, and the guard itself is a wall.

    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    skipped, constructs = _guarded(tree)
    external: set[str] = set()
    inside: set[Ref] = set()
    for node in ast.walk(tree):
        if id(node) in skipped:
            continue
        found_external, found_inside = _imports(node, pkg)
        external |= found_external
        inside |= found_inside
        constructs |= _constructs(node)
    return Facts(frozenset(external), frozenset(inside), frozenset(constructs))


def module_name(rel: Path) -> str:
    """Name a module by its dotted path under src/nemik.

    Args:
        rel: The file's path relative to src/nemik.

    Returns:
        `x` for x.py, `core.x` for core/x.py, `core` for core/__init__.py, `nemik` for the root.

    """
    parts = rel.with_suffix("").parts
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts) if parts else PACKAGE


def read_package(src: Path) -> dict[str, Facts]:
    """Read every python module of the package, subpackages included.

    Args:
        src: The directory holding the nemik package.

    Returns:
        The facts by dotted module name.

    """
    base = src / PACKAGE
    return {
        module_name(path.relative_to(base)): read_facts(
            path, path.relative_to(base).parent.parts
        )
        for path in sorted(base.rglob("*.py"))
    }


def targets(ref: Ref, known: set[str]) -> set[str]:
    """Resolve a (base, name) reference to the modules it runs.

    Importing a.b.c runs the packages nemik, a and a.b and the module a.b.c; `from a import n`
    also runs a.n when that is a module.

    Args:
        ref: The package path and the imported name ("" for a plain import).
        known: The package's module names.

    Returns:
        The known modules the reference reaches.

    """
    base, name = ref
    parts = base.split(".") if base else []
    wanted = [PACKAGE] + [".".join(parts[: i + 1]) for i in range(len(parts))]
    if name:
        wanted.append(f"{base}.{name}" if base else name)
    return {w for w in wanted if w in known}


def closure(name: str, package: dict[str, Facts]) -> list[str]:
    """List a module and every nemik module it imports, transitively.

    Args:
        name: The module.
        package: The facts of every module.

    Returns:
        The names, sorted.

    """
    known = set(package)
    seen = {name}
    todo = [name]
    while todo:
        for ref in package[todo.pop()].nemik:
            for nxt in targets(ref, known) - seen:
                seen.add(nxt)
                todo.append(nxt)
    return sorted(seen)


def closure_evidence(package: dict[str, Facts]) -> dict[str, str]:
    """Hash each module's closure by module facts, as evidence for a rebaseline entry.

    Args:
        package: The facts of every module.

    Returns:
        {module: hex digest of its closure's names and each module's facts}.

    """
    out: dict[str, str] = {}
    for name in package:
        digest = hashlib.sha256()
        for member in closure(name, package):
            facts = package[member]
            text = f"{member}\0{sorted(facts.imports)}{sorted(facts.nemik)}"
            digest.update(f"{text}{sorted(facts.constructs)}\0".encode())
        out[name] = digest.hexdigest()
    return out


def walls_of(facts: Facts, accepted: frozenset[str]) -> set[str]:
    """Name the walls of one module's own text.

    Args:
        facts: The module's facts.
        accepted: The import lines the compiler accepted.

    Returns:
        The wall labels: an import line the table does not list as accepted, and the constructs.

    """
    return {group(line) for line in facts.imports if line not in accepted} | set(
        facts.constructs
    )


def measure(package: dict[str, Facts], accepted: frozenset[str]) -> Measured:
    """Measure every module: the walls reached through its closure.

    Args:
        package: The facts of every module.
        accepted: The import lines the compiler accepted.

    Returns:
        {module: sorted wall labels} for every module.

    """
    own = {name: walls_of(facts, accepted) for name, facts in package.items()}
    return {
        name: sorted(set().union(*(own[n] for n in closure(name, package))))
        for name in package
    }


def pairs_of(measured: Measured) -> Pairs:
    """Make the ratchet file's content: {module: {wall: "reached"}}, modules with a wall only.

    Args:
        measured: The result of `measure`.

    Returns:
        The document whose leaf count is the incidence.

    """
    return {
        name: dict.fromkeys(walls, "reached")
        for name, walls in sorted(measured.items())
        if walls
    }


def incidence(pairs: Pairs) -> int:
    """Count the (module, wall) pairs.

    Args:
        pairs: The ratchet file's content.

    Returns:
        The number of leaves.

    """
    return sum(len(walls) for walls in pairs.values())


def _json_object(path: Path) -> dict[str, object] | None:
    # The JSON object a file holds, or None when there is no file or it holds another kind.
    if not path.is_file():
        return None
    parsed: object = json.loads(path.read_text(encoding="utf-8"))
    return cast("dict[str, object]", parsed) if isinstance(parsed, dict) else None


def read_pairs(root: Path) -> Pairs | None:
    """Read the recorded walls file, validated.

    Args:
        root: The repository root.

    Returns:
        {module: {wall: "reached"}}, or None when the file is missing or not that shape.

    """
    doc = _json_object(root / WALLS_FILE)
    if doc is None:
        return None
    out: Pairs = {}
    for name, walls in doc.items():
        if not isinstance(walls, dict):
            return None
        inner = cast("dict[object, object]", walls)
        if not all(isinstance(k, str) and v == "reached" for k, v in inner.items()):
            return None
        out[name] = {str(k): "reached" for k in inner}
    return out


def read_table(root: Path) -> dict[str, list[str]]:
    """Read the wall table, validated.

    Args:
        root: The repository root.

    Returns:
        {"accepted": lines, "refused": lines}; a missing or malformed part is empty.

    """
    doc = _json_object(root / TABLE_FILE)
    out: dict[str, list[str]] = {}
    for kind in ("accepted", "refused"):
        lines = doc.get(kind) if doc else None
        out[kind] = [str(x) for x in lines] if isinstance(lines, list) else []
    return out


def load_table(root: Path) -> frozenset[str]:
    """Read the import lines the compiler accepted.

    Args:
        root: The repository root.

    Returns:
        The accepted lines; none when there is no table.

    """
    return frozenset(read_table(root)["accepted"])


def import_lines(package: dict[str, Facts]) -> list[str]:
    """List every distinct external import line of the package.

    Args:
        package: The facts of every module.

    Returns:
        The lines, sorted.

    """
    return sorted({line for facts in package.values() for line in facts.imports})


def compiles(codon: Path, line: str) -> bool:
    """Compile one import line with the pinned compiler.

    Args:
        codon: The compiler binary.
        line: The import line.

    Returns:
        True when it compiles.

    """
    with tempfile.TemporaryDirectory() as tmp:
        program = Path(tmp) / "probe.py"
        program.write_text(line + "\n", encoding="utf-8")
        argv = [str(codon), "build", "-o", str(Path(tmp) / "probe.out"), str(program)]
        return capture(argv, cwd=Path(tmp)).returncode == 0


def probe(codon: Path, package: dict[str, Facts]) -> dict[str, list[str]]:
    """Probe every distinct import line with the compiler.

    Args:
        codon: The compiler binary.
        package: The facts of every module.

    Returns:
        {"accepted": lines that compile, "refused": lines that do not}, both sorted.

    """
    accepted: list[str] = []
    refused: list[str] = []
    for line in import_lines(package):
        (accepted if compiles(codon, line) else refused).append(line)
    return {"accepted": accepted, "refused": refused}


def _dump(doc: object) -> str:
    return json.dumps(doc, indent=1, sort_keys=True) + "\n"


def check(root: Path) -> list[str]:
    """Compare the walls file with a fresh measurement.

    Args:
        root: The repository root.

    Returns:
        The problems, none when the file is exact.

    """
    now = pairs_of(measure(read_package(root / "src"), load_table(root)))
    stored = read_pairs(root)
    if stored == now:
        return []
    recorded = incidence(stored) if stored is not None else "no"
    msg = (
        f"{WALLS_FILE} does not match the measurement: {incidence(now)} pairs now, "
        f"{recorded} recorded; run tools/codon_walls.py --write"
    )
    return [msg]


def write(root: Path) -> None:
    """Record the measurement. A rise is the ratchet's to refuse, not this tool's.

    Args:
        root: The repository root.

    """
    now = pairs_of(measure(read_package(root / "src"), load_table(root)))
    (root / WALLS_FILE).write_text(_dump(now), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    """Check the wall incidence file, record it, or rebuild the wall table.

    Args:
        argv: The command line.

    Returns:
        0 when the file is exact, 1 otherwise.

    """
    ap = argparse.ArgumentParser(description=(main.__doc__ or "").splitlines()[0])
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--write", action="store_true", help="record the measurement")
    ap.add_argument("--probe", type=Path, help="rebuild the wall table with this codon")
    args = ap.parse_args(argv, namespace=Options())
    if args.probe is not None:
        table = probe(args.probe, read_package(args.root / "src"))
        (args.root / TABLE_FILE).write_text(_dump(table), encoding="utf-8")
        sys.stdout.write(
            f"{len(table['accepted'])} accepted, {len(table['refused'])} refused\n"
        )
        return 0
    if args.write:
        write(args.root)
    problems = check(args.root)
    for line in problems:
        sys.stdout.write(line + "\n")
    if not problems:
        stored = read_pairs(args.root) or {}
        sys.stdout.write(f"incidence {incidence(stored)} over {len(stored)} modules\n")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
