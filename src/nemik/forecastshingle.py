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


def expected_done(leads: list[float], ages: list[float], horizon: float) -> float:
    """Give how many of a repo's open cards are expected done within the horizon.

    The sum of each open card's `done_by` chance, by its age; chances add as expectations do,
    whether or not the cards finish independently.

    Returns:
        The expected count, 0.0 for no open cards.

    """
    return sum(done_by(leads, age, horizon) for age in ages)


def shingle_rows(
    issued: str, station: str, age: float, chances: dict[str, float]
) -> list[list[str]]:
    """Lay one card's issue out as shingle rows, one per lead, ready to append.

    A shingle keeps every issue with its lead, so a later issue never overwrites an earlier one and
    nemik:W748 can score each lead on its own. A row is: the issue time, the station, the lead
    label, the card's age at issue in days, and the chance, as text.

    Returns:
        [[issued, station, lead, age, chance], ...] in the order of `chances`.

    """
    return [
        [issued, station, lead, f"{age:g}", f"{chance:g}"]
        for lead, chance in chances.items()
    ]


def issue(leads: list[float], age: float, horizons: list[float]) -> dict[str, float]:
    """Issue one card's forecast at every horizon (HORIZONS is the usual set).

    Returns:
        {"+<h>d": chance} for each horizon h, in the order given.

    """
    return {f"+{h:g}d": done_by(leads, age, h) for h in horizons}


def in_line(chance: float, rate: float, ahead: int, horizon: float) -> float:
    """Cap a card's chance by its place in its repo's line (nemik:W831).

    A repo that finishes `rate` cards a day clears about rate * horizon of them in the horizon,
    oldest first, so a card with `ahead` cards before it is reached with the chance
    min(1, rate * horizon / (ahead + 1)); the lead-time chance is scaled by that. The lead times say
    how long finished cards took, not how far back in the line this one stands: scoring them alone
    gave a chance of 0.99 to 112 old cards of busy repos, one of which finished (nemik:W749).

    Returns:
        The chance times the share of the line the horizon reaches, from 0.0 to `chance`.

    """
    return chance * min(1.0, rate * horizon / (ahead + 1))


def issue_in_line(
    leads: list[float], age: float, horizons: list[float], rate: float, ahead: int
) -> dict[str, float]:
    """Issue one card's forecast at every horizon, each capped by its place in line.

    Returns:
        {"+<h>d": chance} for each horizon h, in the order given.

    """
    return {
        f"+{h:g}d": in_line(done_by(leads, age, h), rate, ahead, h) for h in horizons
    }
