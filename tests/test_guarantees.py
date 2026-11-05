# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W133 (luthen-observability:W190 §3): the ordering guarantees nemik-rank --check refuses on.

Each guarantee is falsifiable: --check names the rule and the pair of items that broke it.
"""

from importlib.resources import files

import pytest
from rdflib import Graph, Literal, URIRef

from nemik.adapter import NEMIK, OSLC_CM, STATE, waypoint_uri, workstream_uri
from nemik.rank import inversion, main, policy_blocks, rank, unscored
from nemik.score import Weights, load_bands, load_guarantees

W = Weights(local=1, peer=2, peer_blocked=8)
UNSCORED = 2
B = load_bands()
# I:L, not N: since luthen's W137 calibration a host-reach boundary crossing is critical only with
# some impact, and these tests mean "critical" by R:H S:C.
V = "WV:1/R:{R}/E:N/C:N/I:L/A:N/X:N/S:{S}/F:K/W:N"


def _wp(
    g: Graph,
    sym: str,
    status: str = "ready",
    *,
    pos: int | None = None,
    vector: str | None = None,
) -> URIRef:
    n = waypoint_uri("a", sym)
    g.add((n, OSLC_CM.state, STATE[status]))
    g.add((n, NEMIK.workstream, workstream_uri("a")))
    g.add((n, NEMIK.symbol, Literal(sym)))
    if pos is not None:
        g.add((n, NEMIK.queuePosition, Literal(pos)))
    if vector:
        g.add((n, NEMIK.vector, Literal(vector)))
    return n


def _tag(g: Graph, n: URIRef, touches: tuple[str, ...]) -> URIRef:
    for t in touches:
        g.add((n, NEMIK.touches, Literal(t)))
    return n


def test_packaged_guarantees_load_and_refuse_an_unknown_floor() -> None:
    """Packaged guarantees load and refuse an unknown floor."""
    guar = load_guarantees()
    assert guar.floor in B.order
    assert [p.name for p in guar.policies] == ["trust-boundary"]
    text = 'order = ["a"]\nunscored = "a"\nunmatched = "a"\n[guarantee]\nfloor = "z"\n'
    with pytest.raises(ValueError, match=r"guarantee\.floor"):
        load_guarantees(text)


def test_inversion_names_the_next_item_and_the_urgent_one() -> None:
    """Inversion names the next item and the urgent one."""
    g = Graph()
    _wp(g, "W1", pos=0)  # unscored -> normal, and mtools works it next
    _wp(g, "W2", pos=1, vector=V.format(R="H", S="C"))  # critical
    guar = load_guarantees()
    found = inversion(g, "a", rank(g, "a", W), B, guar)
    assert found is not None
    nxt, urgent = found
    assert (nxt["symbol"], nxt["band_name"]) == ("W1", "normal")
    assert (urgent["symbol"], urgent["band_name"]) == ("W2", "critical")


def test_no_inversion_when_the_next_item_is_at_the_floor_or_nothing_reaches_it() -> (
    None
):
    """No inversion when the next item is at the floor or nothing reaches it."""
    g = Graph()
    _wp(g, "W1", pos=0, vector=V.format(R="H", S="C"))
    _wp(g, "W2", pos=1)
    assert inversion(g, "a", rank(g, "a", W), B, load_guarantees()) is None
    g2 = Graph()
    _wp(g2, "W1", pos=0)
    _wp(
        g2, "W2", pos=1, vector=V.format(R="C", S="U")
    )  # high: below the packaged floor
    assert inversion(g2, "a", rank(g2, "a", W), B, load_guarantees()) is None


def test_policy_blocks_a_ready_item_sharing_a_surface_with_an_open_member() -> None:
    """Policy blocks a ready item sharing a surface with an open member."""
    g = Graph()
    _tag(g, _wp(g, "W1", "blocked"), ("trust-boundary", "opa"))  # a member by tag, open
    _tag(g, _wp(g, "W2"), ("opa", "dashboard"))  # shares the opa surface
    _tag(g, _wp(g, "W3"), ("dashboard",))  # shares nothing with a member
    _tag(
        g, _wp(g, "W4", vector=V.format(R="L", S="C")), ("rbac",)
    )  # a member by vector
    _tag(g, _wp(g, "W5"), ("rbac",))
    _tag(
        g, _wp(g, "W6"), ("opa", "trust-boundary")
    )  # a member itself: never blocked by W1
    assert policy_blocks(g, "a", load_guarantees()) == [
        ("W2", "W1", "trust-boundary", ["opa"]),
        ("W2", "W6", "trust-boundary", ["opa"]),
        ("W5", "W4", "trust-boundary", ["rbac"]),
    ]


def test_a_done_member_blocks_nothing_and_the_class_tag_alone_is_no_surface() -> None:
    """A done member blocks nothing and the class tag alone is no surface."""
    g = Graph()
    _tag(g, _wp(g, "W1", "done"), ("trust-boundary", "opa"))
    _tag(g, _wp(g, "W2"), ("opa",))
    _tag(g, _wp(g, "W3", "blocked"), ("trust-boundary",))
    assert policy_blocks(g, "a", load_guarantees()) == []


def test_unscored_counts_open_waypoints_without_a_vector() -> None:
    """Unscored counts open waypoints without a vector."""
    g = Graph()
    _wp(g, "W1")
    _wp(g, "W2", "blocked")
    _wp(g, "W3", "done")
    _wp(g, "W4", vector=V.format(R="L", S="U"))
    assert unscored(g, "a") == UNSCORED


def test_check_names_rule_and_pair_and_exits_one(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Check names rule and pair and exits one."""
    g = Graph()
    _tag(g, _wp(g, "W1", pos=0), ("opa",))
    _tag(g, _wp(g, "W2", pos=1, vector=V.format(R="H", S="C")), ("opa",))
    with pytest.raises(SystemExit) as e:
        main(["a", "--check"], g=g)
    out = capsys.readouterr().out.splitlines()
    assert e.value.code == 1
    assert (
        "rank: INVERSION a: next is W1 (normal) while W2 is ready at critical (floor critical)"
        in out
    )
    assert "rank: POLICY a: W1 is ready while trust-boundary W2 is open on opa" in out
    assert "rank: UNSCORED a 1" in out
    assert not any(line.startswith("rank: OK") for line in out)


