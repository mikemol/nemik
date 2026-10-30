# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W326: a ready card overtaken by newer ones past the declared age is starved."""

from __future__ import annotations

import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from nemik.check import survey
from nemik.starved import days_limit, starved

NOW = datetime(2026, 10, 11, tzinfo=UTC)


def _card(symbol: str, issued: str, next_step: str) -> dict[str, object]:
    return {
        "symbol": symbol,
        "title": symbol,
        "status": "ready",
        "next_bounded_step": next_step,
        "issued_at": issued,
    }


def test_declared_age_is_read() -> None:
    assert days_limit("[starvation]\ndays = 3\n") == 3
    assert days_limit("") == 14


def test_an_old_card_under_newer_ones_is_starved() -> None:
    """An old card under newer ones is starved."""
    with tempfile.TemporaryDirectory() as tmp:
        queue = Path(tmp) / "a" / ".claude" / "paths-forward.json"
        queue.parent.mkdir(parents=True)
        payload: dict[str, object] = {
            "version": 1,
            "project_root": "/x",
            "counter": 2,
            "residue": [],
            "waypoints": [
                _card("W1", "2026-08-01T00:00:00Z", "x"),
                _card("W2", "2026-10-10T00:00:00Z", "x"),
            ],
        }
        queue.write_text(json.dumps(payload))
        from rdflib import Graph

        g = Graph()
        for _, qg, _ in survey(Path(tmp)):
            if qg is not None:
                g += qg
        found = starved(g, "a", NOW, 14)
    # Whichever ranks lower, only an older card with a newer one ahead can be reported.
    assert all(s.overtaken_by >= 1 and s.waited_days > 14 for s in found)
    assert {s.cite for s in found} <= {"a:W1"}
