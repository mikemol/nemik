# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2077: the wall incidence of src/nemik is recorded exactly.

codon-walls.json lists, per module, the walls Codon refuses that the module reaches through its own
text and its import closure; its leaves are the ratchet's value. The file must match a fresh
measurement. A rise is the ratchet's to refuse (a registered ratchet, a declared rebaseline), so
this file keeps no second record. The table of accepted import lines is checked against the pinned
compiler in tests/test_codon_wall_table.py.
"""

import json
from pathlib import Path

from codon_walls import (
    DYNAMIC,
    TABLE_FILE,
    TYPE_CHECKING,
    WALLS_FILE,
    check,
    import_lines,
    incidence,
    load_table,
    measure,
    pairs_of,
    read_package,
    read_pairs,
    read_table,
    write,
)

ROOT = Path(__file__).resolve().parents[1]
NONE_REACHED = 0
TWO_MODULES = 2
THREE_PAIRS = 3
JSON_ONLY = {"accepted": ["import json"], "refused": []}
JSON_REFUSED = {"accepted": [], "refused": ["import json"]}
NO_TABLE = frozenset[str]()


def _package(root: Path, files: dict[str, str]) -> Path:
    """Write a small package under root/src/nemik; a name may carry a subdirectory.

    Args:
        root: The repository root.
        files: The module sources by path under the package.

    Returns:
        The package directory.

    """
    pkg = root / "src" / "nemik"
    for name, text in files.items():
        (pkg / name).parent.mkdir(parents=True, exist_ok=True)
        (pkg / name).write_text(text, encoding="utf-8")
    return pkg


def _walls(root: Path) -> dict[str, list[str]]:
    """Measure a small package with an empty table, so every external import is a wall.

    Returns:
        The walls each module reaches, by dotted module name.

    """
    return measure(read_package(root / "src"), NO_TABLE)


def _recorded(root: Path) -> int:
    """Read the incidence a root's walls file records.

    Returns:
        The number of (module, wall) pairs in the file.

    """
    pairs = read_pairs(root)
    assert pairs is not None
    return incidence(pairs)


def test_the_incidence_counts_the_leaves_not_the_modules() -> None:
    """Two modules with two and one wall are three pairs: the number a reader compares with 971."""
    pairs = {"a": {"x": "reached", "y": "reached"}, "b": {"x": "reached"}}
    assert incidence(pairs) == THREE_PAIRS
    assert incidence({}) == NONE_REACHED


def test_a_wall_is_reached_through_a_chain_of_two_imports(tmp_path: Path) -> None:
    """Module a imports b, b imports c, c has the wall: a reaches it, so the closure is deep."""
    _package(
        tmp_path,
        {
            "a.py": "from nemik import b\n",
            "b.py": "from nemik import c\n",
            "c.py": "import hashlib\n",
        },
    )
    walls = _walls(tmp_path)
    assert walls["a"] == ["hashlib"]
    assert walls["b"] == ["hashlib"]


def test_modules_that_import_each_other_end_the_closure_and_share_walls(
    tmp_path: Path,
) -> None:
    """A cycle terminates (a mutant that forgets what it has seen would loop) and both reach all."""
    _package(
        tmp_path,
        {
            "a.py": "from nemik import b\nimport hashlib\n",
            "b.py": "from nemik import a\nimport tomllib\n",
        },
    )
    walls = _walls(tmp_path)
    assert walls["a"] == ["hashlib", "tomllib"]
    assert walls["b"] == ["hashlib", "tomllib"]


def test_the_recorded_walls_match_a_fresh_measurement() -> None:
    """The ratchet file and the code agree."""
    assert check(ROOT) == []


def test_the_ratchets_value_is_the_pairs_of_the_measurement() -> None:
    """The file's leaves are the incidence: (module, wall) pairs, none for a clean module."""
    pairs = pairs_of(measure(read_package(ROOT / "src"), load_table(ROOT)))
    assert read_pairs(ROOT) == pairs
    assert all(walls for walls in pairs.values())


