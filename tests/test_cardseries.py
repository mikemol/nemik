# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1138: each open card is a series carrying its age, and nothing else about it."""

from nemik.cardseries import card_lines

BORN = "2026-10-26T01:15:35Z"
# 2026-10-26T00:00Z is 1792972800 (298 days after 2026-01-01); then 4535 and 39863 seconds
BORN_SECONDS = 1792977335
TOUCHED = "2026-10-26T11:04:23Z"
TOUCHED_SECONDS = 1793012663


def _node(
    repo: str, symbol: str, state: str, issued: str, worked: str
) -> dict[str, str]:
    """Build one graph node as the server's document holds it.

    Returns:
        The node, with a title that must never reach a label.

    """
    return {
        "repo": repo,
        "symbol": symbol,
        "state": state,
        "issued": issued,
        "last_worked": worked,
        "title": "free text, never a label",
    }


def test_an_open_card_is_a_series_with_its_issue_time() -> None:
    """Ready, working and blocked cards each get an issued sample labelled repo, card, status."""
    got = card_lines(
        [
            _node("b", "W2", "blocked", BORN, ""),
            _node("a", "W1", "ready", BORN, TOUCHED),
            _node("a", "W3", "working", BORN, ""),
        ]
    )
    assert got == [
        "# TYPE nemik_card_issued_seconds gauge",
        f'nemik_card_issued_seconds{{repo="a",card="W1",status="ready"}} {BORN_SECONDS}',
        f'nemik_card_issued_seconds{{repo="a",card="W3",status="working"}} {BORN_SECONDS}',
        f'nemik_card_issued_seconds{{repo="b",card="W2",status="blocked"}} {BORN_SECONDS}',
        "# TYPE nemik_card_last_worked_seconds gauge",
        f'nemik_card_last_worked_seconds{{repo="a",card="W1"}} {TOUCHED_SECONDS}',
    ]


def test_closed_withheld_and_unreadable_cards_publish_no_series() -> None:
    """Done, dropped and withheld nodes, a node with no stamp and one with no repo are left out."""
    got = card_lines(
        [
            _node("a", "W1", "done", BORN, TOUCHED),
            _node("a", "W2", "dropped", BORN, ""),
            _node("a", "W3", "withheld", BORN, ""),
            _node("a", "W4", "ready", "", ""),
            _node("", "W5", "ready", BORN, ""),
        ]
    )
    assert got == [
        "# TYPE nemik_card_issued_seconds gauge",
        "# TYPE nemik_card_last_worked_seconds gauge",
    ]
    assert "free text" not in "".join(got)
