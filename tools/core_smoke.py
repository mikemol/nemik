# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W824: a smoke call of every pure core function, as text both runtimes must agree on.

The Codon census compiles `import nemik.<module>`, which checks no function body, and a plain
`codon run` hides the optimizer bug that `--release` has (a dict update `d[k] = a[k] * b[k]`
became an in-place update that raised KeyError, found in core.chains). The wasm module is built
with `--release`, so the core must be run that way: tests/test_codon_census.py runs `lines()`
under CPython and under `codon run --release` and compares the two outputs. Only ints and
strings are printed, so the two runtimes cannot differ by float formatting.
"""

from nemik.core.chains import longest_chains
from nemik.core.text import luminance, repo_hue
from nemik.core.treemap import ordered_treemap, tree_of

MILLI = 1000
MICRO = 1000000
SIX = 6


def lines() -> list[str]:
    """Run each core function on a small fixed input and describe the answer.

    Returns:
        One text line per fact.

    """
    names = ["a", "b", "c", "d", "e", "f"]
    pairs = [("a", "b"), ("a", "c"), ("b", "d"), ("c", "d"), ("d", "e")]
    found = longest_chains(names, pairs)
    edges = [(0, 1, 0), (0, 2, 0), (1, 3, 0), (2, 3, 0), (3, 4, 0)]
    tree = tree_of(SIX, [True] * SIX, edges)
    cells = ordered_treemap(tree, [4, 5], (0.0, 0.0, 100.0, 100.0), (4.0, 12.0))
    return [
        f"chains {found.length} {found.up['e']} {found.down['a']}",
        *[f"through {name} {found.paths.get(name, 0)}" for name in names],
        f"tree {tree.parent} {tree.weight} {tree.own} {tree.roots}",
        *[
            f"cell {i} {int(cells.x[i] * MILLI)} {int(cells.y[i] * MILLI)} "
            f"{int(cells.w[i] * MILLI)} {int(cells.h[i] * MILLI)} {cells.depth[i]} "
            f"{int(cells.head[i] * MILLI)}"
            for i in range(SIX)
        ],
        f"hue {repo_hue('luthen-observability')}",
        f"light {int(luminance(12.0, 200.0, 99.0) * MICRO)}",
    ]
