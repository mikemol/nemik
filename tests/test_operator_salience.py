"""nemik:W298: the waiting-on-operator view carries how much demand waits behind each ask."""

from __future__ import annotations

from rdflib import Graph, Literal

from nemik.adapter import NEMIK, OPERATOR, OSLC_CM, STATE, waypoint_uri
from nemik.blocks import operator_asks, with_salience


def _card(g: Graph, repo: str, sym: str, status: str = "blocked"):
    node = waypoint_uri(repo, sym)
    g.add((node, OSLC_CM.state, STATE[status]))
    return node


def _ask(g: Graph, repo: str, sym: str, text: str):
    node = _card(g, repo, sym)
    g.add((node, NEMIK.waitsFor, OPERATOR))
    g.add((node, NEMIK.blockedOn, Literal(f"operator: decide {text}")))
    return node


def test_an_ask_carries_the_demand_of_the_cards_waiting_behind_it() -> None:
    g = Graph()
    heavy = _ask(g, "a", "W1", "the heavy one")
    light = _ask(g, "a", "W2", "the light one")
    for sym in ("W3", "W4", "W5"):
        g.add((_card(g, "a", sym), NEMIK.waitsFor, heavy))
    g.add((_card(g, "a", "W6"), NEMIK.waitsFor, light))
    found = {a["ref"]: a["salience"] for a in with_salience(g, operator_asks(g))}
    assert found == {"a:W1": 3.0, "a:W2": 1.0}


def test_the_metrics_sum_each_repos_asks_and_count_them() -> None:
    # nemik:W300: two asks of repo a hold back 3 and 1; repo b has one with nothing behind it.
    from nemik.metrics import operator_lines

    g = Graph()
    heavy = _ask(g, "a", "W1", "heavy")
    light = _ask(g, "a", "W2", "light")
    _ask(g, "b", "W1", "alone")
    for sym in ("W3", "W4", "W5"):
        g.add((_card(g, "a", sym), NEMIK.waitsFor, heavy))
    g.add((_card(g, "a", "W6"), NEMIK.waitsFor, light))
    lines = operator_lines(g)
    assert 'nemik_operator_salience{repo="a"} 4.00' in lines
    assert 'nemik_operator_asks{repo="a"} 2' in lines
    assert 'nemik_operator_salience{repo="b"} 0.00' in lines


def test_the_heaviest_ask_leads_its_category() -> None:
    g = Graph()
    old = _ask(g, "a", "W1", "old but light")
    g.add((old, NEMIK.ticksBlocked, Literal(50)))
    heavy = _ask(g, "a", "W2", "heavy")
    for sym in ("W3", "W4"):
        g.add((_card(g, "a", sym), NEMIK.waitsFor, heavy))
    first = with_salience(g, operator_asks(g))[0]
    assert first["ref"] == "a:W2"  # more demand behind it beats more ticks blocked
