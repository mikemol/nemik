# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W850 (W547): the letter a finished card owes the repo on the other end of one edge.

workrows.edges_of lists the cross-repo edges of a done or dropped card and delivery.py says which
of them already had their letter. This words the letter for one edge and names its file. The file
name carries the edge, not only the day, so two edges to one repo are two letters and a letter
for one edge never overwrites another's. Plain strings only, so the Codon census compiles it.
(letters.py is the reader of the inboxes; this is the writer's wording.)
"""

# the same shape as workrows.Edge: (kind, other repo, other symbol)
Edge = tuple[str, str, str]

WORDING = {
    "blocked_on": "is blocked on it: the block can lift",
    "enables": "waits on it as a prerequisite: the wait can lift",
    "caused_by": "was caused by it: its cause is closed, so check whether it still stands",
}


def name(day: str, repo: str, symbol: str, edge: Edge) -> str:
    """Name the letter file for one edge.

    Args:
        day: The date the letter is written, `YYYY-MM-DD`.
        repo: The repo that holds the finished card.
        symbol: The finished card's symbol, `W<n>`.
        edge: (kind, other repo, other symbol).

    Returns:
        `<day>-nemik-edge-<repo>-<symbol>-<kind>-<other symbol>.md`.

    """
    kind, _other, other_symbol = edge
    return f"{day}-nemik-edge-{repo}-{symbol}-{kind}-{other_symbol}.md"


def text(repo: str, symbol: str, edge: Edge, outcome: str, day: str) -> str:
    """Word the letter for one edge.

    The first line is `nemik → <other>: ...`, the header letters.py reads to address a letter.

    Args:
        repo: The repo that holds the finished card.
        symbol: The finished card's symbol.
        edge: (kind, other repo, other symbol).
        outcome: `done` or `dropped`.
        day: The date the letter is written.

    Returns:
        The letter's markdown: what happened to the card, which card here it concerns and why.

    """
    kind, other, other_symbol = edge
    why = WORDING.get(kind, "has an edge to it")
    return (
        f"# nemik → {other}: {repo}:{symbol} is {outcome}\n\n"
        f"On {day} {repo}:{symbol} was {outcome}. {other}:{other_symbol} {why}.\n\n"
        f"The edge is `{kind}`. This letter is sent once for it; nemik keeps a record.\n"
    )
