# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W766: a reader sees only what changed since the digest it last saw."""

from pathlib import Path

from nemik.check import unseen
from nemik.digest import delta

FIRST = [
    "provenance: nemik abc",
    "OK        a",
    "  Info      --     2 cards: one",
    "  Warning   W1     two",
    "OK        b",
    "  Warning   W1     two",
]


def test_nothing_changed_shows_only_the_count() -> None:
    """The same digest twice leaves one line, counting all six."""
    assert delta(FIRST, FIRST) == [
        "6 unchanged lines not shown (nemik-check --digest without --since)"
    ]


def test_a_new_finding_is_shown_under_its_header() -> None:
    """W9 on a is new and prints with a's header; the six old lines stay unshown."""
    now = [*FIRST[:4], "  Warning   W9     three", *FIRST[4:]]
    got = delta(now, FIRST)
    assert got[:2] == ["OK        a", "  Warning   W9     three"]
    assert got[-1].startswith("6 unchanged")


def test_a_finding_that_moves_to_another_repo_counts_as_new() -> None:
    """The same message under another header is another key."""
    seen = ["OK        a", "  Warning   W1     two"]
    now = ["OK        a", "OK        b", "  Warning   W1     two"]
    got = delta(now, seen)
    assert got[:2] == ["OK        b", "  Warning   W1     two"]
    assert got[-1].startswith("1 unchanged")


def test_the_file_remembers_the_full_digest_not_the_delta(tmp_path: Path) -> None:
    """A first sight shows everything; the second shows the count; the file keeps the digest."""
    since = tmp_path / "session"
    first = unseen(FIRST, since)
    assert first[:-1] == FIRST
    assert unseen(FIRST, since)[0].startswith("6 unchanged")
    assert since.read_text(encoding="utf-8").splitlines() == FIRST
