# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W626: the cache's radius is derived from the shapes; unbounded means a full run."""

from rdflib.namespace import SH

from nemik.check import shapes
from nemik.shapedepth import FLOOR, UNBOUNDED, depth, radius


def test_the_real_shapes_need_at_least_the_umbrella_chain() -> None:
    """UmbrellaBlockShape walks waiter, umbrella, kid, and the kid's state: the radius is >= 3."""
    texts = sorted(str(t) for t in shapes().objects(None, SH.select))
    found = depth(texts)
    assert found != UNBOUNDED
    assert found >= FLOOR + 2


def test_a_longer_chain_gives_a_larger_radius() -> None:
    """Four variables chained from $this give four hops."""
    query = (
        "SELECT $this WHERE { $this <https://example.org/a> ?x . ?x <https://example.org/b> ?y . "
        "?y <https://example.org/c> ?z . ?z <https://example.org/d> ?w }"
    )
    assert depth([query]) == len("xyzw")


def test_a_property_path_has_no_bound() -> None:
    """A transitive path reads any distance: no radius, so the caller does a full run."""
    query = "SELECT $this WHERE { $this <https://example.org/a>+ ?x }"
    assert depth([query]) == UNBOUNDED
    assert radius([query]) == UNBOUNDED


def test_a_query_that_will_not_parse_has_no_bound() -> None:
    """Unparseable text cannot be measured, so it is treated as unbounded."""
    assert depth(["SELECT WHERE {{{"]) == UNBOUNDED
