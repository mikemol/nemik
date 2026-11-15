# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1101: history's weekly toil roll-up, from the ledger rows and from the triples.

`history.toil` sums the ledger's plain rows per ISO week through the summary's per-day counts. It is
compared with the roll-up computed from the Activity triples the way it was before, on a ledger that
spans a week boundary and a year boundary and has a line naming no card and a line that does not
parse.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from rdflib import RDF
from rdflib.namespace import PROV

from nemik.adapter import NEMIK, ledger_graph
from nemik.history import toil

if TYPE_CHECKING:
    from pathlib import Path

LEDGER = (
    '2026-10-05T10:00:00Z  tick  W1  advanced  unblock  "monday of week 41"\n'
    '2026-10-11T23:30:00Z  tick  W1  advanced  unblock  "sunday of week 41"\n'
    '2026-10-12T00:30:00Z  peer  W2  advanced  msg      "monday of week 42"\n'
    '2026-10-13T09:00:00Z  tick  -   advanced  sweep    "names no card"\n'
    '2025-12-31T09:00:00Z  tick  W3  advanced  sweep    "an ISO week of the next year"\n'
    "not a ledger line\n"
)


def _from_triples(ledger: Path) -> dict[str, dict[str, int]]:
    """Roll the ledger up per ISO week from its Activity triples, as `toil` once did.

    Returns:
        {week label: {effort class: count}}.

    """
    g, _ = ledger_graph("a", ledger)
    weeks: dict[str, dict[str, int]] = {}
    for act in g.subjects(RDF.type, PROV.Activity):
        stamp = str(g.value(act, PROV.startedAtTime) or "")
        if not stamp:
            continue
        iso = datetime.fromisoformat(stamp).isocalendar()
        cls = str(g.value(act, NEMIK.effortClass) or "unclassified")
        week = weeks.setdefault(f"{iso.year}-W{iso.week:02d}", {})
        week[cls] = week.get(cls, 0) + 1
    return weeks


def test_the_weekly_counts_equal_the_ones_the_triples_give(tmp_path: Path) -> None:
    """Per week and class, the rows' counts are the triples' counts."""
    ledger = tmp_path / "ledger"
    ledger.write_text(LEDGER, encoding="utf-8")
    expected = _from_triples(ledger)
    got = {
        str(row["week"]): {k: v for k, v in row.items() if isinstance(v, int) and k != "week"}
        for row in toil(ledger)
    }
    assert got == expected
    assert "2026-W41" in got
    assert "2026-W42" in got


def test_a_week_is_not_split_across_its_days(tmp_path: Path) -> None:
    """MUTANT: reading each day as its own week would make two rows for the one week 41."""
    ledger = tmp_path / "ledger"
    ledger.write_text(LEDGER, encoding="utf-8")
    weeks = [str(row["week"]) for row in toil(ledger)]
    assert weeks.count("2026-W41") == 1
    assert len(weeks) == len(set(weeks))
