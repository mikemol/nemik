# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W786: nemik-serve answers /pacing.json with the rows nemik-pacing prints."""

from datetime import UTC, datetime
from pathlib import Path

from nemik.pacing import limits, paces
from nemik.serve import DOC_ROUTES, Model

FLEET = Path(__file__).parent / "fixtures" / "fleet"


def test_the_route_is_listed_and_answers_the_commands_rows() -> None:
    """One implementation: the route's rows are paces() over the same graph and limits."""
    model = Model(FLEET)
    model.refresh()
    assert "/pacing.json" in DOC_ROUTES
    doc = model.doc_for("/pacing.json")
    rate, burst, days = limits()
    want = paces(model.graph, datetime.now(UTC), rate, burst, days)
    assert doc == {
        "rate": rate,
        "burst": burst,
        "days": days,
        "paces": [p._asdict() for p in want],
    }
