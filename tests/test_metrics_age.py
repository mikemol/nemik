"""nemik:W270: nemik-metrics reports how long the open waypoints have existed."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from nemik.adapter import queue_graph
from nemik.metrics import age_lines


def _wp(symbol: str, status: str, issued: str) -> dict:
    return {"symbol": symbol, "title": symbol, "status": status, "issued_at": issued}


def test_age_is_a_median_and_an_oldest_per_open_state(tmp_path: Path) -> None:
    path = tmp_path / "q.json"
    waypoints = [
        _wp("W1", "ready", "2026-10-01T00:00:00Z"),  # 4 days at the check
        _wp("W2", "ready", "2026-10-02T00:00:00Z"),  # 3
        _wp("W3", "ready", "2026-10-03T00:00:00Z"),  # 2
        _wp("W4", "done", "2026-09-01T00:00:00Z"),  # closed: not an age
    ]
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "project_root": "/x",
                "counter": 4,
                "residue": [],
                "waypoints": waypoints,
            }
        )
    )
    g = queue_graph("a", path)
    lines = age_lines("a", g, datetime(2026, 10, 5, tzinfo=UTC))
    day = 86400
    assert lines == [
        f'nemik_waypoint_age_seconds{{repo="a",state="ready",quantile="0.5"}} {3 * day}',
        f'nemik_waypoint_age_seconds{{repo="a",state="ready",quantile="1"}} {4 * day}',
    ]
