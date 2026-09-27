from rdflib import Graph

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
