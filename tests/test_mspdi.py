# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W365: the MSPDI export reads back to exactly the projected tasks, fleet or one repo."""

import xml.etree.ElementTree as ET
from pathlib import Path

from rdflib import Graph

from nemik.adapter import queue_graph
from nemik.blocks import annotate
from nemik.check import QUEUE, workstream_files
from nemik.mspdi import NS, read, write
from nemik.projection import project

FLEET = Path(__file__).parent / "fixtures" / "fleet"


def _fleet() -> Graph:
    queues = workstream_files(FLEET, QUEUE)
    known = frozenset(r for r, _ in queues)
    g = Graph()
    for repo, path in queues:
        g += queue_graph(repo, path, known)
    annotate(g)
    return g


def test_the_whole_fleet_round_trips() -> None:
    tasks = project(_fleet())
    assert read(write(tasks)) == tasks


def test_one_repo_round_trips_with_its_cross_project_links() -> None:
    g = _fleet()
    tasks = project(g)
    repo = next(t.repo for t in tasks if any(link.cross_repo for link in t.preds))
    mine = project(g, {repo})
    text = write(mine)
    assert read(text) == mine
    root = ET.fromstring(text)
    assert root.findall(f".//{{{NS}}}CrossProject"), (
        "a cross-repo predecessor is a CrossProject link"
    )


def test_every_link_is_finish_to_start() -> None:
    root = ET.fromstring(write(project(_fleet())))
    types = {el.text for el in root.iter(f"{{{NS}}}Type")}
    assert types == {"1"}
