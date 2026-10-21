# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W786: nemik-serve answers /overlaps.json with what nemik-overlaps finds."""

from pathlib import Path

from nemik.overlaps import overlaps
from nemik.serve import DOC_ROUTES, Model

FLEET = Path(__file__).parent / "fixtures" / "fleet"


def test_the_route_is_listed_and_answers_the_commands_tags() -> None:
    """One implementation: the route's tags are overlaps() over the same graph."""
    model = Model(FLEET)
    model.refresh()
    assert "/overlaps.json" in DOC_ROUTES
    doc = model.doc_for("/overlaps.json")
    assert doc == {
        "overlaps": overlaps(model.graph),
        "cross": overlaps(model.graph, cross=True),
    }


def test_every_listed_route_has_a_builder() -> None:
    """DOC_ROUTES and the table doc_for answers from name the same routes."""
    model = Model(FLEET)
    model.refresh()
    for route in DOC_ROUTES:
        assert isinstance(model.doc_for(route), dict)
