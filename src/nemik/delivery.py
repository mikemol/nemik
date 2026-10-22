# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W849 (W547): the delivery record, so one letter goes out per cross-repo edge, once.

When a card is done or dropped, workrows.edges_of lists the cross-repo edges that want a letter.
Naming a letter file by date is not enough to send it once: a rerun on a later day writes a second
letter, and a letter its reader deleted would be sent again. The record is a nemik-owned text file,
one line per delivered edge, `<repo>:<symbol> <kind> <other repo>:<other symbol> <day>`. These
functions read and extend its text and touch no file, so the letter writer (W850) owns where it
lives. Plain strings only, so the Codon census compiles it.
"""

# the same shape as workrows.Edge: (kind, other repo, other symbol)
Edge = tuple[str, str, str]


def key(repo: str, symbol: str, edge: Edge) -> str:
    """Name one delivered edge, without the day.

    Args:
        repo: The repo that holds the finished card.
        symbol: The finished card's symbol, `W<n>`.
        edge: (kind, other repo, other symbol), as workrows.edges_of returns it.

    Returns:
        `<repo>:<symbol> <kind> <other repo>:<other symbol>`.

    """
    kind, other, other_symbol = edge
    return f"{repo}:{symbol} {kind} {other}:{other_symbol}"


def delivered(text: str) -> set[str]:
    """Read the keys of the edges a record says were delivered.

    Args:
        text: The record's text; blank lines and lines with no day are skipped.

    Returns:
        The key of each delivered edge, with its day dropped.

    """
    keys: set[str] = set()
    for line in text.splitlines():
        head, space, _day = line.strip().rpartition(" ")
        if space and head:
            keys.add(head)
    return keys


def owed(text: str, repo: str, symbol: str, edges: list[Edge]) -> list[Edge]:
    """Keep the edges the record does not yet show as delivered.

    Args:
        text: The record's text.
        repo: The repo that holds the finished card.
        symbol: The finished card's symbol.
        edges: Every edge workrows.edges_of found for it.

    Returns:
        The edges still owed a letter, in the order given.

    """
    done = delivered(text)
    return [edge for edge in edges if key(repo, symbol, edge) not in done]


def stamp(repo: str, symbol: str, edge: Edge, day: str) -> str:
    """Write the record line for a delivered edge.

    Args:
        repo: The repo that holds the finished card.
        symbol: The finished card's symbol.
        edge: The edge whose letter went out.
        day: The date it went out, `YYYY-MM-DD`.

    Returns:
        One line ending in a newline, to append to the record.

    """
    return f"{key(repo, symbol, edge)} {day}\n"
