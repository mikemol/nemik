# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1100: metrics' tick pairs and ledger-line counts, from the rows and from the triples.

`metrics.ticks` and `metrics.ledger_rows` read the ledger's plain rows through the summary. Each is
compared with the same value computed from the ledger's Activity triples, the way they were read
before, on a ledger that has a foreign card, a line naming no card and a line that does not parse.
"""

from collections import Counter
from typing import TYPE_CHECKING

from rdflib import RDF
from rdflib.namespace import PROV

from nemik.adapter import NEMIK, ledger_graph
from nemik.metrics import label, ledger_rows, ticks

if TYPE_CHECKING:
    from pathlib import Path

LEDGER = (
    '2026-10-05T10:00:00Z  tick  W1  advanced  unblock  "one"\n'
    '2026-10-06T10:00:00Z  tick  W1  advanced  unblock  "two"\n'
    '2026-10-06T11:00:00Z  tick  mtools:W9  blocked   sweep    "foreign"\n'
    '2026-10-12T09:00:00Z  tick  -   advanced  sweep    "names no card"\n'
    '2026-10-13T09:00:00Z  peer  W1  advanced  msg      "a peer asked"\n'
    "not a ledger line\n"
)


def _root(tmp_path: Path) -> Path:
    """Write one repo's ledger under a root, with its queue marker.

    Returns:
        The ledger file.

    """
    claude = tmp_path / "a" / ".claude"
    claude.mkdir(parents=True)
    (claude / "paths-forward.json").write_text("{}", encoding="utf-8")
    ledger = claude / "paths-forward.ledger"
    ledger.write_text(LEDGER, encoding="utf-8")
    return ledger


def test_the_tick_pairs_equal_the_ones_the_triples_give(tmp_path: Path) -> None:
    """A tick line that names a card is (stamp, symbol), a foreign card by its own symbol."""
    ledger = _root(tmp_path)
    g, _ = ledger_graph("a", ledger)
    expected = sorted(
        (str(g.value(act, PROV.startedAtTime)), str(used).rpartition("/")[2])
        for act in g.subjects(RDF.type, PROV.Activity)
        for used in g.objects(act, PROV.used)
        if str(g.value(act, NEMIK.kind)) == "tick"
    )
    assert sorted(ticks("a", ledger)) == expected
    named = [ln for ln in LEDGER.splitlines() if "  tick  " in ln and "  -   " not in ln]
    assert len(expected) == len(named)


def test_the_ledger_line_counts_equal_the_ones_the_triples_give(tmp_path: Path) -> None:
    """Counts by (class, kind) and the unparsed count are the same on both routes."""
    ledger = _root(tmp_path)
    g, unparsed = ledger_graph("a", ledger)
    counted = Counter(
        (str(c), str(k))
        for a in g.subjects(RDF.type, PROV.Activity)
        for c in g.objects(a, NEMIK.effortClass)
        for k in g.objects(a, NEMIK.kind)
    )
    expected = [
        f"nemik_ledger_lines{label(repo='a', kind=kind, **{'class': cls})} {n}"
        for (cls, kind), n in sorted(counted.items())
    ]
    expected.append(f"nemik_ledger_unparsed{label(repo='a')} {unparsed}")
    got = [ln for ln in ledger_rows(tmp_path) if not ln.startswith("#")]
    assert got == expected
    assert unparsed > 0
