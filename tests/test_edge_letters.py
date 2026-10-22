# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W850: a finished card's cross-repo edges become inbox letters, once each."""

import json
from pathlib import Path

from nemik.edgeletters import name, text
from nemik.witnesses import RECORD, deliver

ALPHA: dict[str, list[dict[str, object]]] = {"waypoints": [{"symbol": "W1"}]}
BETA: dict[str, list[dict[str, object]]] = {
    "waypoints": [
        {"symbol": "W5", "blocked_on": ["alpha:W1"]},
        {"symbol": "W6", "caused_by": "alpha:W1"},
    ]
}
QUEUES = {"alpha": json.dumps(ALPHA), "beta": json.dumps(BETA)}
DAY = "2026-10-22"
NEXT_DAY = "2026-10-23"
CARD = ("alpha", "W1")
EDGE = ("blocked_on", "beta", "W5")
BOTH = [
    "2026-10-22-nemik-edge-alpha-W1-blocked_on-W5.md",
    "2026-10-22-nemik-edge-alpha-W1-caused_by-W6.md",
]


def _fleet(root: Path) -> None:
    """Make beta's inbox under `root`."""
    (root / "beta" / "inbox").mkdir(parents=True)


def test_a_letter_file_name_carries_the_edge() -> None:
    """Two edges to one repo are two files."""
    assert name(DAY, "alpha", "W1", EDGE) == BOTH[0]
    other = ("caused_by", "beta", "W6")
    assert name(DAY, "alpha", "W1", other) == BOTH[1]


def test_a_letter_opens_with_the_header_the_inbox_reader_addresses_by() -> None:
    """The first line is `# nemik → beta: ...`, so letters.py finds the recipient."""
    body = text("alpha", "W1", EDGE, "done", DAY)
    assert body.startswith("# nemik → beta: alpha:W1 is done\n")
    assert "beta:W5 is blocked on it" in body


def test_each_edge_gets_one_letter_and_a_rerun_writes_none(tmp_path: Path) -> None:
    """Two edges, two letters; the second run finds both recorded."""
    _fleet(tmp_path)
    first = deliver(tmp_path, QUEUES, CARD, "done", DAY)
    assert sorted(p.name for p in first) == BOTH
    assert deliver(tmp_path, QUEUES, CARD, "done", NEXT_DAY) == []


def test_a_deleted_letter_is_not_sent_again(tmp_path: Path) -> None:
    """The reader removes a letter; the record still says it went out."""
    _fleet(tmp_path)
    for letter in deliver(tmp_path, QUEUES, CARD, "done", DAY):
        letter.unlink()
    assert deliver(tmp_path, QUEUES, CARD, "done", NEXT_DAY) == []
    assert (tmp_path / RECORD).read_text(encoding="utf-8").splitlines() == [
        f"alpha:W1 blocked_on beta:W5 {DAY}",
        f"alpha:W1 caused_by beta:W6 {DAY}",
    ]


def test_a_repo_with_no_inbox_stays_owed_until_it_has_one(tmp_path: Path) -> None:
    """Nothing is written or stamped without an inbox; a later run delivers."""
    assert deliver(tmp_path, QUEUES, CARD, "done", DAY) == []
    assert not (tmp_path / RECORD).exists()
    _fleet(tmp_path)
    later = deliver(tmp_path, QUEUES, CARD, "done", NEXT_DAY)
    assert sorted(p.name for p in later) == [n.replace(DAY, NEXT_DAY) for n in BOTH]
