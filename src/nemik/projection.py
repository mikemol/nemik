"""nemik:W413: nemik's cards as tasks with predecessor links, the one mapping every export reuses.

Every tool the integration survey ranks (docs/integration-survey.md) reads the same structure: tasks,
and links saying one task cannot finish before another. MS Project XML writes it as PredecessorLink
(Type 1, finish-to-start; CrossProject for a predecessor in another project), issue trackers as
"blocked by". So the mapping is made once, here, and each exporter (W365 MSPDI, W366 issue JSON)
only serializes `Task`.

A card's predecessors are what it waits for (`waitsFor`, resolved by annotate) and what enables it
(`enables` points from the enabler). A predecessor in another repo is a cross-project link. `decode`
inverts the projection to (card, predecessor) pairs, so a test can pin that nothing is lost.

UIDs: MSPDI wants positive integers, unique in the file. A task's UID is its index in the sorted cite
list plus one: stable for a given set of cards, and decode never needs it (links carry the cite).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from nemik.cards import Card, cards

if TYPE_CHECKING:
    from rdflib import Graph


@dataclass(frozen=True)
class Link:
    """One predecessor: its cite, and whether it lives in another repo (MSPDI CrossProject)."""

    cite: str
    cross_repo: bool


@dataclass(frozen=True)
class Task:
    """A card as a task. `done` is MSPDI's 100% complete; `preds` are finish-to-start links."""

    uid: int
    cite: str
    name: str
    done: bool
    preds: tuple[Link, ...] = field(default_factory=tuple)

    @property
    def repo(self) -> str:
        return self.cite.partition(":")[0]


def project(g: Graph, repos: set[str] | None = None) -> list[Task]:
    """The cards of `repos` (every repo when None) as tasks, in cite order."""
    return project_cards(cards(g), repos)


def project_cards(
    by_cite: dict[str, Card], repos: set[str] | None = None
) -> list[Task]:
    """nemik:W425: the projection over plain `Card`s, no rdflib: the portable core (W422).

    A card's predecessors are what it waits for and what enables it; one in another repo is a
    cross-project link.
    """
    chosen = [
        c for cite, c in sorted(by_cite.items()) if repos is None or c.repo in repos
    ]
    tasks = []
    for uid, card in enumerate(chosen, start=1):
        preds = sorted(set(card.waits_for) | set(card.enabled_by))
        tasks.append(
            Task(
                uid=uid,
                cite=card.cite,
                name=card.title or card.cite,
                done=card.done,
                preds=tuple(Link(p, p.partition(":")[0] != card.repo) for p in preds),
            )
        )
    return tasks


def decode(tasks: list[Task]) -> set[tuple[str, str]]:
    """(card, predecessor) cite pairs: what `project` was given, for a round-trip test."""
    return {(t.cite, link.cite) for t in tasks for link in t.preds}
