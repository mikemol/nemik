# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W949: an outbox appends its repo's log activities, or says the log was not read."""

import json
from pathlib import Path

from rdflib import Graph

from nemik.adapter import queue_graph, waypoint_uri
from nemik.ask import quoted
from nemik.hostroot_cli import log_document
from nemik.outbox import outbox
from nemik.waitlog import activity

FIRST = 1_700_000_000_000_000_000
SECOND = FIRST + 60_000_000_000
LATE = "2026-10-24T02:01:00Z"
EARLY = "2026-10-24T02:00:00Z"


def _queue(tmp_path: Path) -> Graph:
    """Read a queue of repo a with one ready card.

    Returns:
        The queue's graph.

    """
    residue: list[str] = []
    cards: list[dict[str, object]] = [{"symbol": "W1", "title": "t", "status": "ready"}]
    state: dict[str, object] = {
        "version": 1,
        "project_root": "/a",
        "counter": 1,
        "residue": residue,
        "waypoints": cards,
    }
    path = tmp_path / "a.json"
    path.write_text(json.dumps(state), encoding="utf-8")
    return queue_graph("a", path)


def _line(waiting: str, cite: str, blocker: str, at_ns: int, when: str) -> str:
    """Make a VictoriaLogs line holding the wait record waitlog would send.

    Returns:
        The line.

    """
    message = activity(waiting, cite, 3, blocker, at_ns)
    return f'{{"_msg": {quoted(message)}, "_time": {quoted(when)}}}'


def _log_file(tmp_path: Path) -> Path:
    """Write the log file nemik-hostroot would: two of repo a's records and one of repo b's.

    Returns:
        The file.

    """
    lines = [
        _line("a", "a:W5", "b:W1", SECOND, LATE),
        _line("a", "a:W6", "b:W2", FIRST, EARLY),
        _line("b", "b:W9", "a:W1", FIRST, EARLY),
    ]
    path = tmp_path / "log-activities.json"
    path.write_text(log_document(lines, "2026-10-24T03:00:00Z"), encoding="utf-8")
    return path


def test_the_repos_log_activities_follow_its_cards(tmp_path: Path) -> None:
    """Its own two, oldest first, after the card; another repo's is not here; no summary."""
    text = outbox("a", _queue(tmp_path), frozenset(), _log_file(tmp_path))
    assert '"totalItems": 3' in text
    assert text.index("urn:nemik:a/W1") < text.index("a:W6 has waited")
    assert text.index("a:W6 has waited") < text.index("a:W5 has waited")
    assert "b:W9" not in text
    assert "not part of this collection" not in text


def test_an_activity_naming_a_withheld_card_is_dropped(tmp_path: Path) -> None:
    """Withholding a:W6 removes the activity that names it from the document."""
    hidden = frozenset({str(waypoint_uri("a", "W6"))})
    text = outbox("a", _queue(tmp_path), hidden, _log_file(tmp_path))
    assert "a:W6" not in text
    assert "a:W5 has waited" in text


def test_no_file_or_an_unreadable_one_is_said_in_the_summary(tmp_path: Path) -> None:
    """The collection says the log was not read, rather than looking complete."""
    graph = _queue(tmp_path)
    broken = tmp_path / "broken.json"
    broken.write_text("not a header", encoding="utf-8")
    for given in (None, tmp_path / "missing.json", broken):
        text = outbox("a", graph, frozenset(), given)
        assert "not part of this collection" in text
        assert '"totalItems": 1' in text
