"""nemik:W178: low-hanging fruit as one virtual row."""

from rdflib import Graph, Literal

from nemik.adapter import NEMIK
from nemik.rank import fruit


def test_members_are_leaves_moving_nothing_or_tagged() -> None:
    rows = [
        {"symbol": "W1", "downstream": 0},
        {"symbol": "W2", "downstream": 5},
        {"symbol": "W3", "downstream": 0},
    ]
    f = fruit(Graph(), "a", rows)
    assert f is not None
    assert f["members"] == ["W1", "W3"] and f["class_weight"] == 2


def test_tagged_item_joins_with_its_downstream() -> None:
    from nemik.adapter import waypoint_uri, workstream_uri

    g = Graph()
    n = waypoint_uri("a", "W2")
    g.add((n, NEMIK.symbol, Literal("W2")))
    g.add((n, NEMIK.workstream, workstream_uri("a")))
    g.add((n, NEMIK.touches, Literal("fruit")))
    f = fruit(g, "a", [{"symbol": "W2", "downstream": 3}])
    assert f is not None
    assert f["members"] == ["W2"] and f["class_weight"] == 4


def test_no_members_no_row() -> None:
    assert fruit(Graph(), "a", [{"symbol": "W1", "downstream": 2}]) is None


def _graph(spec):
    """{symbol: [what it enables]} as ready waypoints in repo a."""
    from nemik.adapter import OSLC_CM, waypoint_uri, workstream_uri

    g = Graph()
    for sym, en in spec.items():
        n = waypoint_uri("a", sym)
        g.add((n, NEMIK.symbol, Literal(sym)))
        g.add((n, NEMIK.workstream, workstream_uri("a")))
        g.add(
            (
                n,
                OSLC_CM.state,
                NEMIK.Ready if not en or en != ["blocked"] else NEMIK.Blocked,
            )
        )
        for t in en:
            if t != "blocked":
                g.add((n, NEMIK.enables, waypoint_uri("b", t)))
                g.add((waypoint_uri("b", t), OSLC_CM.state, NEMIK.Blocked))
    return g


def test_pile_outweighs_a_deep_item_and_leads() -> None:
    from nemik.rank import load_weights, rank

    g = _graph(
        {
            "W1": ["W90"],
            "W2": [],
            "W3": [],
            "W4": [],
            "W5": [],
            "W6": [],
            "W7": [],
            "W8": [],
            "W9": [],
            "W10": [],
        }
    )  # W1 moves one stalled peer (8); fruit W2-W10 weigh 9
    rows = rank(g, "a", load_weights())
    assert rows[0]["symbol"] == "W2" and rows[0]["fruit"]["class_weight"] == 9


def test_deep_item_outweighing_the_pile_leads() -> None:
    from nemik.rank import load_weights, rank

    g = _graph({"W1": ["W90"], "W2": [], "W3": []})  # one stalled peer (8) > fruit 2
    assert rank(g, "a", load_weights())[0]["symbol"] == "W1"


def test_a_working_fruit_member_holds_the_class_slot() -> None:
    """luthen-observability 2026-10-02: with a fruit member working, no other member inherits the class weight."""
    from nemik.adapter import OSLC_CM, waypoint_uri
    from nemik.rank import load_weights, rank

    g = _graph(
        {
            "W1": ["W90"],
            "W2": [],
            "W3": [],
            "W4": [],
            "W5": [],
            "W6": [],
            "W7": [],
            "W8": [],
            "W9": [],
            "W10": [],
        }
    )
    g.set((waypoint_uri("a", "W2"), OSLC_CM.state, NEMIK.Working))
    rows = rank(g, "a", load_weights())
    assert rows[0]["symbol"] == "W1" and not any("fruit" in r for r in rows)
