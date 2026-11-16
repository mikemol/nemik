# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2217: a round whose inputs did not change is not ranked again."""

from typing import TYPE_CHECKING

import pytest

from nemik import rank
from nemik.rounddigest import (
    card_lines,
    digest,
    fold,
    inside,
    queue_digest,
    remember,
    unchanged,
)

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

DIGEST_LENGTH = 32
REFUSED = 2
QUEUE = (
    '{"waypoints": [{"symbol": "W1", "status": "ready", "touches": ["b", "a"], '
    '"vector": "WV:1/R:H", "evidence": "first"}]}'
)


def _queue_root(tmp_path: Path) -> Path:
    """Write a root with one repo and one queue file.

    Returns:
        The root.

    """
    queue = tmp_path / "root" / "a" / ".claude" / "paths-forward.json"
    queue.parent.mkdir(parents=True)
    queue.write_text(QUEUE, encoding="utf-8")
    return tmp_path / "root"


def _argv(root: Path, tmp_path: Path, digest_file: Path) -> list[str]:
    """Spell the command line of a round export that keeps a digest.

    Returns:
        The arguments after the program name.

    """
    return [
        "--root",
        str(root),
        "--round-file",
        str(tmp_path / "export" / "round.json"),
        "--digest-file",
        str(digest_file),
    ]


def _watch(monkeypatch: pytest.MonkeyPatch) -> list[bool]:
    """Replace the survey with one that reads no queue and records that it was asked.

    Returns:
        The list the stand-in appends to, one entry per call.

    """
    asked: list[bool] = []

    def survey(
        root: Path, *, check: bool = True
    ) -> Iterator[tuple[str, None, list[str]]]:
        """Record the call and read no queue.

        Returns:
            An empty survey.

        """
        del root
        asked.append(check)
        return iter([])

    monkeypatch.setattr(rank, "survey", survey)
    return asked


def test_the_digest_is_stable_and_thirty_two_hex_digits() -> None:
    """The same inputs give the same digest, whatever order the lists are written in."""
    one = digest([("a", QUEUE)], "")
    two = digest([("a", QUEUE.replace('["b", "a"]', '["a", "b"]'))], "")
    assert one == two
    assert len(one) == DIGEST_LENGTH
    assert fold("x") != fold("y")


def test_only_what_the_round_reads_moves_the_digest() -> None:
    """A status, a tag, a vector or the landings move it; an evidence edit does not."""
    base = digest([("a", QUEUE)], "")
    assert digest([("a", QUEUE.replace("first", "second"))], "") == base
    assert digest([("a", QUEUE.replace("ready", "working"))], "") != base
    assert digest([("a", QUEUE.replace('"b"', '"gate-repair"'))], "") != base
    assert digest([("a", QUEUE.replace("R:H", "R:L"))], "") != base
    assert digest([("a", QUEUE)], '{"landings": []}') != base


def test_an_unreadable_queue_is_a_line_not_a_crash() -> None:
    """A file that is not a queue still digests, as `unreadable`, so a break is a change."""
    assert card_lines("a", "not json") == ["a|unreadable"]
    assert card_lines("a", "[]") == ["a|unreadable"]
    assert digest([("a", "not json")], "") != digest([("a", QUEUE)], "")


def test_a_digest_inside_the_export_tree_is_refused(tmp_path: Path) -> None:
    """The export tree is served whole, so a digest kept there would be served."""
    round_file = str(tmp_path / "export" / "round.json")
    assert inside(round_file, str(tmp_path / "export" / "digest"))
    assert not inside(round_file, str(tmp_path / "state" / "digest"))


def test_a_kept_digest_is_read_back_exactly(tmp_path: Path) -> None:
    """Remember then unchanged says yes for that digest and no for another."""
    kept = str(tmp_path / "state" / "digest")
    assert not unchanged("abc", kept)
    remember("abc", kept)
    assert unchanged("abc", kept)
    assert not unchanged("abd", kept)


def test_an_unchanged_round_is_not_ranked_again(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """With the kept digest equal to the fresh one, main returns without the survey."""
    root = _queue_root(tmp_path)
    kept = tmp_path / "state" / "digest"
    remember(queue_digest(str(root), str(tmp_path / "none")), str(kept))
    asked = _watch(monkeypatch)
    rank.main(_argv(root, tmp_path, kept))
    assert asked == []


def test_a_changed_round_is_ranked_and_its_digest_kept(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """MUTANT: a mode that always skipped never exports; a changed digest ranks, then is kept."""
    root = _queue_root(tmp_path)
    kept = tmp_path / "state" / "digest"
    remember("something else", str(kept))
    asked = _watch(monkeypatch)
    rank.main(_argv(root, tmp_path, kept))
    assert asked == [False]
    assert unchanged(queue_digest(str(root), str(tmp_path / "none")), str(kept))


def test_main_refuses_a_digest_inside_the_export_tree(tmp_path: Path) -> None:
    """Exit 2 before any ranking when the digest file sits beside the round file."""
    root = _queue_root(tmp_path)
    with pytest.raises(SystemExit) as stopped:
        rank.main(_argv(root, tmp_path, tmp_path / "export" / "digest"))
    assert stopped.value.code == REFUSED