def test_the_ratchet_is_declared_for_the_census() -> None:
    """ratchets.json names codon-walls.json, so the pace gets a row and a series for it."""
    declared = (ROOT / "ratchets.json").read_text(encoding="utf-8")
    assert f'"{WALLS_FILE}"' in declared


def test_every_import_line_of_the_package_is_in_the_table() -> None:
    """An unprobed line counts as a wall, so a new import must be probed into the table."""
    table = read_table(ROOT)
    known = set(table["accepted"]) | set(table["refused"])
    assert set(import_lines(read_package(ROOT / "src"))) <= known


def test_a_malformed_walls_file_is_a_problem_not_a_crash(tmp_path: Path) -> None:
    """A file that is not {module: {wall: "reached"}} reads as nothing recorded."""
    _package(tmp_path, {"a.py": "import hashlib\n"})
    for bad in ("[]", '{"a": 1}', '{"a": {"hashlib": 2}}'):
        (tmp_path / WALLS_FILE).write_text(bad, encoding="utf-8")
        assert read_pairs(tmp_path) is None
        assert len(check(tmp_path)) == 1


def test_a_written_file_checks_clean(tmp_path: Path) -> None:
    """Writing records exactly what a fresh measurement says."""
    _package(tmp_path, {"a.py": "import hashlib\n", "b.py": "from nemik import a\n"})
    write(tmp_path)
    assert check(tmp_path) == []
    assert set(read_pairs(tmp_path) or {}) == {"a", "b"}


def test_a_change_not_recorded_is_a_problem(tmp_path: Path) -> None:
    """A wall added after the recording makes the file stale."""
    pkg = _package(tmp_path, {"a.py": "import hashlib\n"})
    write(tmp_path)
    (pkg / "a.py").write_text("import hashlib\nimport tomllib\n", encoding="utf-8")
    assert len(check(tmp_path)) == 1


def test_removing_a_wall_lowers_every_module_that_reaches_it(tmp_path: Path) -> None:
    """The adapter loses its wall, and so does the module that imports it: two pairs fall."""
    pkg = _package(
        tmp_path, {"a.py": "import hashlib\n", "b.py": "from nemik import a\n"}
    )
    write(tmp_path)
    before = _recorded(tmp_path)
    (pkg / "a.py").write_text("import json\n", encoding="utf-8")
    (tmp_path / TABLE_FILE).write_text(json.dumps(JSON_ONLY), encoding="utf-8")
    write(tmp_path)
    assert before - _recorded(tmp_path) == TWO_MODULES


def test_deleting_a_line_with_no_wall_leaves_the_incidence_unchanged(
    tmp_path: Path,
) -> None:
    """A fall must come from a wall going, not from a line that was never one."""
    pkg = _package(tmp_path, {"a.py": "import hashlib\nX = 1\nY = 2\n"})
    write(tmp_path)
    before = _recorded(tmp_path)
    (pkg / "a.py").write_text("import hashlib\nX = 1\n", encoding="utf-8")
    write(tmp_path)
    assert _recorded(tmp_path) == before


def test_a_table_growth_raises_the_count_with_no_code_change(tmp_path: Path) -> None:
    """A line first accepted and then found refused raises the count: a rise to declare."""
    _package(tmp_path, {"a.py": "import json\n"})
    table = tmp_path / TABLE_FILE
    table.write_text(json.dumps(JSON_ONLY), encoding="utf-8")
    write(tmp_path)
    assert _recorded(tmp_path) == NONE_REACHED
    table.write_text(json.dumps(JSON_REFUSED), encoding="utf-8")
    assert len(check(tmp_path)) == 1
    write(tmp_path)
    assert _recorded(tmp_path) == 1


def test_a_relative_import_reaches_its_module(tmp_path: Path) -> None:
    """`from . import a` and `from .a import f` are edges, as `from nemik import a` is."""
    _package(
        tmp_path,
        {
            "a.py": "import hashlib\n",
            "b.py": "from . import a\n",
            "c.py": "from .a import f\n",
        },
    )
    walls = _walls(tmp_path)
    assert walls["b"] == ["hashlib"]
    assert walls["c"] == ["hashlib"]


