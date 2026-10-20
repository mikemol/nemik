# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W746: the climate, what a region (a repo) does over a window, counted out of its events.

The weather (nemik:W745) is where each card stands; the climate is how a repo behaves: how many
cards it mints and closes a day, how many it reopens, and how long a card takes from its first
appearance to done, as a median and a ninetieth percentile. Counted from the events of
nemik:W744, so it inherits their sampling: events backfilled from git are commit-grain, which
makes a lead time up to one commit gap long or short at each end and a reopen count a lower
bound (docs/weather-questions.md). No import beyond datetime, no future import: it compiles
under Codon as written.
"""

from datetime import datetime, timedelta

# station, time, field, from, to, commit: nemik.cardevents.Event
Event = tuple[str, str, str, str, str, str]

QUANTILE_90 = 0.9
CLOSED = {"done", "dropped", "removed"}
STAMP_BODY = 19  # len("2026-10-01T00:00:00")
OFFSET_LEN = 6  # len("+00:00")


def _instant(stamp: str) -> datetime:
    """Read an ISO stamp as a moment in UTC, with no zone attached.

    Codon's datetime.fromisoformat accepts only a stamp with no offset, so the offset is applied
    here: the date and time part is parsed, then the +hh:mm or -hh:mm at its end is taken off,
    and fractional seconds are dropped. A stamp with no offset is already UTC.

    Returns:
        The moment as a naive datetime in UTC.

    """
    moment = datetime.fromisoformat(stamp[:STAMP_BODY])
    tail = stamp[-OFFSET_LEN:]
    if len(stamp) > STAMP_BODY and tail[0] in "+-" and tail[3] == ":":
        shift = timedelta(hours=int(tail[1:3]), minutes=int(tail[4:6]))
        return moment - shift if tail[0] == "+" else moment + shift
    return moment


def levels_at(events: list[Event], moment: str) -> dict[str, dict[str, float]]:
    """Count each repo's cards by state at one moment, from the events up to it.

    Each card's status as of `moment` (the fold of nemik:W745, repeated here because a Codon module
    cannot import a sibling), counted per repo: the open cards, how many are ready (the frontier),
    working (work in progress) and blocked, and the blocked share of the open cards. A card minted
    but not yet given a status counts as open and none of the three.

    Returns:
        {repo: {open, ready, working, blocked, blocked_share}}.

    """
    until = _instant(moment)
    standing: dict[str, str] = {}
    for station, stamp, field, _, now, _ in events:
        if _instant(stamp) > until:
            continue
        if field == "card":
            standing[station] = "" if now == "minted" else now
        elif field == "status":
            standing[station] = now
    out: dict[str, dict[str, float]] = {}
    for station, status in standing.items():
        repo = station.partition(":")[0]
        row = out.setdefault(
            repo, dict.fromkeys(("open", "ready", "working", "blocked"), 0.0)
        )
        if status in CLOSED:
            continue
        row["open"] += 1
        if status in {"ready", "working", "blocked"}:
            row[status] += 1
    for row in out.values():
        row["blocked_share"] = row["blocked"] / row["open"] if row["open"] else 0.0
    return out


def _chain(
    card: str, waits: dict[str, list[str]], memo: dict[str, int], trail: set[str]
) -> int:
    """Measure the longest run of open local blockers under one card.

    Returns:
        0 for a card that waits on no open local card, else 1 more than its deepest blocker;
        a blocker already on the trail (a cycle) counts 0.

    """
    if card in memo:
        return memo[card]
    trail.add(card)
    depth = 0
    for blocker in waits.get(card, []):
        if blocker not in trail:
            depth = max(depth, 1 + _chain(blocker, waits, memo, trail))
    trail.discard(card)
    memo[card] = depth
    return depth


def depth_at(events: list[Event], moment: str) -> dict[str, float]:
    """Give each repo's deepest chain of open cards waiting on open cards, at one moment.

    The blockers are the repo's own cards named in `blocked_on` (a bare W<n> or repo:W<n> of the
    same repo), read from the events at or before `moment`; a card closed by then no longer
    blocks. A repo whose open cards wait on nothing local has depth 0.

    Returns:
        {repo: the longest chain, in cards beyond the first}.

    """
    until = _instant(moment)
    standing: dict[str, str] = {}
    named: dict[str, list[str]] = {}
    for station, stamp, field, _, now, _ in events:
        if _instant(stamp) > until:
            continue
        if field == "card":
            standing[station] = "" if now == "minted" else now
        elif field == "status":
            standing[station] = now
        elif field == "blocked_on":
            named[station] = [part for part in now.split(",") if part]
    opened = {s for s, status in standing.items() if status not in CLOSED}
    waits: dict[str, list[str]] = {}
    for station in opened:
        repo = station.partition(":")[0]
        resolved = [b if ":" in b else f"{repo}:{b}" for b in named.get(station, [])]
        waits[station] = [
            b for b in resolved if b in opened and b.partition(":")[0] == repo
        ]
    memo: dict[str, int] = {}
    out: dict[str, float] = {}
    for station in sorted(opened):
        repo = station.partition(":")[0]
        deepest = _chain(station, waits, memo, set())
        out[repo] = max(out.get(repo, 0.0), float(deepest))
    return out


def levels_series(
    events: list[Event], start: str, end: str, step_days: float
) -> list[tuple[str, dict[str, dict[str, float]]]]:
    """Take the levels at evenly spaced moments from start to end, both included.

    Returns:
        [(moment, levels_at(events, moment))], oldest first; just the start when the step is
        not positive.

    """
    low = _instant(start)
    span = (_instant(end) - low).total_seconds()
    step = step_days * 86400
    count = int(span // step) if step > 0 else 0
    moments = [
        (low + timedelta(seconds=i * step)).isoformat() + "+00:00"
        for i in range(count + 1)
    ]
    return [(moment, levels_at(events, moment)) for moment in moments]


def waits_of(events: list[Event]) -> dict[str, list[float]]:
    """Collect how long each finished stint in a status lasted, in days, by status.

    A stint runs from a card's status event to its next status event (or to the card's dropping or
    removal); a stint still running has no length yet and is left out. `ready` and `blocked`
    stints are the waits a rank's wait weight prices.

    Returns:
        {status: [days, ...]}, each list sorted ascending.

    """
    since: dict[str, tuple[str, datetime]] = {}
    out: dict[str, list[float]] = {}
    for station, stamp, field, _, now, _ in events:
        if field not in {"status", "card"}:
            continue
        at = _instant(stamp)
        if station in since:
            status, began = since.pop(station)
            if status:
                out.setdefault(status, []).append(_days(began, at))
        if field == "status" or now == "minted":
            since[station] = (now if field == "status" else "", at)
    return {status: sorted(days) for status, days in out.items()}


def _days(start: datetime, end: datetime) -> float:
    """Measure the days from one instant to another.

    Returns:
        The difference in days.

    """
    return (end - start).total_seconds() / 86400


def _quantile(sorted_values: list[float], share: float) -> float:
    """Pick a quantile of a sorted list by position.

    Returns:
        The value at share of the way along the list, 0.0 for an empty list.

    """
    if not sorted_values:
        return 0.0
    return sorted_values[int(share * (len(sorted_values) - 1))]


def leads_by_repo(events: list[Event], moment: str) -> dict[str, list[float]]:
    """List, per repo, the days each card took from mint to its first done, by one moment.

    Only cards whose minting was seen and that were done at or before `moment` count; the lists
    are sorted ascending, the lead times a forecast (nemik:W747) is made from.

    Returns:
        {repo: [days, ...]}.

    """
    until = _instant(moment)
    born: dict[str, datetime] = {}
    closed: set[str] = set()
    out: dict[str, list[float]] = {}
    for station, stamp, field, _, now, _ in events:
        at = _instant(stamp)
        if at > until:
            continue
        if field == "card" and now == "minted":
            born[station] = at
        elif field == "status" and now == "done" and station not in closed:
            closed.add(station)
            if station in born:
                repo = station.partition(":")[0]
                out.setdefault(repo, []).append(_days(born[station], at))
    return {repo: sorted(days) for repo, days in out.items()}


def open_ages(events: list[Event], moment: str) -> dict[str, float]:
    """Give the age in days, at one moment, of every card that was minted and still open.

    A card's age runs from its minting; a card whose status is done, dropped or removed at
    `moment` is left out, as is one whose minting was not seen.

    Returns:
        {station: days}.

    """
    until = _instant(moment)
    born: dict[str, datetime] = {}
    standing: dict[str, str] = {}
    for station, stamp, field, _, now, _ in events:
        at = _instant(stamp)
        if at > until:
            continue
        if field == "card":
            standing[station] = "" if now == "minted" else now
            if now == "minted":
                born[station] = at
        elif field == "status":
            standing[station] = now
    return {
        station: _days(born[station], until)
        for station, status in standing.items()
        if station in born and status not in CLOSED
    }


def climate_of(
    events: list[Event], start: str, end: str
) -> dict[str, dict[str, float]]:
    """Count each repo's activity over the window [start, end) from its events.

    `events` are oldest first; a card's minting may precede the window, which is how a lead time
    is known for a card closed inside it. Counted: cards minted, closed (a status to done),
    dropped, and reopened (a status from done to anything else); per day over the window; the
    median and ninetieth percentile of the days from mint to the first done, over the cards
    closed in the window whose mint was seen.

    Returns:
        {repo: {minted, done, dropped, reopened, minted_per_day, done_per_day, lead_median_days,
        lead_p90_days, leads}}.

    """
    low, high = _instant(start), _instant(end)
    span = max(_days(low, high), 1e-9)
    born: dict[str, datetime] = {}
    closed: set[str] = set()
    counts: dict[str, dict[str, float]] = {}
    leads: dict[str, list[float]] = {}
    for station, stamp, field, was, now, _ in events:
        at = _instant(stamp)
        repo = station.partition(":")[0]
        row = counts.setdefault(
            repo, dict.fromkeys(("minted", "done", "dropped", "reopened"), 0.0)
        )
        inside = low <= at < high
        if field == "card" and now == "minted":
            born[station] = at
            if inside:
                row["minted"] += 1
        elif field == "card" and now == "dropped" and inside:
            row["dropped"] += 1
        elif field == "status" and now == "done" and station not in closed:
            closed.add(station)
            if inside:
                row["done"] += 1
                if station in born:
                    leads.setdefault(repo, []).append(_days(born[station], at))
        elif field == "status" and was == "done" and inside:
            row["reopened"] += 1
    out: dict[str, dict[str, float]] = {}
    for repo, row in counts.items():
        ordered = sorted(leads.get(repo, []))
        entry = dict(row)
        entry["minted_per_day"] = row["minted"] / span
        entry["done_per_day"] = row["done"] / span
        entry["lead_median_days"] = _quantile(ordered, 0.5)
        entry["lead_p90_days"] = _quantile(ordered, QUANTILE_90)
        entry["leads"] = float(len(ordered))
        out[repo] = entry
    return out
