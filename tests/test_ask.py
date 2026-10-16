# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W587: filing an ask mints the filer's waypoint and writes the floor entry that cites it."""

import json
from pathlib import Path

from nemik.ask import blocked_on, braces_balanced, entry, slug_ok, title
from nemik.ask_cli import main

CLAIM = "fence admission records no waiter, so `hold` cannot be fair (a {nested} brace is fine)"


def _queue(tmp_path: Path) -> Path:
    """Write an empty queue.

    Args:
        tmp_path: A scratch directory.

    Returns:
        The queue file.

    """
    residue: list[str] = []
    cards: list[dict[str, object]] = []
    state: dict[str, object] = {
        "version": 1,
        "project_root": str(tmp_path),
        "counter": 6,
        "residue": residue,
        "waypoints": cards,
    }
    path = tmp_path / "paths-forward.json"
    path.write_text(json.dumps(state))
    return path


def _args(tmp_path: Path, *extra: str) -> list[str]:
    """Build the command line for a filing in a scratch queue and floor.

    Args:
        tmp_path: A scratch directory.
        extra: More arguments.

    Returns:
        The arguments.

    """
    floor = tmp_path / "floor"
    floor.mkdir(exist_ok=True)
    return [
        *("--filer", "life", "--to", "mtools", "--slug", "ask-fence-no-waiter"),
        *("--claim", CLAIM, "--owner-card", "W12"),
        *("--state", str(_queue(tmp_path)), "--floor", str(floor)),
        *extra,
    ]


def test_the_words_of_the_card_and_the_entry() -> None:
    """Title, wait and entry carry the owner, the filer and the filer's own waypoint."""
    assert slug_ok("ask-x-1")
    assert not slug_ok("Ask X")
    assert not slug_ok("-x")
    assert braces_balanced(CLAIM)
    assert not braces_balanced("a } b {")
    assert title("mtools", "first line\nsecond").startswith("Ask mtools: first line")
    assert blocked_on("mtools", "W12") == "mtools:W12"
    assert blocked_on("mtools", "") == "mtools"
    text = entry("k", "life", "mtools", CLAIM, "W7")
    assert "note    = {kind=ask by=life to=mtools}," in text
    assert "waypoint = {life:W7}" in text


def test_a_dry_run_changes_nothing(tmp_path: Path) -> None:
    """Without --apply neither the queue nor the floor is touched."""
    args = _args(tmp_path)
    queue = Path(args[args.index("--state") + 1])
    before = queue.read_text(encoding="utf-8")
    assert main(args) == 0
    assert queue.read_text(encoding="utf-8") == before
    assert list((tmp_path / "floor").iterdir()) == []


def test_applying_mints_blocks_and_writes_then_a_second_filing_is_refused(
    tmp_path: Path,
) -> None:
    """The card waits on the owner's card, the entry cites it, a reuse is refused."""
    args = _args(tmp_path, "--apply")
    assert main(args) == 0
    stored: dict[str, list[dict[str, object]]] = json.loads(
        (tmp_path / "paths-forward.json").read_text(encoding="utf-8")
    )
    (card,) = stored["waypoints"]
    assert (card["symbol"], card["status"]) == ("W7", "blocked")
    assert card["blocked_on"] == ["mtools:W12"]
    written = (tmp_path / "floor" / "ask-fence-no-waiter.bib").read_text(
        encoding="utf-8"
    )
    assert "waypoint = {life:W7}" in written
    refused = 2
    assert main(args) == refused
