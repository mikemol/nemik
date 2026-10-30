# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W602: what nemik writes as iCalendar parses by the standard's reader, whole."""

import json
from pathlib import Path

from icalendar import Calendar

from nemik.adapter import queue_graph
from nemik.blocks import AskRow
from nemik.calwrite import feed
from nemik.vtodo import calendar, vtodos

TITLE = "trip; to, the lake \\ " + "x" * 120
ASK: AskRow = {
    "ref": "life:W21",
    "title": "Resume, approve",
    "category": "needs-you",
    "ask": "life-0e | operator: decide approve notes/resume.md as-is, or say what to change",
    "waiting": ["life:W10"],
    "same_ask": [],
    "last_activity": "2026-09-28T13:02:06Z",
}


def _life(tmp_path: Path) -> Path:
    """Write a queue with one dated card, one recurring card in a named zone, one long title.

    Args:
        tmp_path: A scratch directory.

    Returns:
        The queue file.

    """
    residue: list[str] = []
    cards: list[dict[str, str]] = [
        {"symbol": "W9", "title": TITLE, "status": "ready", "due": "20261001T220000Z"},
        {
            "symbol": "W30",
            "title": "drill",
            "status": "ready",
            "dtstart": "TZID=America/Detroit:20261005T180000",
            "rrule": "FREQ=WEEKLY;BYDAY=MO",
        },
    ]
    state: dict[str, object] = {
        "version": 1,
        "project_root": "/x",
        "counter": 30,
        "residue": residue,
        "waypoints": cards,
    }
    path = tmp_path / "life.json"
    path.write_text(json.dumps(state))
    return path


def test_the_calendar_feed_parses_and_keeps_the_title_whole(tmp_path: Path) -> None:
    """Escaping and folding survive the standard's reader; a named zone brings its VTIMEZONE."""
    graph = queue_graph("life", _life(tmp_path))
    parsed = Calendar.from_ical(feed(graph, ["life"]))
    kinds = [component.name for component in parsed.walk()]
    assert "VTIMEZONE" in kinds
    summaries = [str(component.get("SUMMARY")) for component in parsed.walk("VEVENT")]
    assert any(summary.endswith(TITLE) or TITLE in summary for summary in summaries)


def test_the_needs_you_calendar_parses_with_its_summary_unescaped() -> None:
    """The VTODO projection is valid iCalendar and its comma comes back as a comma."""
    asks: list[AskRow] = [ASK]
    parsed = Calendar.from_ical(calendar(vtodos(asks, {"life"})))
    (todo,) = list(parsed.walk("VTODO"))
    assert "approve notes/resume.md as-is, or say what to change" in str(
        todo.get("SUMMARY")
    )
