# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W425: the queue's cards as plain data, the pure input the typed-subset modules read.

nemik:W422's plan moves modules into a portable Python subset that transpiles to TypeScript (mtools:
W1070-W1073). rdflib cannot cross that line, so the graph is read once, here, into frozen records of
strings and tuples; projection, critical and health can then be written against `Card` alone. This
is not nemik.index (W412): that one is a per-build cache keyed by rdflib terms for speed; this one
is the contract a module needs to be portable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from rdflib.namespace import DCTERMS

from nemik.adapter import NEMIK, OSLC_CM
from nemik.blocks import ref

if TYPE_CHECKING:
    from rdflib import Graph


@dataclass(frozen=True)
class Card:
    """One card: its cite, state word, title and its links, as cites. Sorted, so equal cards compare equal."""

    cite: str
    state: (
        str  # ready, working, blocked, done, ... (the local name of its oslc_cm:state)
    )
    title: str
    waits_for: tuple[str, ...]  # the cards it waits for (annotate's resolved waitsFor)
    enabled_by: tuple[str, ...]  # the cards that enable it
    ticks_blocked: int = (
        0  # loop ticks it has spent blocked (health's oldest-block signal, W454)
    )

    @property
    def repo(self) -> str:
        """The repo the card lives in."""
        return self.cite.partition(":")[0]

    @property
    def done(self) -> bool:
        """Whether the card is done."""
        return self.state == "done"


def cards(g: Graph) -> dict[str, Card]:
    """Every card in `g`, by cite: the only place this layer touches rdflib.

    nemik:W518: inside one build's `indexed()` scope it is read once per graph and shared (a Card is
    frozen, the dict is copied), where health and critical each asked for it again.
    """
    from nemik.index import index

    ix = index(g)
    if ix is None:
        return _read(g)
    if ix.cards is None:
        ix.cards = _read(g)
    return dict(ix.cards)


def _read(g: Graph) -> dict[str, Card]:
    nodes = set(g.subjects(OSLC_CM.state, None))
    out: dict[str, Card] = {}
    for n in nodes:
        state = str(g.value(n, OSLC_CM.state) or "").rsplit("#", 1)[-1].lower()
        out[ref(n)] = Card(
            cite=ref(n),
            state=state,
            title=str(g.value(n, DCTERMS.title) or ""),
            waits_for=tuple(
                sorted(ref(o) for o in g.objects(n, NEMIK.waitsFor) if o in nodes)
            ),
            enabled_by=tuple(
                sorted(ref(s) for s in g.subjects(NEMIK.enables, n) if s in nodes)
            ),
            ticks_blocked=int(str(g.value(n, NEMIK.ticksBlocked) or 0)),
        )
    return dict(sorted(out.items()))
