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


def mae(pairs: list[tuple[float, float]]) -> float:
    """Score count forecasts by the mean absolute error of their expected count.

    Args:
        pairs: Each forecast's expected count and the count that happened.

    Returns:
        The mean absolute error, 0.0 for no forecasts.

    """
    if not pairs:
        return 0.0
    return sum(abs(expected - actual) for expected, actual in pairs) / len(pairs)


def reliability(
    pairs: list[tuple[float, bool]], bins: int
) -> list[tuple[float, float, int]]:
    """Bin forecast chances and give the share that came true in each bin.

    A reliable forecast has, among the cases it said 0.3 for, about three in ten that happened.
    The chances 0.0 to 1.0 are cut into `bins` equal-width bins (1.0 falls in the last); an empty
    bin is left out.

    Args:
        pairs: Each forecast's chance of "done" and whether the card was done.
        bins: How many equal-width bins.

    Returns:
        (mean chance in the bin, share that happened, count) for each non-empty bin, lowest first.

    """
    if bins < 1:
        return []
    chances: dict[int, list[float]] = {}
    happened: dict[int, int] = {}
    for chance, done in pairs:
        slot = min(int(chance * bins), bins - 1)
        chances.setdefault(slot, []).append(chance)
        happened[slot] = happened.get(slot, 0) + (1 if done else 0)
    return [
        (
            sum(chances[s]) / len(chances[s]),
            happened[s] / len(chances[s]),
            len(chances[s]),
        )
        for s in sorted(chances)
    ]


def persistence_brier(outcomes: list[bool]) -> float:
    """Score the forecast that nothing changes: every open card stays open, chance 0.

    Returns:
        The Brier score of chance 0.0 for each outcome.

    """
    return brier([(0.0, done) for done in outcomes])


def climatology_brier(outcomes: list[bool]) -> float:
    """Score the forecast that every card has the base rate of done, whatever its age.

    Returns:
        The Brier score of the share of done outcomes, said for each outcome.

    """
    if not outcomes:
        return 0.0
    rate = len([done for done in outcomes if done]) / len(outcomes)
    return brier([(rate, done) for done in outcomes])


def skill(score: float, reference: float) -> float:
    """Give how much better a score is than a reference forecast's, as a share of it.

    Returns:
        1.0 for a perfect score, 0.0 for no better than the reference, below 0.0 for worse;
        0.0 when the reference is itself perfect.

    """
    if not reference:
        return 0.0
    return 1.0 - score / reference


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

    Returns:
        {lead: Brier score} for each lead with at least one scorable row (see shingle_pairs).

    """
    found = shingle_pairs(rows, done_at, now, grain_days)
    return {lead: brier(pairs) for lead, pairs in found.items()}


def lead_report(pairs: list[tuple[float, bool]], bins: int) -> dict[str, float]:
    """Judge one lead's forecasts against the two references (nemik:W761).

    Args:
        pairs: The lead's (chance, whether done) pairs.
        bins: How many reliability bins to cut the chances into.

    Returns:
        n, brier, persistence, climatology, skill_persistence and skill_climatology (see skill),
        and a reliability row per non-empty bin as `bin<k>_chance`, `bin<k>_share`, `bin<k>_n`.

    """
    outcomes = [done for _, done in pairs]
    score = brier(pairs)
    persist, climate = persistence_brier(outcomes), climatology_brier(outcomes)
    out = {
        "n": float(len(pairs)),
        "brier": score,
        "persistence": persist,
        "climatology": climate,
        "skill_persistence": skill(score, persist),
        "skill_climatology": skill(score, climate),
    }
    for k, (chance, share, count) in enumerate(reliability(pairs, bins)):
        out[f"bin{k}_chance"] = chance
        out[f"bin{k}_share"] = share
        out[f"bin{k}_n"] = float(count)
    return out


def shingle_pairs(
    rows: list[list[str]], done_at: dict[str, str], now: str, grain_days: float
) -> dict[str, list[tuple[float, bool]]]:
    """Pair each scorable shingle row's chance with what happened, per lead (nemik:W747).

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
        {lead: [(chance, done), ...]} for each lead with at least one scorable row.

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
    return pairs
