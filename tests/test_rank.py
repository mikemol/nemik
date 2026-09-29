from rdflib import Graph, Literal

from nemik.adapter import NEMIK, OSLC_CM, STATE, waypoint_uri
from nemik.rank import Weights, downstream_weight, load_weights

W = Weights(local=1, peer=2, peer_blocked=8)


def _wp(g: Graph, repo: str, sym: str, status: str = "ready"):
    node = waypoint_uri(repo, sym)
    g.add((node, OSLC_CM.state, STATE[status]))
    return node


def test_packaged_weights_rank_stalled_peers_highest() -> None:
    w = load_weights()
    assert w.peer_blocked > w.peer > w.local


def test_weights_override_from_text() -> None:
    assert load_weights("local = 2\npeer = 5\npeer_blocked = 9\n") == Weights(2, 5, 9)


def test_short_chain_with_stalled_peer_outranks_long_local_reach() -> None:
    # luthen's case (nemik:W38): W79 reaches a long local chain; W45 unblocks a stalled peer.
    g = Graph()
    w79, w45 = _wp(g, "a", "W79"), _wp(g, "a", "W45")
    prev = w79
    for i in range(5):
        nxt = _wp(g, "a", f"W{100 + i}")
        g.add((prev, NEMIK.enables, nxt))
        prev = nxt
    stalled = _wp(g, "b", "W124", "blocked")
    g.add((stalled, NEMIK.waitsFor, w45))
    assert downstream_weight(g, w79, W) == 5
    assert downstream_weight(g, w45, W) == 8


def test_transitive_across_three_repos_and_done_is_pruned() -> None:
    g = Graph()
    a1, b1, c1 = _wp(g, "a", "W1"), _wp(g, "b", "W1"), _wp(g, "c", "W1")
    g.add((a1, NEMIK.enables, b1))
    g.add((b1, NEMIK.enables, c1))
    assert downstream_weight(g, a1, W) == 4  # two reachable peers
    g.add((b1, OSLC_CM.state, STATE["done"]))
    g.remove((b1, OSLC_CM.state, STATE["ready"]))
    assert downstream_weight(g, a1, W) == 0


def test_cycle_terminates_and_counts_each_node_once() -> None:
    g = Graph()
    x, y = _wp(g, "a", "W1"), _wp(g, "a", "W2")
    g.add((x, NEMIK.enables, y))
    g.add((y, NEMIK.enables, x))
    assert downstream_weight(g, x, W) == 1


def test_rank_orders_ready_items_by_weight_then_symbol() -> None:
    from nemik.adapter import workstream_uri
    from nemik.rank import rank

    g = Graph()
    ws = workstream_uri("a")
    lo, hi, blk = _wp(g, "a", "W2"), _wp(g, "a", "W9"), _wp(g, "a", "W3", "blocked")
    for n, s in ((lo, "W2"), (hi, "W9"), (blk, "W3")):
        g.add((n, NEMIK.workstream, ws))
        g.add((n, NEMIK.symbol, Literal(s)))
    g.add((_wp(g, "b", "W1", "blocked"), NEMIK.waitsFor, hi))
    rows = rank(g, "a", W)
    assert [r["symbol"] for r in rows] == ["W9", "W2"]  # blocked W3 excluded
    assert rows[0]["downstream"] == 8  # the raw cross-repo sum
    assert rows[0]["weight"] > rows[1]["weight"]  # `weight` carries the composed order (W132)


def _ready(g: Graph, repo: str, sym: str, pos: int):
    from nemik.adapter import workstream_uri
    n = _wp(g, repo, sym)
    g.add((n, NEMIK.workstream, workstream_uri(repo)))
    g.add((n, NEMIK.symbol, Literal(sym)))
    g.add((n, NEMIK.queuePosition, Literal(pos)))
    return n


def test_drift_fires_when_next_item_is_outweighed_and_clears_when_it_leads() -> None:
    from nemik.rank import drift

    g = Graph()
    first, heavy = _ready(g, "a", "W1", 0), _ready(g, "a", "W2", 1)
    stalled = _wp(g, "b", "W9", "blocked")
    g.add((stalled, NEMIK.waitsFor, heavy))
    nxt, top = drift(g, "a", W)
    assert (nxt["symbol"], top["symbol"]) == ("W1", "W2")
    g.remove((stalled, NEMIK.waitsFor, heavy))
    g.add((stalled, NEMIK.waitsFor, first))
    assert drift(g, "a", W) is None


def test_umbrella_children_are_direct_feeders_not_transitive_leaves() -> None:
    # paperkit's W59 (nemik:W112): W59 waits on W60, which W132 and W78 enable.
    from nemik.rank import children, frontier

    g = Graph()
    w59, w60, w132, w78 = (_wp(g, "p", s) for s in ("W59", "W60", "W132", "W78"))
    g.add((w59, NEMIK.waitsFor, w60))
    for leaf in (w132, w78):
        g.add((leaf, NEMIK.enables, w60))
    assert children(g, w59) == {w60}
    assert frontier(g, w59)[0] == {w132, w78}


def _row(sym, operator=0, band=-3, weight=0):
    return {"symbol": sym, "operator": operator, "band": band, "weight": weight}


def test_compose_lexicographic_is_one_objective_per_tier() -> None:
    from nemik.rank import Composition, compose

    rows = [_row("W1", band=-3, weight=50), _row("W2", band=-1, weight=0), _row("W3", operator=1, band=-4)]
    lex = Composition((("operator",), ("band",), ("weight",)), {})
    assert [r["symbol"] for r in compose(rows, lex)] == ["W3", "W2", "W1"]


def test_compose_pareto_front_then_scalarized_within_it() -> None:
    from nemik.rank import Composition, compose

    # W1 (band -3, weight 50) and W2 (band -1, weight 0) are both on the first front of
    # [band, weight]; W4 is dominated by W1. Inside the front, 100 per band step beats 50 weight.
    rows = [_row("W1", band=-3, weight=50), _row("W2", band=-1, weight=0), _row("W4", band=-3, weight=10)]
    comp = Composition((("operator",), ("band", "weight")), {"band": 100, "weight": 1})
    assert [r["symbol"] for r in compose(rows, comp)] == ["W2", "W1", "W4"]
    # Weight the trade the other way and the same front flips; the dominated W4 stays last.
    comp = Composition((("operator",), ("band", "weight")), {"band": 10, "weight": 1})
    assert [r["symbol"] for r in compose(rows, comp)] == ["W1", "W2", "W4"]


def test_operator_asks_rank_first_under_the_packaged_composition() -> None:
    from nemik.rank import compose, load_composition

    rows = [_row("W1", band=0, weight=999), _row("W2", operator=1, band=-4, weight=0)]
    assert [r["symbol"] for r in compose(rows, load_composition())] == ["W2", "W1"]


def test_composition_refuses_an_unknown_objective() -> None:
    import pytest

    from nemik.rank import load_composition

    with pytest.raises(ValueError, match="unknown objectives"):
        load_composition('[order]\ntiers = [["age"]]\n')
