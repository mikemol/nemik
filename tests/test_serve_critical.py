# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W786: nemik-serve answers /critical.json with what nemik-critical --json prints."""

from pathlib import Path

from nemik.critical import critical, critical_doc
from nemik.serve import DOC_ROUTES, Model

FLEET = Path(__file__).parent / "fixtures" / "fleet"


def test_the_route_is_listed_and_answers_the_commands_document() -> None:
    """One implementation: the route's document is critical_doc over the same graph."""
    model = Model(FLEET)
    model.refresh()
    assert "/critical.json" in DOC_ROUTES
    assert model.doc_for("/critical.json") == critical_doc(model.graph)


def test_the_document_carries_the_length_the_chain_and_the_cycles() -> None:
    """The fields the command's --json prints, with the length the core computes."""
    model = Model(FLEET)
    model.refresh()
    doc = model.critical_json()
    assert doc["length"] == critical(model.graph).length
    assert {"chain", "slack", "rank", "paths", "cycles"} <= set(doc)
