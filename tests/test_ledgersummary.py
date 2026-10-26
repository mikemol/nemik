# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1097: the ledger summary holds what every consumer of the Activity triples takes.

For one ledger the Activity triples and the summary are both built, and each consumer's value is
computed from the triples the way that consumer computes it (serve and blocks per card, metrics by
class and kind and its tick pairs, history by class per period) and compared. The triples are read
back from their N-Triples text, so the comparison is plain strings.
"""

from collections import Counter
from pathlib import Path

from nemik.adapter import ledger_graph, ledger_rows
from nemik.ledgersummary import Summary, summarize

LEDGER = (
    '2026-10-05T10:00:00Z  tick  W1  advanced  unblock  "one"\n'
    '2026-10-06T10:00:00Z  tick  W1  advanced  unblock  "two"\n'
    '2026-10-06T11:00:00Z  tick  W2  blocked   sweep    "three"\n'
    '2026-10-12T09:00:00Z  tick  -   advanced  sweep    "names no card"\n'
    '2026-10-13T09:00:00Z  peer  W1  advanced  msg      "a peer asked"\n'
)
RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
ACTIVITY = "<http://www.w3.org/ns/prov#Activity>"
USED = "<http://www.w3.org/ns/prov#used>"
STARTED = "<http://www.w3.org/ns/prov#startedAtTime>"
CLASS = "#effortClass>"
KIND = "#kind>"
Rows = dict[str, dict[str, str]]


def _read(tmp_path: Path) -> tuple[Rows, Summary]:
    """Build the ledger's Activity triples and its summary.

    Returns:
        (each activity's predicate to object text, the summary).

    """
    path = tmp_path / "ledger"
    path.write_text(LEDGER, encoding="utf-8")
    graph, _ = ledger_graph("a", path)
    activities: Rows = {}
    for line in graph.serialize(format="nt").splitlines():
        if line.strip():
            subject, predicate, rest = line.split(" ", 2)
            activities.setdefault(subject, {})[predicate] = rest.removesuffix(" .")
    typed = f"<{RDF}type>"
    held = {s: p for s, p in activities.items() if p.get(typed) == ACTIVITY}
    return held, summarize(ledger_rows(path))


def _symbol(used: str) -> str:
    return used.strip("<>").rpartition("/")[2]


def _stamp(row: dict[str, str]) -> str:
    return row[STARTED].split('"')[1]


def _field(row: dict[str, str], tail: str) -> str:
    return next((v.split('"')[1] for k, v in row.items() if k.endswith(tail)), "")


def test_the_effort_and_latest_stamp_per_card_match_the_triples(
    tmp_path: Path,
) -> None:
    """Serve and blocks take, per card, the count by class and the latest stamp."""
    ledger, (per_card, last, _, _, _) = _read(tmp_path)
    effort: dict[str, Counter[str]] = {}
    latest: dict[str, str] = {}
    for row in ledger.values():
        if USED in row:
            symbol = _symbol(row[USED])
            effort.setdefault(symbol, Counter())[_field(row, CLASS)] += 1
            latest[symbol] = max(latest.get(symbol, ""), _stamp(row))
    assert per_card == {symbol: dict(counts) for symbol, counts in effort.items()}
    assert last == latest
    assert set(per_card) == {"W1", "W2"}


def test_the_counts_by_class_and_kind_match_the_triples(tmp_path: Path) -> None:
    """Metrics' nemik_ledger_lines is one count per (effort class, kind)."""
    ledger, (_, _, by_kind, _, _) = _read(tmp_path)
    counted = Counter(
        (_field(row, CLASS), _field(row, KIND)) for row in ledger.values()
    )
    assert by_kind == dict(counted)


def test_the_counts_per_day_match_the_triples(tmp_path: Path) -> None:
    """History.toil sums classes per ISO week, which a day's counts sum to."""
    ledger, (_, _, _, per_day, _) = _read(tmp_path)
    days: dict[str, Counter[str]] = {}
    for row in ledger.values():
        days.setdefault(_stamp(row)[:10], Counter())[_field(row, CLASS)] += 1
    assert per_day == {day: dict(counts) for day, counts in days.items()}


def test_the_tick_lines_that_name_a_card_match_the_triples(tmp_path: Path) -> None:
    """Metrics' ticks are (stamp, symbol) for the tick lines with a card."""
    ledger, (_, _, _, _, ticks) = _read(tmp_path)
    found = sorted(
        (_stamp(row), _symbol(row[USED]))
        for row in ledger.values()
        if _field(row, KIND) == "tick" and USED in row
    )
    assert sorted(ticks) == found
    assert [symbol for _, symbol in ticks] == ["W1", "W1", "W2"]
