# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1139: a queue with no git history gets its weekly rows from its own stamps."""

import copy
import json
import tracemalloc
from datetime import UTC, datetime
from pathlib import Path

from nemik.history import (
    QueueDoc,
    Snapshot,
    Waypoint,
    snapshots,
    stamp_snapshots,
    weekly,
)

OPENED_IN_FIRST_WEEK = 2
CLOSED_IN_FIRST_WEEK = 1
TWO_WEEKS = 2
SMALL_HEAP = 64 * 1024 * 1024  # the fixed code takes 7.9 MiB for the 1000 cards below
SEEDS = 40
STAMP_POOL = 14  # fewer stamps than cards, so some are shared and the moments repeat
MAX_CARDS = 90
TENTHS = 10  # each draw below picks a tenth, and these are the cases that tenth selects
CLOSED_BELOW = 5  # tenths 0-4: a `completed` stamp, which may be before the `issued_at`
EMPTY_BELOW = 6  # tenth 5: an empty `completed`; 6-9: none
STATUSES = ["ready", "working", "blocked", "done", "dropped"]
COMPACT = "%Y%m%dT%H%M%SZ"
QUEUE = Path(".claude") / "paths-forward.json"
# one card closed, one open, one issued a week later, one with no stamp at all
CARDS: list[Waypoint] = [
    {
        "symbol": "W1",
        "status": "done",
        "issued_at": "2026-11-02T10:00:00Z",
        "completed": "20261103T120000Z",
    },
    {"symbol": "W2", "status": "ready", "issued_at": "2026-11-02T11:00:00Z"},
    {"symbol": "W3", "status": "blocked", "issued_at": "2026-11-10T09:00:00Z"},
    {"symbol": "W4", "status": "ready"},
]
DOC: QueueDoc = {"waypoints": CARDS}


def _queue(tmp_path: Path) -> Path:
    """Write the cards as a queue file outside any repository.

    Returns:
        The queue file's path.

    """
    path = tmp_path / QUEUE
    path.parent.mkdir()
    path.write_text(json.dumps(DOC), encoding="utf-8")
    return path


def _states(snap: Snapshot) -> dict[str, str]:
    """Give each card of a snapshot with its status.

    Returns:
        The status by symbol.

    """
    return {str(w["symbol"]): str(w["status"]) for w in snap[1]["waypoints"]}


def test_a_queue_with_no_git_history_reads_its_stamps(tmp_path: Path) -> None:
    """The snapshots are one per distinct stamp, oldest first, and a card with no stamp is out."""
    _queue(tmp_path)
    snaps = snapshots(tmp_path)
    assert [at.isoformat() for at, _ in snaps] == [
        "2026-11-02T10:00:00+00:00",
        "2026-11-02T11:00:00+00:00",
        "2026-11-03T12:00:00+00:00",
        "2026-11-10T09:00:00+00:00",
    ]
    assert set(_states(snaps[-1])) == {"W1", "W2", "W3"}


def test_a_closed_card_was_open_before_its_close() -> None:
    """W1 reads ready until its `completed` stamp and done from then on."""
    first, _, closed, _ = stamp_snapshots(DOC)
    assert _states(first) == {"W1": "ready"}
    assert _states(closed)["W1"] == "done"


def test_the_weekly_rows_count_what_opened_and_closed(tmp_path: Path) -> None:
    """Two ISO weeks: two cards opened and one closed in the first, one opened in the second."""
    _queue(tmp_path)
    rows = weekly(snapshots(tmp_path))
    assert len(rows) == TWO_WEEKS
    first, second = rows
    opened: object = first["opened"]
    closed: object = first["closed"]
    later: object = second["opened"]
    assert (opened, closed, later) == (OPENED_IN_FIRST_WEEK, CLOSED_IN_FIRST_WEEK, 1)


def test_the_snapshots_share_their_cards_instead_of_copying_each_per_moment() -> None:
    """nemik:W2069: n cards give at most 2n distinct dicts across all the moments, not n squared.

    A copy of every issued card per moment was 1.3 GiB for the 2000-card queue the pod builds.
    """
    count = 60
    cards: list[Waypoint] = [
        {
            "symbol": f"W{n}",
            "status": "done" if n % 2 else "ready",
            "issued_at": f"2026-11-02T{n // 60:02d}:{n % 60:02d}:00Z",
            "completed": f"20261103T{n // 60:02d}{n % 60:02d}00Z" if n % 2 else "",
        }
        for n in range(count)
    ]
    snaps = stamp_snapshots({"waypoints": cards})
    distinct = {id(w) for _, doc in snaps for w in doc["waypoints"]}
    assert len(snaps) > count
    assert len(distinct) <= 2 * count


def _large(count: int) -> QueueDoc:
    """Make a queue of `count` cards, each issued a minute after the last, every third closed.

    Returns:
        The queue document.

    """
    cards: list[Waypoint] = []
    for n in range(count):
        card: Waypoint = {
            "symbol": f"W{n}",
            "status": "done" if n % 3 == 0 else "ready",
            "issued_at": f"2026-11-02T{n // 60 % 24:02d}:{n % 60:02d}:00Z",
        }
        if n % 3 == 0:
            card["completed"] = f"20261103T{n // 60 % 24:02d}{n % 60:02d}30Z"
        cards.append(card)
    return {"waypoints": cards}


