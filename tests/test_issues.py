# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W366: the issue-tracker export reads back to the projected tasks, keeping every blocker."""

from pathlib import Path

from rdflib import Graph

from nemik.adapter import queue_graph
from nemik.blocks import annotate
from nemik.check import QUEUE, workstream_files
from nemik.issues import read, to_issues, write
from nemik.projection import decode, project

FLEET = Path(__file__).parent / "fixtures" / "fleet"


def _fleet() -> Graph:
    queues = workstream_files(FLEET, QUEUE)
    known = frozenset(r for r, _ in queues)
    g = Graph()
    for repo, path in queues:
        g += queue_graph(repo, path, known)
    annotate(g)
    return g


def test_issues_round_trip_to_the_projection() -> None:
    """Issues round trip to the projection."""
    tasks = project(_fleet())
    back = read(write(tasks))
    assert [(t.cite, t.name, t.done, t.preds) for t in back] == [
        (t.cite, t.name, t.done, t.preds) for t in tasks
    ]
    assert decode(back) == decode(tasks)


def test_every_issue_names_its_card_and_repo() -> None:
    """Every issue names its card and repo."""
    for issue in to_issues(project(_fleet())):
        assert str(issue["cite"]) in str(issue["body"])
        assert issue["labels"] == [str(issue["cite"]).partition(":")[0]]
        assert issue["state"] in {"open", "closed"}
