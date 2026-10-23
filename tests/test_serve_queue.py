# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W931: nemik-serve answers /queue.json with each repo's ready cards in work order."""

from pathlib import Path

from nemik.serve import DOC_ROUTES, Model

FLEET = Path(__file__).parent / "fixtures" / "fleet"
KEYS = {"place", "cite", "title", "weight", "band", "waited_days", "overtaken_by"}


def _check(repo: str, rows: object) -> None:
    """Assert one repo's rows are places 1 to n, each with every column the page reads."""
    assert isinstance(rows, list)
    found = [row for row in rows if isinstance(row, dict)]
    assert len(found) == len(rows), repo
    assert [int(str(row.get("place"))) for row in found] == list(
        range(1, len(found) + 1)
    ), repo
    assert all(set(map(str, row)) == KEYS for row in found), repo
    assert all(str(row.get("cite")).startswith(f"{repo}:") for row in found), repo


def test_the_route_is_listed_and_every_repo_has_a_numbered_queue() -> None:
    """Each queue is places 1..n in order, and every row carries the columns the page reads."""
    model = Model(FLEET)
    model.refresh()
    assert "/queue.json" in DOC_ROUTES
    doc = model.doc_for("/queue.json")
    queues = doc["queues"]
    assert isinstance(queues, dict)
    assert queues
    for repo in sorted(map(str, queues)):
        _check(repo, queues.get(repo))
