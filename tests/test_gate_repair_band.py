# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2039: within a repo a gate-repair card is a strict first tier, above all weight."""

from typing import cast

import pytest
from rdflib import Graph, Literal, URIRef

from nemik.adapter import NEMIK, OSLC_CM, STATE, waypoint_uri, workstream_uri
from nemik.rank import (
    Composition,
    RankOptions,
    RankRow,
    compose,
    load_composition,
    objectives,
    rank,
    rank_fleet,
)
from nemik.roundcli import NO_LANDINGS, round_document
from nemik.score import Weights, load_bands, tagged_band

W = Weights(local=1, peer=2, peer_blocked=8)
GATE = "gate-repair"
CUSTOM = """
order = ["gate-repair", "velocity", "normal"]
unscored = "normal"
unmatched = "normal"
gate = ["gate-repair"]
[tag]
gate-repair = "repairs-the-gate"
velocity = "velocity"
"""
# a gate band that is neither named gate-repair nor first in the order
RENAMED = """
order = ["velocity", "emergency", "normal"]
unscored = "normal"
unmatched = "normal"
gate = ["emergency"]
[tag]
emergency = "repairs"
velocity = "velocity"
"""
# the [tag] table is written velocity first, against the band order
VELOCITY_FIRST = """
order = ["gate-repair", "velocity", "normal"]
unscored = "normal"
unmatched = "normal"
[tag]
velocity = "velocity"
gate-repair = "repairs-the-gate"
"""
BASE = 'order = ["velocity", "normal"]\nunscored = "normal"\nunmatched = "normal"\n'
# enough blocked peers (8 each, half becomes salience) that a velocity card's weight passes the
# 100 units one band step is worth, which is where a band-step gate fails
FANOUT = 40


def _card(g: Graph, sym: str, *, tag: str | None = None, repo: str = "a") -> URIRef:
    node = waypoint_uri(repo, sym)
    g.add((node, OSLC_CM.state, STATE["ready"]))
    g.add((node, NEMIK.workstream, workstream_uri(repo)))
    g.add((node, NEMIK.symbol, Literal(sym)))
    if tag:
        g.add((node, NEMIK.touches, Literal(tag)))
    return node


def _feeding(g: Graph, node: URIRef, count: int) -> None:
    """Make `count` blocked peer cards wait for `node`, so it carries weight."""
    for i in range(count):
        peer = waypoint_uri("b", f"W{900 + i}")
        g.add((peer, OSLC_CM.state, STATE["blocked"]))
        g.add((peer, NEMIK.waitsFor, node))


def _symbols(rows: list[RankRow]) -> list[str]:
    return [r["symbol"] for r in rows]


def test_the_gate_repair_band_is_first_and_a_declared_gate() -> None:
    """The packaged bands list gate-repair first, above velocity, and declare it a gate."""
    bands = load_bands()
    assert bands.order[:2] == (GATE, "velocity")
    assert bands.gate == (GATE,)
    assert dict(bands.tags) == {GATE: GATE, "velocity": "velocity"}


def test_a_weightless_gate_card_ranks_first_through_rank() -> None:
    """Through rank(): a card with no weight outranks velocity cards carrying a lot of it."""
    g = Graph()
    _card(g, "W1", tag=GATE)
    heavy = _card(g, "W2", tag="velocity")
    normal = _card(g, "W3")
    _feeding(g, heavy, FANOUT)
    _feeding(g, normal, FANOUT * 2)
    rows = rank(g, "a", W, options=RankOptions(fruit_row=False))
    assert _symbols(rows)[0] == "W1"
    assert rows[0]["band_name"] == GATE


def test_two_gate_cards_come_first_ordered_by_weight_between_themselves() -> None:
    """A gate sibling with weight goes first of the two, and both precede a heavy velocity card."""
    g = Graph()
    _card(g, "W1", tag=GATE)
    sibling = _card(g, "W2", tag=GATE)
    heavy = _card(g, "W3", tag="velocity")
    _feeding(g, sibling, 2)
    _feeding(g, heavy, FANOUT)
    rows = rank(g, "a", W, options=RankOptions(fruit_row=False))
    assert _symbols(rows) == ["W2", "W1", "W3"]


def test_a_gate_card_heads_the_round_file() -> None:
    """Through round_document(): the gate card is the round's first line whatever others weigh."""
    g = Graph()
    _card(g, "W1", tag=GATE)
    heavy = _card(g, "W2", tag="velocity")
    other = _card(g, "W3")
    _feeding(g, heavy, FANOUT)
    _feeding(g, other, FANOUT * 2)
    rows = rank(g, "a", W)
    dicts = [
        {"symbol": r["symbol"], "salience": r["salience"], "title": r.get("title", "")}
        for r in rows
    ]
    text = round_document(
        {"a": cast("list[dict[str, object]]", dicts)}, NO_LANDINGS, "S"
    )
    first = next(line for line in text.splitlines() if '"symbol"' in line)
    assert '"W1"' in first


def test_the_repo_tier_stays_ahead_of_the_gate_in_the_fleet_pool() -> None:
    """In the fleet pool a lower-tier repo's gate card ranks behind a higher-tier repo's card."""
    g = Graph()
    _card(g, "W1", tag=GATE, repo="gabion")
    _card(g, "W2", repo="mtools")
    cites = [r["cite"] for r in rank_fleet(g, W)]
    assert cites == ["mtools:W2", "gabion:W1"]


