# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W972: the inbound waits and unclaimed blocks, from plain edges, on a two-repo fleet."""

from pathlib import Path

from queue_cases import make_card, write_queue
from rdflib import RDF, Graph
from rdflib.namespace import PROV

from nemik.adapter import BASE, NEMIK, OSLC_CM
from nemik.cardflags import inbound_rows, unclaimed_blocks
from nemik.rank import ref_of

Plain = dict[str, list[str]]
EXPECTED = [
    ("alpha:W1", "beta", ["beta:W7"]),
    ("alpha:W2", "beta", ["beta:W8"]),
    ("alpha:W3", "beta", ["beta:W7"]),
    ("alpha:W6", "beta", []),
]


def fleet(root: Path) -> Graph:
    """Two repos: alpha waits on beta in four ways, one of which nothing in beta claims.

    W1 is claimed by beta:W7 enabling it, W2 by beta:W8 caused by it, W3 names beta:W7, and W6
    waits on beta with no claim. W4 waits on its own repo's W5, which is no inbound wait.

    Returns:
        The merged graph.

    """
    alpha = [
        make_card("W1", "blocked", ["beta"], []),
        make_card("W2", "blocked", ["beta"], []),
        make_card("W3", "blocked", ["beta:W7"], []),
        make_card("W4", "blocked", ["W5"], []),
        make_card("W5", "ready", [], []),
        make_card("W6", "blocked", ["beta"], []),
    ]
    beta = [
        make_card("W7", "ready", [], ["alpha:W1"]),
        make_card("W8", "ready", [], [], caused_by="alpha:W2"),
    ]
    merged = Graph()
    merged += write_queue(root / "alpha.json", "alpha", alpha)
    merged += write_queue(root / "beta.json", "beta", beta)
    return merged


def plain(g: Graph) -> tuple[Plain, Plain, Plain]:
    """Read the waits, enablers and informed-by cards of a graph as plain strings.

    Returns:
        (waits, enablers, informed), keyed by card reference.

    """
    waits: Plain = {}
    enablers: Plain = {}
    informed: Plain = {}
    for node in g.subjects(OSLC_CM.state, None):
        card = ref_of(node)
        enablers[card] = [ref_of(w) for w in g.subjects(NEMIK.enables, node)]
        informed[card] = [ref_of(w) for w in g.subjects(PROV.wasInformedBy, node)]
        if (node, OSLC_CM.state, NEMIK.Done) in g:
            continue
        targets: list[str] = []
        for target in g.objects(node, NEMIK.waitsFor):
            if (target, RDF.type, NEMIK.Workstream) in g:
                targets.append(str(target).removeprefix(BASE))
            elif (target, RDF.type, OSLC_CM.ChangeRequest) in g:
                targets.append(ref_of(target))
        waits[card] = targets
    return waits, enablers, informed


def test_each_wait_has_the_claims_the_fixture_gives_it(tmp_path: Path) -> None:
    """W1, W2 and W3 are claimed in the three ways, W6 by nothing, and W4's wait is not inbound."""
    rows = inbound_rows(*plain(fleet(tmp_path)))
    assert rows == EXPECTED


def test_the_unclaimed_block_is_the_one_wait_nothing_claims(tmp_path: Path) -> None:
    """Only alpha:W6 waits on beta with no enabling, caused or named card there."""
    rows = inbound_rows(*plain(fleet(tmp_path)))
    assert unclaimed_blocks(rows) == [("alpha:W6", "beta")]


def test_the_rows_are_ordered_by_blocker_then_card() -> None:
    """Two blockers: the order is the blocker's name first, as blocks.inbound sorts."""
    waits = {"a:W1": ["z"], "a:W2": ["b"], "a:W3": ["b"]}
    rows = inbound_rows(waits, {}, {})
    assert [(c, b) for c, b, _ in rows] == [("a:W2", "b"), ("a:W3", "b"), ("a:W1", "z")]
