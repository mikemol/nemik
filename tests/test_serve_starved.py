# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W786: nemik-serve answers /starved.json with the rows nemik-starved --json prints."""

from datetime import UTC, datetime
from pathlib import Path

from nemik.serve import DOC_ROUTES, Model
from nemik.starved import days_limit, starved_fleet

FLEET = Path(__file__).parent / "fixtures" / "fleet"


def test_the_route_is_listed_and_answers_the_commands_rows() -> None:
    """One implementation: the route's rows are starved_fleet's over the same graph and age."""
    model = Model(FLEET)
    model.refresh()
    assert "/starved.json" in DOC_ROUTES
    doc = model.doc_for("/starved.json")
    days = days_limit()
    want = starved_fleet(model.graph, [], datetime.now(UTC), days)
    assert doc == {"days": days, "starved": [s._asdict() for s in want]}