def test_inside_a_repo_tier_the_fleet_pool_puts_the_gate_card_first() -> None:
    """In the fleet pool a repo's weightless gate card still precedes its heavy velocity card."""
    g = Graph()
    _card(g, "W1", tag=GATE, repo="mtools")
    heavy = _card(g, "W2", tag="velocity", repo="mtools")
    _feeding(g, heavy, FANOUT)
    cites = [r["cite"] for r in rank_fleet(g, W, load_composition())]
    assert cites == ["mtools:W1", "mtools:W2"]


def _plain_rows() -> list[RankRow]:
    # cards outside the gate band, as fresh rows each call (compose writes `key` into them)
    return [
        {"symbol": "W1", "operator": 0, "gate": 0, "band": -1, "weight": 7},
        {"symbol": "W2", "operator": 0, "gate": 0, "band": 0, "weight": 0},
        {"symbol": "W3", "operator": 0, "gate": 0, "band": -3, "weight": 50},
        {"symbol": "W4", "operator": 0, "gate": 0, "band": -3, "weight": 10},
    ]


def test_other_cards_keep_the_order_the_old_composition_gave() -> None:
    """Cards outside the gate band order exactly as under the old [band, weight] tier."""
    new = load_composition()
    old = Composition((("band", "weight"),), new.scalarize)
    assert new.tiers == (("gate",), ("band", "weight"))
    got_new = compose(_plain_rows(), new)
    got_old = compose(_plain_rows(), old)
    assert _symbols(got_new) == _symbols(got_old)


def test_the_tag_value_not_the_band_name_puts_a_card_in_the_band() -> None:
    """With the tag `repairs-the-gate`, only that tag takes the band; the band's name does not."""
    bands = load_bands(CUSTOM)
    got = tagged_band("normal", "x", {"repairs-the-gate"}, tags=bands.tags)
    assert got == (GATE, "touches repairs-the-gate")
    assert tagged_band("normal", "x", {GATE}, tags=bands.tags) == ("normal", "x")
    g = Graph()
    tagged = _card(g, "W1", tag="repairs-the-gate")
    named = _card(g, "W2", tag=GATE)
    assert objectives(g, tagged, W, bands)["gate"] == 1
    assert objectives(g, named, W, bands)["gate"] == 0


def test_a_gate_band_with_another_name_and_place_is_still_a_gate() -> None:
    """The gate objective follows bands.toml's gate list, not a band's name or its place."""
    bands = load_bands(RENAMED)
    g = Graph()
    repair = _card(g, "W1", tag="repairs")
    velocity = _card(g, "W2", tag="velocity")
    plain = _card(g, "W3")
    assert objectives(g, repair, W, bands)["gate"] == 1
    assert objectives(g, repair, W, bands)["band_name"] == "emergency"
    assert objectives(g, velocity, W, bands)["gate"] == 0
    assert objectives(g, plain, W, bands)["gate"] == 0


def test_watching_keeps_the_declared_tags_and_gate() -> None:
    """Naming the behind ratchets does not drop the tag table or the gate."""
    bands = load_bands()
    watched = bands.watching(frozenset({"file:x"}))
    assert watched.tags == bands.tags
    assert watched.gate == bands.gate
    assert watched.behind == frozenset({"file:x"})


def test_tags_are_taken_in_the_declared_band_order() -> None:
    """A card carrying both tags takes the earlier band, in the order the bands declare."""
    bands = load_bands()
    both = {"velocity", GATE}
    assert tagged_band("normal", "x", both, tags=bands.tags)[0] == GATE
    reversed_tags = tuple(reversed(bands.tags))
    assert tagged_band("normal", "x", both, tags=reversed_tags)[0] == "velocity"


def test_the_loader_orders_tags_by_band_not_by_the_table() -> None:
    """A [tag] table written velocity first still loads gate-repair first, as order declares."""
    bands = load_bands(VELOCITY_FIRST)
    assert [band for band, _ in bands.tags] == [GATE, "velocity"]
    both = {"velocity", "repairs-the-gate"}
    assert tagged_band("normal", "x", both, tags=bands.tags)[0] == GATE


def test_a_tag_or_gate_naming_a_band_outside_order_is_refused() -> None:
    """The file refuses a [tag] key or a gate entry that is not a listed band."""
    with pytest.raises(ValueError, match="not in order"):
        load_bands(BASE + '[tag]\ngate-repair = "x"\n')
    with pytest.raises(ValueError, match="not in order"):
        load_bands(BASE + 'gate = ["gate-repair"]\n')


def test_without_a_tag_table_only_the_velocity_tag_counts() -> None:
    """A bands file with no [tag] table keeps the old behaviour: the velocity tag only."""
    bands = load_bands(BASE)
    assert bands.tags == ()
    assert bands.gate == ()
    assert tagged_band("normal", "x", {"velocity"}, tags=bands.tags)[0] == "velocity"
    assert tagged_band("normal", "x", {GATE}, tags=bands.tags) == ("normal", "x")
