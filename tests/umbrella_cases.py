# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W529: read what UmbrellaBlockShape names, for the tests that build umbrella graphs."""

from itertools import count

from rdflib import Graph
from rdflib.term import Node

from nemik.blocks import annotate
from nemik.check import shapes
from nemik.shaclinc import findings

_KEYS = count()


def blocked_on_umbrellas(g: Graph) -> set[Node]:
    """Collect the waypoints UmbrellaBlockShape names.

    Args:
        g: The graph of cards.

    Returns:
        The cards blocked on another workstream's umbrella. Each call uses a fresh cache key,
        since findings() caches by key.

    """
    annotate(g)
    rows = findings(f"umbrella-blocked-{next(_KEYS)}", g, shapes())
    return {focus for focus, _, m in rows if "another workstream's umbrella" in m}
