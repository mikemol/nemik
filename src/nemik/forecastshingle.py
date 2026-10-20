# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W747: the forecast shingle, the chance a card is done within a horizon, from lead times.

The climate (nemik:W746) measures how long cards took from mint to done: the lead times. A forecast
for an open card of a given age is the share of the lead times that ended inside the horizon, among
those that had not ended by that age: P(done by age + h | not done by age). Issued at several
horizons (+1 d, +3 d, +7 d) and kept with the lead each was issued at, as NOAA keeps its shingle, so
nemik:W748 can score each against what happened. Pure functions over lists of days; no import, no
future import, so it compiles under Codon as written.
"""

HORIZONS = [1.0, 3.0, 7.0]


def done_by(leads: list[float], age: float, horizon: float) -> float:
    """Give the chance an open card of this age is done within the horizon, from past lead times.

    Among the lead times longer than `age` (the cards that had not finished by then), the share
    that ended within `horizon` days more. With none longer, nothing in the history says the card
    finishes, so the chance is 0.0 (a floor, not a claim).

    Returns:
        A number from 0.0 to 1.0.

    """
    longer = [lead for lead in leads if lead > age]
    if not longer:
        return 0.0
    return len([lead for lead in longer if lead <= age + horizon]) / len(longer)


def issue(leads: list[float], age: float, horizons: list[float]) -> dict[str, float]:
    """Issue one card's forecast at every horizon (HORIZONS is the usual set).

    Returns:
        {"+<h>d": chance} for each horizon h, in the order given.

    """
    return {f"+{h:g}d": done_by(leads, age, h) for h in horizons}
