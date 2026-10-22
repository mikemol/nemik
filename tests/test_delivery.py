# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W849: the delivery record sends one letter per cross-repo edge, once."""

import json

from nemik.delivery import delivered, key, owed, stamp
from nemik.workrows import edges_of

EDGES = [
    ("blocked_on", "beta", "W5"),
    ("caused_by", "beta", "W5"),
    ("enables", "gamma", "W2"),
]
ALPHA: dict[str, list[dict[str, object]]] = {"waypoints": [{"symbol": "W1"}]}
BETA: dict[str, list[dict[str, object]]] = {
    "waypoints": [{"symbol": "W5", "blocked_on": ["alpha:W1"]}]
}
QUEUES = {"alpha": json.dumps(ALPHA), "beta": json.dumps(BETA)}


def test_a_key_names_the_card_the_kind_and_the_other_card() -> None:
    """The key is the finished card, the edge kind and the card on the other end."""
    assert key("alpha", "W1", EDGES[0]) == "alpha:W1 blocked_on beta:W5"


def test_an_empty_record_owes_every_edge() -> None:
    """Nothing delivered yet: all three edges are still owed, in the order given."""
    assert owed("", "alpha", "W1", EDGES) == EDGES


def test_a_stamped_edge_is_not_owed_again_on_a_later_day() -> None:
    """A rerun on another day finds the line by its key, whatever its day."""
    record = stamp("alpha", "W1", EDGES[0], "2026-10-22")
    assert owed(record, "alpha", "W1", EDGES) == EDGES[1:]
    assert delivered(record) == {"alpha:W1 blocked_on beta:W5"}


def test_a_record_line_names_the_day_last() -> None:
    """The line is the key, a space and the day, ending in a newline."""
    assert stamp("alpha", "W1", EDGES[2], "2026-10-22") == (
        "alpha:W1 enables gamma:W2 2026-10-22\n"
    )


def test_blank_and_dayless_lines_are_skipped() -> None:
    """A blank line or one with no day counts for nothing."""
    assert delivered("\n  \nalpha:W1\n") == set()


def test_the_record_is_per_finished_card() -> None:
    """The same edge of another finished card is a different key and still owed."""
    record = stamp("alpha", "W1", EDGES[0], "2026-10-22")
    assert owed(record, "alpha", "W7", EDGES[:1]) == EDGES[:1]


def test_the_edge_walk_feeds_the_record() -> None:
    """Edges from workrows.edges_of go through the record: stamped ones drop out."""
    edges = edges_of(QUEUES, "alpha", "W1")
    assert edges == [("blocked_on", "beta", "W5")]
    record = stamp("alpha", "W1", edges[0], "2026-10-22")
    assert owed(record, "alpha", "W1", edges) == []
