# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W131: WV:1 vectors -> declared bands; unscored and invalid are visible, never a zero."""

import json
from pathlib import Path

import pytest

from nemik.adapter import NEMIK, queue_graph, waypoint_uri
from nemik.score import band, load_bands, load_guarantees, tagged_band

B = load_bands()
V = "WV:1/R:{R}/E:{E}/C:{C}/I:{I}/A:{A}/X:N/S:{S}/F:K/W:N"


def vec(
    *,
    r: str = "L",
    e: str = "N",
    c: str = "N",
    i: str = "N",
    a: str = "N",
    s: str = "U",
) -> str:
    """Build a WV:1 vector string from the given metric values.

    Returns:
        The vector.

    """
    return V.format(R=r, E=e, C=c, I=i, A=a, S=s)


def test_a_card_tagged_velocity_is_in_the_band_above_critical() -> None:
    """nemik:W1077: the owner's tag puts the card first, whatever its vector says."""
    assert B.order[0] == "velocity"
    assert B.rank("velocity") < B.rank("critical")
    assert tagged_band("normal", "unscored", {"velocity", "docs"}) == (
        "velocity",
        "touches velocity",
    )
    assert tagged_band("high", "S:C", {"docs"}) == ("high", "S:C")


def test_the_floor_names_critical_so_a_ready_velocity_card_is_not_skipped() -> None:
    """The guarantee holds at critical and above, which includes velocity, the band above it."""
    assert load_guarantees(bands=B).floor == "critical"


@pytest.mark.parametrize(
    ("v", "want"),
    [
        # luthen's W137 calibration: crossing a boundary from the host is critical only with some
        # impact; with every impact N it is a boundary crossing and lands in high.
        (vec(r="H", s="C", i="L"), "critical"),
        (vec(r="H", s="C", c="L"), "critical"),
        (vec(r="H", s="C", a="L"), "critical"),
        (vec(r="H", s="C"), "high"),
        (vec(e="Y", c="H"), "critical"),
        # Cluster reach floods high unless something is at stake; host reach with availability at
        # risk is high, and bare host or cluster reach is elevated.
        (vec(r="C", i="L"), "high"),
        (vec(r="C", a="L"), "high"),
        (vec(r="C"), "elevated"),
        (vec(r="H", a="H"), "high"),
        (vec(r="H"), "elevated"),
        (vec(s="C"), "high"),
        (vec(r="T"), "elevated"),
        (vec(), "low"),
        (vec(c="L"), "normal"),  # local, some impact: no rule -> unmatched
    ],
)
def test_band_table(v: str, want: str) -> None:
    """Band table."""
    assert band(v, B)[0] == want


def test_unscored_and_invalid_take_the_declared_default_and_say_why() -> None:
    """Unscored and invalid take the declared default and say why."""
    assert band(None, B) == (B.unscored, "unscored")
    b, why = band("WV:1/R:H", B)
    assert b == B.unscored
    assert why.startswith("invalid:")


def test_table_refuses_a_default_outside_its_order() -> None:
    """Table refuses a default outside its order."""
    with pytest.raises(ValueError, match="not in order"):
        load_bands('order = ["a"]\nunscored = "b"\nunmatched = "a"\n')


def test_adapter_carries_the_vector_as_written(tmp_path: Path) -> None:
    """Adapter carries the vector as written."""
    q = tmp_path / "q.json"
    payload: dict[str, object] = {
        "version": 1,
        "project_root": "/x",
        "counter": 1,
        "residue": [],
        "waypoints": [
            {
                "symbol": "W1",
                "title": "t",
                "status": "ready",
                "vector": vec(r="H", s="C"),
                "vector_source": "agent",
            }
        ],
    }
    q.write_text(json.dumps(payload))
    g = queue_graph("r", q)
    n = waypoint_uri("r", "W1")
    assert str(g.value(n, NEMIK.vector)) == vec(r="H", s="C")
    assert str(g.value(n, NEMIK.vectorSource)) == "agent"
