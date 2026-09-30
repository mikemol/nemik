"""nemik:W133 (luthen-observability:W190 §3): the ordering guarantees nemik-rank --check refuses on.

Each guarantee is falsifiable: --check names the rule and the pair of items that broke it.
"""

import pytest
from rdflib import Graph, Literal

from nemik.adapter import NEMIK, OSLC_CM, STATE, waypoint_uri, workstream_uri
from nemik.rank import Weights, inversion, main, policy_blocks, rank, unscored
from nemik.score import load_bands, load_guarantees

W = Weights(local=1, peer=2, peer_blocked=8)
B = load_bands()
V = "WV:1/R:{R}/E:N/C:N/I:N/A:N/X:N/S:{S}/F:K/W:N"


def _wp(g: Graph, sym: str, status: str = "ready", pos: int | None = None, vector: str | None = None,
        touches: tuple[str, ...] = ()):
    n = waypoint_uri("a", sym)
    g.add((n, OSLC_CM.state, STATE[status]))
    g.add((n, NEMIK.workstream, workstream_uri("a")))
    g.add((n, NEMIK.symbol, Literal(sym)))
    if pos is not None:
        g.add((n, NEMIK.queuePosition, Literal(pos)))
    if vector:
        g.add((n, NEMIK.vector, Literal(vector)))
    for t in touches:
        g.add((n, NEMIK.touches, Literal(t)))
    return n


def test_packaged_guarantees_load_and_refuse_an_unknown_floor() -> None:
    guar = load_guarantees()
    assert guar.floor in B.order
    assert [p.name for p in guar.policies] == ["trust-boundary"]
    text = 'order = ["a"]\nunscored = "a"\nunmatched = "a"\n[guarantee]\nfloor = "z"\n'
    with pytest.raises(ValueError, match="guarantee.floor"):
        load_guarantees(text)


def test_inversion_names_the_next_item_and_the_urgent_one() -> None:
    g = Graph()
    _wp(g, "W1", pos=0)  # unscored -> normal, and mtools works it next
    _wp(g, "W2", pos=1, vector=V.format(R="H", S="C"))  # critical
    guar = load_guarantees()
    nxt, urgent = inversion(g, "a", rank(g, "a", W), B, guar)
    assert (nxt["symbol"], nxt["band_name"]) == ("W1", "normal")
    assert (urgent["symbol"], urgent["band_name"]) == ("W2", "critical")


def test_no_inversion_when_the_next_item_is_at_the_floor_or_nothing_reaches_it() -> None:
    g = Graph()
    _wp(g, "W1", pos=0, vector=V.format(R="H", S="C"))
    _wp(g, "W2", pos=1)
    assert inversion(g, "a", rank(g, "a", W), B, load_guarantees()) is None
    g2 = Graph()
    _wp(g2, "W1", pos=0)
    _wp(g2, "W2", pos=1, vector=V.format(R="C", S="U"))  # high: below the packaged floor
    assert inversion(g2, "a", rank(g2, "a", W), B, load_guarantees()) is None


def test_policy_blocks_a_ready_item_sharing_a_surface_with_an_open_member() -> None:
    g = Graph()
    _wp(g, "W1", "blocked", touches=("trust-boundary", "opa"))  # a member by tag, open
    _wp(g, "W2", touches=("opa", "dashboard"))  # shares the opa surface
    _wp(g, "W3", touches=("dashboard",))  # shares nothing with a member
    _wp(g, "W4", vector=V.format(R="L", S="C"), touches=("rbac",))  # a member by vector
    _wp(g, "W5", touches=("rbac",))
    _wp(g, "W6", touches=("opa", "trust-boundary"))  # a member itself: never blocked by W1
    assert policy_blocks(g, "a", load_guarantees()) == [
        ("W2", "W1", "trust-boundary", ["opa"]),
        ("W2", "W6", "trust-boundary", ["opa"]),
        ("W5", "W4", "trust-boundary", ["rbac"]),
    ]


def test_a_done_member_blocks_nothing_and_the_class_tag_alone_is_no_surface() -> None:
    g = Graph()
    _wp(g, "W1", "done", touches=("trust-boundary", "opa"))
    _wp(g, "W2", touches=("opa",))
    _wp(g, "W3", "blocked", touches=("trust-boundary",))
    assert policy_blocks(g, "a", load_guarantees()) == []


def test_unscored_counts_open_waypoints_without_a_vector() -> None:
    g = Graph()
    _wp(g, "W1")
    _wp(g, "W2", "blocked")
    _wp(g, "W3", "done")
    _wp(g, "W4", vector=V.format(R="L", S="U"))
    assert unscored(g, "a") == 2


def test_check_names_rule_and_pair_and_exits_one(capsys) -> None:
    g = Graph()
    _wp(g, "W1", pos=0, touches=("opa",))
    _wp(g, "W2", pos=1, vector=V.format(R="H", S="C"), touches=("opa",))
    with pytest.raises(SystemExit) as e:
        main(["a", "--check"], g=g)
    out = capsys.readouterr().out.splitlines()
    assert e.value.code == 1
    assert "rank: INVERSION a: next is W1 (normal) while W2 is ready at critical (floor critical)" in out
    assert "rank: POLICY a: W1 is ready while trust-boundary W2 is open on opa" in out
    assert "rank: UNSCORED a 1" in out
    assert not any(line.startswith("rank: OK") for line in out)


def test_check_ok_still_reports_the_unscored_census(capsys) -> None:
    g = Graph()
    _wp(g, "W1", pos=0)
    with pytest.raises(SystemExit) as e:
        main(["a", "--check"], g=g)
    out = capsys.readouterr().out.splitlines()
    assert e.value.code == 0
    assert out == ["rank: UNSCORED a 1", "rank: OK a: next ready item carries the top cross-repo weight"]
