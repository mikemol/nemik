# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2257: a workstream that is a hub is judged whole, and follows one card's change.

3caa25a let a hub's neighbours into the validated subgraph with only the predicates the Workstream
shapes read (nemik:W2225), and 6b85278 limited that to a hub that IS a workstream. The restriction
for a workstream was pinned on the fixture fleet only, which has no workstream above HUB cards. Here
one has: a workstream with more than HUB ready cards and no working one is reported by
ActiveCardShape, and marking one card working must clear the report in the incremental run exactly
as in a full run, and marking it ready again must bring the report back.
"""

from pathlib import Path

from rdflib import RDF, Graph, Literal, URIRef
from rdflib.namespace import DCTERMS
from rdflib.term import Node

from nemik.adapter import NEMIK, OSLC_CM, queue_graph
from nemik.blocks import annotate
from nemik.check import shapes
from nemik.queuefiles import QUEUE, workstream_files
from nemik.shaclinc import HUB, findings, shacl_results
from nemik.urnbase import BASE

FLEET = Path(__file__).parent / "fixtures" / "fleet"
CARDS = HUB + 5
NO_WORKING = "no working card while items are ready"
KEY = "test-workstream-hub"
Rows = list[tuple[Node, str, str]]  # (focus, severity, message), as findings gives them


def _fleet() -> Graph:
    """Read the fixture fleet into one graph.

    Returns:
        The merged, annotated graph.

    """
    queues = workstream_files(FLEET, QUEUE)
    known = frozenset(r for r, _ in queues)
    g = Graph()
    for repo, path in queues:
        g += queue_graph(repo, path, known)
    annotate(g)
    return g


def _card(ws: URIRef, at: int) -> URIRef:
    """Name the `at`-th card of the workstream under test.

    Returns:
        The card's node.

    """
    return URIRef(f"{ws}/W{9000 + at}")


def _workstream(g: Graph) -> URIRef:
    """Add a workstream of CARDS ready cards, none working.

    Returns:
        The workstream's node.

    """
    ws = URIRef(f"{BASE}zeta")
    g.add((ws, RDF.type, NEMIK.Workstream))
    for at in range(CARDS):
        card = _card(ws, at)
        g.add((card, RDF.type, OSLC_CM.ChangeRequest))
        g.add((card, NEMIK.symbol, Literal(f"W{9000 + at}")))
        g.add((card, DCTERMS.title, Literal(f"card {at}")))
        g.add((card, OSLC_CM.state, NEMIK.Ready))
        g.add((card, NEMIK.workstream, ws))
    return ws


def _set_state(g: Graph, card: URIRef, state: URIRef) -> None:
    """Move one card to `state`."""
    g.remove((card, OSLC_CM.state, None))
    g.add((card, OSLC_CM.state, state))


def _both(g: Graph) -> tuple[Rows, Rows]:
    """Judge the graph incrementally and in full.

    Returns:
        The incremental rows and the full-run rows, sorted by their text.

    """
    sh = shapes()
    inc = sorted(findings(KEY, g, sh), key=str)
    full = sorted(
        ((f, s, m) for f, rows in shacl_results(g, sh).items() for s, m in rows),
        key=str,
    )
    return list(inc), full


def _reported(rows: Rows, ws: URIRef) -> bool:
    """Say whether the workstream is reported as having no working card.

    Returns:
        True when a row for the workstream carries the ActiveCardShape message.

    """
    return any(f == ws and NO_WORKING in m for f, _, m in rows)


def test_a_workstream_hub_follows_one_cards_change_as_a_full_run_does() -> None:
    """Working clears the report, ready brings it back, each equal to a full run."""
    g = _fleet()
    ws = _workstream(g)
    first, _ = _both(g)
    assert _reported(first, ws), "the fixture must start with the report present"
    _set_state(g, _card(ws, 0), NEMIK.Working)
    inc, full = _both(g)
    assert inc == full
    assert not _reported(inc, ws)
    _set_state(g, _card(ws, 0), NEMIK.Ready)
    inc, full = _both(g)
    assert inc == full
    assert _reported(inc, ws)


def test_another_cards_working_mark_still_counts_when_one_card_changes() -> None:
    """The verdict reads cards the change did not touch: card 1 stays working while card 0 toggles.

    A run that walked only the changed card would see one ready card and no working one, and
    report a workstream that a full run does not.
    """
    g = _fleet()
    ws = _workstream(g)
    _set_state(g, _card(ws, 1), NEMIK.Working)
    first, _ = _both(g)
    assert not _reported(first, ws)
    _set_state(g, _card(ws, 0), NEMIK.Blocked)
    inc, full = _both(g)
    assert inc == full
    _set_state(g, _card(ws, 0), NEMIK.Ready)
    inc, full = _both(g)
    assert inc == full
    assert not _reported(inc, ws)