def _issued(text: object) -> datetime | None:
    """Read an `issued_at` stamp of the form 2026-11-02T10:00:00Z.

    Returns:
        The moment, or None when there is no stamp.

    """
    if not isinstance(text, str) or not text:
        return None
    return datetime.fromisoformat(text)


def _completed(text: object) -> datetime | None:
    """Read a `completed` stamp of the form 20261103T123030Z.

    Returns:
        The moment, or None when there is no stamp.

    """
    if not isinstance(text, str) or not text:
        return None
    return datetime.strptime(text, COMPACT).replace(tzinfo=UTC)


def _old_snapshots(doc: QueueDoc) -> list[Snapshot]:
    """Build the snapshots as stamp_snapshots did before nemik:W2069, a copy per card per moment.

    This is the old loop as it was, with the stamp readers of this file in place of history's.

    Returns:
        (moment, queue) for each distinct stamp, oldest first.

    """
    born = []
    for card in doc["waypoints"]:
        issued = _issued(card.get("issued_at"))
        if issued is not None:
            born.append((card, issued, _completed(card.get("completed"))))
    moments = sorted({t for _, a, b in born for t in (a, b) if t is not None})
    out: list[Snapshot] = []
    for at in moments:
        cards: list[Waypoint] = []
        for card, issued, completed in born:
            if issued > at:
                continue
            closed = completed is not None and completed <= at
            now = str(card.get("status", ""))
            status = "done" if closed else ("ready" if now == "done" else now)
            cards.append(card | {"status": status})
        out.append((at, {"waypoints": cards}))
    return out


def test_the_shared_snapshots_equal_the_copied_ones_on_a_large_queue() -> None:
    """nemik:W2069: sharing the cards changes nothing a reader sees, on 400 cards."""
    doc = _large(400)
    assert stamp_snapshots(doc) == _old_snapshots(doc)


class _Draws:
    """A repeatable stream of small numbers: a linear congruential generator, not for secrets."""

    def __init__(self, seed: int) -> None:
        self.state = seed + 1

    def below(self, bound: int) -> int:
        """Draw the next number in 0 to bound - 1.

        Returns:
            The number.

        """
        self.state = (self.state * 1103515245 + 12345) % 2147483648
        return (self.state >> 8) % bound


def _random_queue(draws: _Draws) -> QueueDoc:
    """Make a queue of random cards with the stamp cases the fallback meets.

    Stamps come from a small pool, so several cards share a moment; a card may have no
    `issued_at`, an empty or missing `completed`, or a `completed` before its `issued_at`; and its
    status is any of those the queue holds, including done on a card with no completion stamp.

    Returns:
        The queue document.

    """
    pool = [f"2026-11-0{1 + n // 24}T{n % 24:02d}:00:00Z" for n in range(STAMP_POOL)]
    cards: list[Waypoint] = []
    for n in range(draws.below(MAX_CARDS)):
        card: Waypoint = {
            "symbol": f"W{n}",
            "status": STATUSES[draws.below(len(STATUSES))],
        }
        if draws.below(TENTHS) != 0:
            card["issued_at"] = pool[draws.below(STAMP_POOL)]
        case = draws.below(TENTHS)
        if case < CLOSED_BELOW:
            done_at = datetime.fromisoformat(pool[draws.below(STAMP_POOL)])
            card["completed"] = done_at.strftime(COMPACT)
        elif case < EMPTY_BELOW:
            card["completed"] = ""
        cards.append(card)
    return {"waypoints": cards}


def test_the_shared_snapshots_equal_the_copied_ones_on_random_queues() -> None:
    """nemik:W2069: equal to the old loop on 40 seeds, 0 to 89 cards, shared and odd stamps."""
    for seed in range(SEEDS):
        doc = _random_queue(_Draws(seed))
        assert stamp_snapshots(doc) == _old_snapshots(doc), seed


def test_a_weekly_pass_leaves_the_shared_cards_unchanged() -> None:
    """nemik:W2069: a consumer that changed a card would change it in every snapshot that shares it.

    weekly() reads each snapshot and the time each card spent in each status; the cards come out
    of it as they went in, so the sharing cannot show one consumer's edit to another.
    """
    doc = _large(200)
    snaps = stamp_snapshots(doc)
    before = copy.deepcopy(snaps)
    weekly(snaps)
    assert snaps == before


def test_a_queue_of_a_thousand_cards_stays_within_a_small_heap() -> None:
    """nemik:W2069: the heap the snapshots take is linear in the cards, so it stays under 64 MiB.

    The fixed code takes 7.9 MiB at its peak for these 1000 cards, so the bound has room for the
    machine and a small growth. The copying version held a dict per card per moment, some 800
    thousand for these 1000 cards (161 MiB traced), and the 2000-card queue the pod builds took
    1.3 GiB.
    """
    doc = _large(1000)
    tracemalloc.start()
    try:
        snaps = stamp_snapshots(doc)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert len(snaps) > len(doc["waypoints"])
    assert peak < SMALL_HEAP


def test_no_queue_file_is_no_snapshots(tmp_path: Path) -> None:
    """With neither git history nor a queue file there is nothing to read."""
    assert snapshots(tmp_path) == []


def test_since_never_falls_back_to_the_stamps(tmp_path: Path) -> None:
    """`since` asks about commits, so a queue outside git answers it with nothing."""
    _queue(tmp_path)
    assert snapshots(tmp_path, since="2026-01-01") == []
