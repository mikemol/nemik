# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W748: verification, how far a forecast's chances were from what happened.

A forecast (nemik:W747) says "P(done by +3d) = 0.4"; the truth is whether the card was done. The
Brier score is the mean squared distance between the chances and the outcomes (0 is perfect, 0.25 is
what saying 0.5 every time earns, 1 is certainty wrong every time). A forecast is only scored at a
lead no finer than the grain of the truth it is scored against (operator ruling, record 8f3e501d:
backfilled history is commit-grain, so a lead shorter than the gap between commits would be scored
against noise). Imports only datetime, no future import: compiles under Codon as written.
"""

from datetime import datetime, timedelta

STAMP_BODY = 19  # len("2026-10-01T00:00:00")
OFFSET_LEN = 6  # len("+00:00")


def _instant(stamp: str) -> datetime:
    """Read an ISO stamp as a moment in UTC, with no zone attached.

    Codon's datetime.fromisoformat accepts only a stamp with no offset, so the offset is applied
    here (as in nemik.climate, which a Codon module cannot import): the date and time part is
    parsed, the +hh:mm or -hh:mm at its end is taken off, and fractional seconds are dropped.

    Returns:
        The moment as a naive datetime in UTC.

    """
    moment = datetime.fromisoformat(stamp[:STAMP_BODY])
    tail = stamp[-OFFSET_LEN:]
    if len(stamp) > STAMP_BODY and tail[0] in "+-" and tail[3] == ":":
        shift = timedelta(hours=int(tail[1:3]), minutes=int(tail[4:6]))
        return moment - shift if tail[0] == "+" else moment + shift
    return moment


def brier(pairs: list[tuple[float, bool]]) -> float:
    """Score forecasts by the mean squared error of their chances.

    Args:
        pairs: Each forecast's chance of "done" and whether the card was done.

    Returns:
        The Brier score from 0.0 to 1.0, lower better; 0.0 for no forecasts.

    """
    if not pairs:
        return 0.0
    return sum((chance - (1.0 if done else 0.0)) ** 2 for chance, done in pairs) / len(
        pairs
    )


def scorable(lead_days: float, grain_days: float) -> bool:
    """Say whether a lead is coarse enough to score against truth of this grain.

    A lead shorter than the grain of the observations would be judged against noise: the moment
    a card finished is not known more finely than the gap between the commits that saw it.

    Returns:
        True when the lead is at least the grain.

    """
    return lead_days >= grain_days


def score_shingle(
    rows: list[list[str]], done_at: dict[str, str], now: str, grain_days: float
) -> dict[str, float]:
    """Score shingle rows (nemik:W747) per lead against when each card was done.

    A row is [issued, station, lead, age, chance]. Its outcome is whether the station was done
    at or before issued + lead, known only once that moment has passed (`now`), so a row whose
    horizon is still ahead is left out; so is a row whose lead is finer than the grain. A card
    already done when the row was issued is left out too: it was never forecast.

    Args:
        rows: The shingle rows.
        done_at: {station: ISO time of its first done}; absent for a card not done.
        now: The time the truth is read at.
        grain_days: The grain of the observations, in days.

    Returns:
        {lead: Brier score} for each lead with at least one scorable row.

    """
    present = _instant(now)
    pairs: dict[str, list[tuple[float, bool]]] = {}
    for issued, station, lead, _, chance in rows:
        days = float(lead[1:-1])
        began = _instant(issued)
        due = began + timedelta(days=days)
        finished = done_at.get(station, "")
        if not scorable(days, grain_days) or due > present:
            continue
        if finished and _instant(finished) <= began:
            continue
        outcome = bool(finished) and _instant(finished) <= due
        pairs.setdefault(lead, []).append((float(chance), outcome))
    return {lead: brier(found) for lead, found in pairs.items()}
