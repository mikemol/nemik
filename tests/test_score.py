"""nemik:W131: WV:1 vectors -> declared bands; unscored and invalid are visible, never a zero."""

import json

import pytest

from nemik.adapter import NEMIK, queue_graph, waypoint_uri
from nemik.score import band, load_bands

B = load_bands()
V = "WV:1/R:{R}/E:{E}/C:{C}/I:{I}/A:{A}/X:N/S:{S}/F:K/W:N"


def vec(R="L", E="N", C="N", I="N", A="N", S="U"):
    return V.format(R=R, E=E, C=C, I=I, A=A, S=S)


@pytest.mark.parametrize(
    ("v", "want"),
    [
        # luthen's W137 calibration: crossing a boundary from the host is critical only with some
        # impact; with every impact N it is a boundary crossing and lands in high.
        (vec(R="H", S="C", I="L"), "critical"),
        (vec(R="H", S="C", C="L"), "critical"),
        (vec(R="H", S="C", A="L"), "critical"),
        (vec(R="H", S="C"), "high"),
        (vec(E="Y", C="H"), "critical"),
        # Cluster reach floods high unless something is at stake; host reach with availability at
        # risk is high, and bare host or cluster reach is elevated.
        (vec(R="C", I="L"), "high"),
        (vec(R="C", A="L"), "high"),
        (vec(R="C"), "elevated"),
        (vec(R="H", A="H"), "high"),
        (vec(R="H"), "elevated"),
        (vec(S="C"), "high"),
        (vec(R="T"), "elevated"),
        (vec(), "low"),
        (vec(C="L"), "normal"),  # local, some impact: no rule -> unmatched
    ],
)
def test_band_table(v, want) -> None:
    assert band(v, B)[0] == want


def test_unscored_and_invalid_take_the_declared_default_and_say_why() -> None:
    assert band(None, B) == (B.unscored, "unscored")
    b, why = band("WV:1/R:H", B)
    assert b == B.unscored and why.startswith("invalid:")


def test_table_refuses_a_default_outside_its_order() -> None:
    with pytest.raises(ValueError, match="not in order"):
        load_bands('order = ["a"]\nunscored = "b"\nunmatched = "a"\n')


def test_adapter_carries_the_vector_as_written(tmp_path) -> None:
    q = tmp_path / "q.json"
    q.write_text(
        json.dumps(
            {
                "version": 1,
                "project_root": "/x",
                "counter": 1,
                "residue": [],
                "waypoints": [
                    {
                        "symbol": "W1",
                        "title": "t",
                        "status": "ready",
                        "vector": vec(R="H", S="C"),
                        "vector_source": "agent",
                    }
                ],
            }
        )
    )
    g = queue_graph("r", q)
    n = waypoint_uri("r", "W1")
    assert str(g.value(n, NEMIK.vector)) == vec(R="H", S="C")
    assert str(g.value(n, NEMIK.vectorSource)) == "agent"