def test_a_subpackage_module_is_named_by_its_path_and_reached(tmp_path: Path) -> None:
    """core/x.py is `core.x`, so it cannot collide with x.py, and importers reach its walls."""
    _package(
        tmp_path,
        {
            "x.py": "X = 1\n",
            "core/x.py": "import hashlib\n",
            "y.py": "from nemik.core import x\n",
            "z.py": "from nemik.core.x import f\n",
            "w.py": "import nemik.core.x\n",
        },
    )
    walls = _walls(tmp_path)
    assert walls["x"] == []
    assert walls["core.x"] == ["hashlib"]
    assert walls["y"] == walls["z"] == walls["w"] == ["hashlib"]


def test_a_relative_import_inside_a_subpackage_resolves_against_it(
    tmp_path: Path,
) -> None:
    """`from . import x` in core/y.py is core.x, and `from .. import a` is the root a."""
    _package(
        tmp_path,
        {
            "a.py": "import tomllib\n",
            "core/x.py": "import hashlib\n",
            "core/y.py": "from . import x\nfrom .. import a\n",
        },
    )
    assert _walls(tmp_path)["core.y"] == ["hashlib", "tomllib"]


def test_a_package_init_is_run_by_importing_through_it(tmp_path: Path) -> None:
    """Importing core.x runs core/__init__.py, so its walls are reached too."""
    _package(
        tmp_path,
        {
            "core/__init__.py": "import tomllib\n",
            "core/x.py": "X = 1\n",
            "y.py": "from nemik.core import x\n",
        },
    )
    assert _walls(tmp_path)["y"] == ["tomllib"]


def test_a_function_level_import_is_an_edge_and_a_wall(tmp_path: Path) -> None:
    """An import inside a function runs when it is called, so it counts."""
    _package(
        tmp_path,
        {
            "a.py": "import hashlib\n",
            "b.py": "def f():\n    from nemik import a\n    import tomllib\n",
        },
    )
    assert _walls(tmp_path)["b"] == ["hashlib", "tomllib"]


def test_the_typing_guard_is_one_wall_and_its_body_is_skipped(tmp_path: Path) -> None:
    """TYPE_CHECKING is one label, found as an import or a guard; imports under it are skipped."""
    _package(
        tmp_path,
        {
            "a.py": (
                "from typing import TYPE_CHECKING\n"
                "if TYPE_CHECKING:\n    import hashlib\n"
            )
        },
    )
    assert _walls(tmp_path)["a"] == [TYPE_CHECKING]


def test_a_guard_taken_from_the_local_module_is_not_a_wall(tmp_path: Path) -> None:
    """The pinned Codon cannot import typing.TYPE_CHECKING but compiles nemik._typing (W2125).

    A module that guards with the name taken from the local module has no wall for the guard, its
    guarded import is still skipped, and the same guard taken from typing stays a wall.
    """
    _package(
        tmp_path,
        {
            "_typing.py": "TYPE_CHECKING = False\n",
            "a.py": (
                "from nemik._typing import TYPE_CHECKING\n"
                "if TYPE_CHECKING:\n    import hashlib\n"
            ),
            "b.py": (
                "from typing import TYPE_CHECKING\n"
                "if TYPE_CHECKING:\n    import hashlib\n"
            ),
        },
    )
    walls = _walls(tmp_path)
    assert walls["a"] == []
    assert walls["b"] == [TYPE_CHECKING]


def test_the_else_branch_of_the_typing_guard_is_read(tmp_path: Path) -> None:
    """The else branch runs at run time, so an import there counts."""
    _package(
        tmp_path,
        {
            "a.py": (
                "from typing import TYPE_CHECKING\n"
                "if TYPE_CHECKING:\n    pass\nelse:\n    import hashlib\n"
            )
        },
    )
    assert _walls(tmp_path)["a"] == ["TYPE_CHECKING", "hashlib"]


def test_a_bare_import_module_call_is_a_dynamic_import(tmp_path: Path) -> None:
    """`from importlib import import_module` then `import_module(x)` imports by a computed name."""
    _package(
        tmp_path,
        {"a.py": "from importlib import import_module\nimport_module('x')\n"},
    )
    assert DYNAMIC in _walls(tmp_path)["a"]
