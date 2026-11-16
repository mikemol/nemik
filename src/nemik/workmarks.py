# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1083: a ready card that leads a landed commit's subject, shown beside its done-when.

A symbol-led commit does not mean the card landed: a card worked in slices leads one commit per
slice (github-8f's sweep: about half are first parts). So nothing here closes or flags a card. It
lines each candidate's newest commit subject up with the card's own statement of what is left
(its next bounded step), so the owner reads the verdict from both and not from the symbol alone.
"""


def head(subject: str) -> str:
    """Name the card a commit subject leads, or "" when it leads none.

    Args:
        subject: A commit subject line, `W<n>: ...` for a card's commit.

    Returns:
        The symbol before the first colon when it reads W<n>; an empty string otherwise.

    """
    symbol = subject.partition(":")[0]
    if symbol.startswith("W") and symbol[1:].isdigit():
        return symbol
    return ""


def leading(subjects: list[str]) -> dict[str, str]:
    """Map each card a commit subject leads to its newest such subject.

    Args:
        subjects: Commit subjects, newest first.

    Returns:
        The newest subject for each symbol that leads one, in the order first met.

    """
    newest: dict[str, str] = {}
    for subject in subjects:
        symbol = head(subject)
        if symbol and symbol not in newest:
            newest[symbol] = subject
    return newest


def pair(ready: dict[str, str], subjects: list[str]) -> list[str]:
    """Line each ready card that leads a commit up with what the card says is left.

    Args:
        ready: The repo's ready cards, symbol to its next bounded step (empty when it states none).
        subjects: The repo's recent commit subjects, newest first.

    Returns:
        One line per candidate, by symbol: the symbol, its newest leading subject, and the card's
        done-when, or a note that the card states none. A card that leads no commit has no line.

    """
    newest = leading(subjects)
    out: list[str] = []
    for symbol in sorted(ready):
        if symbol not in newest:
            continue
        left = ready[symbol].strip() or "(the card states no next step)"
        out.append(f"{symbol}\n  landed: {newest[symbol]}\n  left:   {left}")
    return out
