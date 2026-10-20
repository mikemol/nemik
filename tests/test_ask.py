# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W587: filing an ask mints the filer's waypoint and writes the floor entry that cites it."""

import json
from pathlib import Path

import pytest

from nemik.ask import blocked_on, braces_balanced, entry, slug_ok, title
from nemik.ask_cli import main

CLAIM = "fence admission records no waiter, so `hold` cannot be fair (a {nested} brace is fine)"


@pytest.fixture()
def scratch_fleet(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the scratch directory the home whose ~/github the writer reads the fleet from."""
    monkeypatch.setenv("HOME", str(tmp_path))


def _write(repo: Path, cards: list[dict[str, object]]) -> Path:
    """Write a queue under <repo>/.claude, where the writer finds a workstream.

    Args:
        repo: The repo's directory.
        cards: Its waypoints.

    Returns:
        The queue file.

    """
    residue: list[str] = []
    state: dict[str, object] = {
        "version": 1,
        "project_root": str(repo),
        "counter": 12,
        "residue": residue,
        "waypoints": cards,
    }
    path = repo / ".claude" / "paths-forward.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state))
    return path


def _queue(tmp_path: Path) -> Path:
    """Write the filer's empty queue and the owner's, whose W12 is open.

    The owner's queue sits beside the filer's, so the writer resolves `mtools:W12` here and not in
    the real fleet, where W12 has since landed (a test must not depend on that).

    Args:
        tmp_path: A scratch directory, the fleet root.

    Returns:
        The filer's queue file.

    """
    owner: dict[str, object] = {
        "symbol": "W12",
        "title": "the owner's card",
        "status": "ready",
        "blocked_on": [],
        "enables": [],
        "touches": [],
        "next_bounded_step": "work",
        "evidence": "",
    }
    _write(tmp_path / "github" / "mtools", [owner])
    return _write(tmp_path / "github" / "life", [])


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


@pytest.mark.usefixtures("scratch_fleet")
def test_a_dry_run_changes_nothing(tmp_path: Path) -> None:
    """Without --apply neither the queue nor the floor is touched."""
    args = _args(tmp_path)
    queue = Path(args[args.index("--state") + 1])
    before = queue.read_text(encoding="utf-8")
    assert main(args) == 0
    assert queue.read_text(encoding="utf-8") == before
    assert list((tmp_path / "floor").iterdir()) == []


@pytest.mark.usefixtures("scratch_fleet")
def test_applying_mints_blocks_and_writes_then_a_second_filing_is_refused(
    tmp_path: Path,
) -> None:
    """The card waits on the owner's card, the entry cites it, a reuse is refused."""
    args = _args(tmp_path, "--apply")
    assert main(args) == 0
    stored: dict[str, list[dict[str, object]]] = json.loads(
        (tmp_path / "github" / "life" / ".claude" / "paths-forward.json").read_text(
            encoding="utf-8"
        )
    )
    (card,) = stored["waypoints"]
    assert (card["symbol"], card["status"]) == ("W13", "blocked")
    assert card["blocked_on"] == ["mtools:W12"]
    written = (tmp_path / "floor" / "ask-fence-no-waiter.bib").read_text(
        encoding="utf-8"
    )
    assert "waypoint = {life:W13}" in written
    refused = 2
    assert main(args) == refused
