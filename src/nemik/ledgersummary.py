# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1097: what the consumers take from a ledger, summed once, not one graph node per line.

Each ledger line became a prov:Activity with about nine triples (17,811 activities and 163,088
triples, 48 percent of the merged graph and about 196 MiB of the build's memory, W1073). The
consumers reduce them to a few counts: serve and blocks want, per card, the count by effort class
and the latest stamp; metrics wants the count by (class, kind) and the tick lines that name a
card; history wants the count by class per day (its ISO weeks are summed from days). This sums
those in one pass over plain rows (stamp, kind, symbol, effort class), so a consumer can read the
summary and the Activity triples need not be built. Plain strings, integers and dicts, no import,
so the Codon census compiles it.
"""

# per card symbol: effort count by class
PerCard = dict[str, dict[str, int]]
# per card symbol: the latest stamp of a line that used it
Last = dict[str, str]
# (effort class, kind): how many lines
ByKind = dict[tuple[str, str], int]
# day (the stamp's date): effort count by class
PerDay = dict[str, dict[str, int]]
# the tick lines that name a card, as (stamp, symbol) in file order
Ticks = list[tuple[str, str]]
Summary = tuple[PerCard, Last, ByKind, PerDay, Ticks]


def summarize(rows: list[tuple[str, str, str, str]]) -> Summary:
    """Sum a ledger's lines into what its consumers read.

    Args:
        rows: One tuple per parsed line in file order: (stamp, kind, symbol or "" when it names no
            card, effort class).

    Returns:
        (per card count by class, per card latest stamp, count by (class, kind), per day count by
        class, the tick lines that name a card).

    """
    per_card: PerCard = {}
    last: Last = {}
    by_kind: ByKind = {}
    per_day: PerDay = {}
    ticks: Ticks = []
    for stamp, kind, symbol, cls in rows:
        key = (cls, kind)
        by_kind[key] = by_kind.get(key, 0) + 1
        if stamp:
            day = per_day.setdefault(stamp[:10], {})
            day[cls] = day.get(cls, 0) + 1
        if symbol:
            counts = per_card.setdefault(symbol, {})
            counts[cls] = counts.get(cls, 0) + 1
            last[symbol] = max(last.get(symbol, ""), stamp)
            if kind == "tick":
                ticks.append((stamp, symbol))
    return per_card, last, by_kind, per_day, ticks
