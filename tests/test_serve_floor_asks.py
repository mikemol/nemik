# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W786: nemik-serve answers /floor-asks.json with what nemik-floor-asks checks."""

from pathlib import Path

from nemik.floorasks import floor_asks, unresolved
from nemik.serve import DOC_ROUTES, Model

FLEET = Path(__file__).parent / "fixtures" / "fleet"


def test_the_route_is_listed_and_answers_the_commands_check() -> None:
    """One implementation: the route's asks and unresolved pointers are the command's."""
    model = Model(FLEET)
    model.refresh()
    assert "/floor-asks.json" in DOC_ROUTES
    floor = FLEET / "summit" / "floor"
    doc = model.doc_for("/floor-asks.json")
    assert doc["asks"] == len(floor_asks(floor))
    assert doc["unresolved"] == [
        {"key": key, "pointer": ptr, "why": why}
        for key, ptr, why in unresolved(FLEET, floor)
    ]


def test_a_root_without_a_floor_has_no_asks(tmp_path: Path) -> None:
    """No summit/floor directory is no asks, not an error."""
    model = Model(tmp_path)
    doc = model.doc_for("/floor-asks.json")
    assert doc == {"asks": 0, "unresolved": []}
