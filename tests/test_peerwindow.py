# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1149: a peer tree's churn is three counts, and a handoff not in HEAD is named."""

from peerwindow import WATCH, counts_of, read_watch, report

PORCELAIN = [" M a.py", "MM b.py", "A  c.py", "?? d.py", "?? e.py"]
TRACKED = 3
BOTH = 1
UNTRACKED = 2


def test_the_counts_keep_mm_apart_from_a_plain_modification() -> None:
    """A path staged and unstaged at once is a peer mid-operation, not just uncommitted."""
    assert counts_of(PORCELAIN) == (TRACKED, BOTH, UNTRACKED)
    assert counts_of([]) == (0, 0, 0)


def test_the_watch_list_is_data_read_from_the_file() -> None:
    """The recorded watch list names summit and its one handed artefact."""
    watched, handed = read_watch(WATCH.read_text(encoding="utf-8"))
    assert [peer for peer, _ in watched] == ["summit"]
    assert handed == [
        ("summit", "registries/capabilities/substitutable-backing-store.md")
    ]


def test_a_watch_list_with_nothing_in_it_reads_as_empty() -> None:
    """No watched peer and no handoff: nothing is measured and the totals say so."""
    assert read_watch("{}") == ([], [])


def test_the_report_says_quiet_busy_unavailable_and_unplaced() -> None:
    """One line per peer with its why, one per unplaced handoff, then the totals."""
    watched = [
        (("a", "why a"), (0, 0, 4)),
        (("b", "why b"), (2, 1, 0)),
        (("c", "why c"), None),
    ]
    lines = report(watched, [("b", "x/y.md")])
    assert lines[0] == "  QUIET  a: 0 tracked change(s), 0 staged+unstaged, 4 untracked"
    assert lines[2] == "  BUSY   b: 2 tracked change(s), 1 staged+unstaged, 0 untracked"
    assert lines[4].startswith("  UNAVAILABLE  c")
    assert "  UNPLACED  b:x/y.md — handed over, absent from HEAD" in lines
    assert lines[-1] == "peer_write_window: 3 watched peer(s), 1 unplaced handoff(s)"
