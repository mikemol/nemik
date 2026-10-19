# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W530: a ledger line's session is a prov:Agent the line's activity is associated with."""

from pathlib import Path

from rdflib import URIRef
from rdflib.namespace import PROV, RDF

from nemik.adapter import ledger_graph

SESSION = "695f3e0a-d36f-4080-9c67-7548978cd99e"
STAMPED = '2026-10-19T10:00:00Z  tick  W7  advanced  unblock  "a note"'


def test_a_line_with_a_session_names_its_agent(tmp_path: Path) -> None:
    """The activity is associated with urn:uuid:<session>, which is typed prov:Agent."""
    path = tmp_path / "paths-forward.ledger"
    path.write_text(f"{STAMPED}  session={SESSION}\n", encoding="utf-8")
    graph, unparsed = ledger_graph("demo", path)
    agent = URIRef(f"urn:uuid:{SESSION}")
    assert not unparsed
    assert (agent, RDF.type, PROV.Agent) in graph
    assert len(list(graph.subject_objects(PROV.wasAssociatedWith))) == 1


def test_a_line_without_a_session_has_no_agent(tmp_path: Path) -> None:
    """No session on the line, nothing to associate."""
    path = tmp_path / "paths-forward.ledger"
    path.write_text(f"{STAMPED}\n", encoding="utf-8")
    graph, _ = ledger_graph("demo", path)
    assert not list(graph.subject_objects(PROV.wasAssociatedWith))