def test_check_ok_still_reports_the_unscored_census(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Check ok still reports the unscored census."""
    g = Graph()
    _wp(g, "W1", pos=0)
    with pytest.raises(SystemExit) as e:
        main(["a", "--check"], g=g)
    out = capsys.readouterr().out.splitlines()
    assert e.value.code == 0
    assert out == [
        "rank: UNSCORED a 1",
        "rank: OK a: next ready item carries the top cross-repo weight",
    ]


def test_only_narrows_the_blocked_dependents_to_named_tags() -> None:
    """nemik:W138 (luthen §3): only tenant-facing rollouts wait on an open trust-boundary item."""
    text = (
        files("nemik.data")
        .joinpath("bands.toml")
        .read_text()
        .replace(
            'tag = "trust-boundary"\n',
            'tag = "trust-boundary"\nonly = ["tenant-rollout"]\n',
            1,
        )
    )
    g = Graph()
    _tag(g, _wp(g, "W1", "blocked"), ("trust-boundary", "opa"))
    _tag(g, _wp(g, "W2"), ("opa", "tenant-rollout"))  # in scope: blocked
    _tag(
        g, _wp(g, "W3"), ("opa", "dashboard")
    )  # same surface, not a rollout: not blocked
    assert policy_blocks(g, "a", load_guarantees(text)) == [
        ("W2", "W1", "trust-boundary", ["opa"])
    ]
