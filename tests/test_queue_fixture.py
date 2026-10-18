# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W690: a small queue and ledger that nemik reads and the SHACL shapes accept.

The fixture covers each field nemik reads (states, enables, blocked_on, caused_by, manifest, size,
witness and its language, residue, a completed stamp) and the ledger's tick and interrupt lines. The
contract stays in OSLC CM, PROV and SHACL (operator, 2026-10-15), so this checks that the adapter
turns the fixture into cards and activities and that shapes.ttl reports no Violation on it.
"""

from pathlib import Path

from nemik.adapter import NEMIK, OSLC_CM, STATE, ledger_graph, queue_graph, waypoint_uri
from nemik.check import survey

HERE = Path(__file__).parent
ROOT = HERE / "fixtures" / "queue"
QUEUE = HERE / "fixtures" / "queue" / "alpha" / "paths-forward.json"
LEDGER = HERE / "fixtures" / "queue" / "alpha" / "paths-forward.ledger"
STATES = {
    "W1": "done",
    "W2": "ready",
    "W3": "blocked",
    "W4": "working",
    "W5": "blocked",
}


def test_the_adapter_reads_each_card_in_its_state() -> None:
    """Five cards, each in the OSLC CM state its status names."""
    g = queue_graph("alpha", QUEUE, frozenset({"alpha"}))
    read = {
        s: (waypoint_uri("alpha", s), OSLC_CM.state, STATE[v]) in g
        for s, v in STATES.items()
    }
    assert read == dict.fromkeys(STATES, True)


def test_the_manifest_size_and_witness_reach_the_graph() -> None:
    """W2's planned files and size, and W5's witness (as its weather id), are read."""
    g = queue_graph("alpha", QUEUE, frozenset({"alpha"}))
    w2 = waypoint_uri("alpha", "W2")
    planned = {str(o) for o in g.objects(w2, NEMIK.plannedPath)}
    assert planned == {"src/alpha/core.py", "tests/test_core.py"}
    assert [str(o) for o in g.objects(w2, NEMIK.sizeClass)] == ["small"]
    assert (waypoint_uri("alpha", "W5"), NEMIK.weather, None) in g


def test_the_ledger_reads_with_nothing_unparsed() -> None:
    """Three lines, none left over."""
    g, unparsed = ledger_graph("alpha", LEDGER)
    assert unparsed == 0
    assert len(g) > 0


def test_the_shapes_report_no_violation() -> None:
    """The survey's SHACL pass over the fixture finds nothing at Violation severity."""
    findings = [f for _, _, fs in survey(ROOT) for f in fs]
    assert [f for f in findings if f[0] == "Violation"] == []
