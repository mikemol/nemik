# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W365: the MSPDI export reads back to exactly the projected tasks, fleet or one repo."""

from pathlib import Path

import pytest
from rdflib import Graph

from nemik.adapter import queue_graph
from nemik.blocks import annotate
from nemik.mspdi import parse, read, write
from nemik.projection import project
from nemik.queuefiles import QUEUE, workstream_files

FLEET = Path(__file__).parent / "fixtures" / "fleet"
BOMB = (
    '<?xml version="1.0"?>'
    '<!DOCTYPE Project [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;&a;">]>'
    "<Project><Tasks><Task><Name>&b;</Name></Task></Tasks></Project>"
)


def _fleet() -> Graph:
    queues = workstream_files(FLEET, QUEUE)
    known = frozenset(r for r, _ in queues)
    g = Graph()
    for repo, path in queues:
        g += queue_graph(repo, path, known)
    annotate(g)
    return g


def test_the_whole_fleet_round_trips() -> None:
    """The whole fleet round trips."""
    tasks = project(_fleet())
    assert read(write(tasks)) == tasks


def test_one_repo_round_trips_with_its_cross_project_links() -> None:
    """One repo round trips with its cross project links."""
    g = _fleet()
    tasks = project(g)
    repo = next(t.repo for t in tasks if any(link.cross_repo for link in t.preds))
    mine = project(g, {repo})
    text = write(mine)
    assert read(text) == mine
    assert parse(text).descendants("CrossProject"), (
        "a cross-repo predecessor is a CrossProject link"
    )


def test_every_link_is_finish_to_start() -> None:
    """Every link is finish to start."""
    root = parse(write(project(_fleet())))
    types = {el.text for el in root.descendants("Type")}
    assert types == {"1"}


def test_a_document_with_a_doctype_is_refused() -> None:
    """A DOCTYPE, where an entity is declared, is refused before anything expands (W1633)."""
    with pytest.raises(ValueError, match="DOCTYPE"):
        read(BOMB)


def test_text_with_markup_characters_survives_a_round_trip() -> None:
    """A name holding & < and > is escaped on write and read back unchanged (W1633)."""
    tasks = project(_fleet())
    first = tasks[0]
    odd = type(first)(
        uid=first.uid,
        cite=first.cite,
        name="a & b < c > d",
        done=first.done,
        preds=(),
    )
    assert read(write([odd])) == [odd]
