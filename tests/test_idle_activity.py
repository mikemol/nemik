# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1102: the tick outcomes idle reads, from the ledger file and from the Activity triples.

`adapter.tick_outcomes` reads a ledger's tick lines straight from the file. It is compared with the
outcomes computed from the Activity triples the way `idle` once did, on a ledger whose lines are
out of stamp order and tie on a stamp, with a non-tick line and a line that does not parse.
"""

from typing import TYPE_CHECKING

from rdflib.namespace import PROV

from nemik.adapter import NEMIK, ledger_graph, tick_outcomes

if TYPE_CHECKING:
    from pathlib import Path

LEDGER = (
    '2026-10-06T10:00:00Z  tick  W1  advanced  unblock  "later"\n'
    '2026-10-05T10:00:00Z  tick  W1  idle      sweep    "earlier"\n'
    '2026-10-06T10:00:00Z  tick  W2  blocked   sweep    "same stamp as the first"\n'
    '2026-10-07T10:00:00Z  peer  W1  advanced  msg      "not a tick"\n'
    "not a ledger line\n"
)


def test_the_outcomes_equal_the_ones_the_triples_give(tmp_path: Path) -> None:
    """Tick outcomes, oldest first, are the same from the file as from the triples."""
    ledger = tmp_path / "ledger"
    ledger.write_text(LEDGER, encoding="utf-8")
    g, _ = ledger_graph("a", ledger)
    rows = sorted(
        (
            str(g.value(node, PROV.startedAtTime)),
            str(g.value(node, NEMIK.outcome)),
        )
        for node in g.subjects(NEMIK.kind, None)
        if str(g.value(node, NEMIK.kind)) == "tick"
    )
    assert tick_outcomes(ledger) == [outcome for _, outcome in rows]


def test_a_line_that_is_not_a_tick_is_left_out(tmp_path: Path) -> None:
    """MUTANT: reading every line would add the peer line's outcome, `advanced`."""
    ledger = tmp_path / "ledger"
    ledger.write_text(LEDGER, encoding="utf-8")
    outcomes = tick_outcomes(ledger)
    assert outcomes[0] == "idle"
    assert len(outcomes) == len([ln for ln in LEDGER.splitlines() if "  tick  " in ln])
