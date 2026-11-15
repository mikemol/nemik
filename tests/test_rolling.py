# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1997: a card waiting on a blocker that keeps landing is a Warning (rolling blocker).

The landings document is read in both layouts the fleet produces: the host's (the stamp, then a row
per line) and luthen's egress rewrite (one line), which read as no rows at all until this card. The
bound is a declared percentile of landings per card, learned from the document.
"""

import json
from typing import TYPE_CHECKING

from nemik.check import survey
from nemik.landings import Landing, document, read_document
from nemik.rolling import bound, counts, message

if TYPE_CHECKING:
    from pathlib import Path

AS_OF = "2026-11-15T10:43:29Z"
NINETY = 90


def _row(repo: str, card: str, n: int) -> Landing:
    return Landing(repo, f"sha{n}", card, 100 + n, f"2026-11-0{1 + n % 9}T00:00:00Z")


def _rows() -> list[Landing]:
    """Give fifty cards that landed once, and one rolling card that landed twelve times.

    Returns:
        The landings, oldest first.

    """
    rows = [_row("b", f"W{n}", n) for n in range(1, 51)]
    rows += [_row("b", "W900", n) for n in range(12)]
    return rows


def _one_line(rows: list[Landing]) -> str:
    """Write the rows as luthen's egress gate does: one document on one line.

    Returns:
        The text, with the stamp first and every row in a single list.

    """
    objects = ", ".join(
        f'{{"card": "{r.card}", "gate_s": "{r.gate_s}", "repo": "{r.repo}", '
        f'"sha": "{r.sha}", "when": "{r.when}"}}'
        for r in rows
    )
    return f'{{"as_of": "{AS_OF}", "rows": [{objects}]}}'


def test_the_one_line_egress_layout_reads_as_its_rows() -> None:
    """MUTANT: the egress rewrite is one line; a reader taking rows after line one sees none."""
    rows = _rows()
    one_line = _one_line(rows)
    assert "\n" not in one_line
    as_of, read = read_document(one_line)
    assert as_of == AS_OF
    assert [(r.repo, r.card, r.sha, r.gate_s) for r in read] == [
        (r.repo, r.card, r.sha, r.gate_s) for r in rows
    ]


def test_the_host_layout_still_reads() -> None:
    """The stamp then a row per line, as document() writes it."""
    rows = _rows()
    assert len(read_document(document(rows, AS_OF))[1]) == len(rows)


def test_the_bound_is_the_declared_percentile_of_landings_per_card() -> None:
    """Fifty cards of one landing and one of twelve: the 90th percentile is one."""
    landed = counts(_pairs(_rows()))
    assert bound(landed, NINETY) == 1
    assert bound(landed, 100) == max(landed.values())
    assert bound({}, NINETY) == 0


def test_a_row_with_no_card_is_not_counted() -> None:
    """A landing naming no card is no card's landing."""
    assert counts([("b", "-"), ("b", "W1")]) == {"b:W1": 1}


def _pairs(rows: list[Landing]) -> list[tuple[str, str]]:
    """Give each landing as the (repo, card) pair rolling counts.

    Returns:
        The pairs, in order.

    """
    return [(r.repo, r.card) for r in rows]


def _card(symbol: str, status: str, blocked_on: list[str]) -> dict[str, object]:
    return {
        "symbol": symbol,
        "title": "t",
        "status": status,
        "blocked_on": blocked_on,
        "blocked_kind": "agent" if blocked_on else None,
        "enables": [],
        "evidence": "",
    }


def _fleet(root: Path, *, landings: bool) -> None:
    """Lay out a: W1 blocked on b:W900 (rolling) and W2 on b:W1 (landed once); b holds both."""
    for name, cards in (
        ("a", [_card("W1", "blocked", ["b:W900"]), _card("W2", "blocked", ["b:W1"])]),
        ("b", [_card("W900", "ready", []), _card("W1", "ready", [])]),
    ):
        claude = root / name / ".claude"
        claude.mkdir(parents=True)
        state = {
            "version": 1,
            "project_root": str(root / name),
            "counter": 900,
            "residue": [],
            "waypoints": cards,
        }
        (claude / "paths-forward.json").write_text(json.dumps(state), encoding="utf-8")
    if landings:
        (root / "landings.json").write_text(document(_rows(), AS_OF), encoding="utf-8")


def _said(root: Path) -> list[str]:
    for name, _graph, found in survey(root, check=True):
        if name == "a":
            return [msg for _sev, _focus, msg in found]
    return []


def test_a_card_waiting_on_a_rolling_blocker_is_told_to_split_it(tmp_path: Path) -> None:
    """a:W1 waits on b:W900 (twelve landings, bound one): a Warning naming the blocker and count."""
    _fleet(tmp_path, landings=True)
    said = [m for m in _said(tmp_path) if "keeps landing" in m]
    assert len(said) == 1
    assert message("b:W900", 12, 1, NINETY) in said


def test_without_a_landings_document_nothing_is_filed(tmp_path: Path) -> None:
    """No document is no answer, not an empty one: no rolling-blocker Warning."""
    _fleet(tmp_path, landings=False)
    assert not any("keeps landing" in m for m in _said(tmp_path))
