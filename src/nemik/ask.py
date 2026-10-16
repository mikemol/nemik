# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W587: filing an ask is mechanical: the filer's waypoint, then the entry that cites it.

summit's floor takes an ask as a BibTeX `@misc` entry in floor/inbox/ whose
`waypoint = {<repo>:W<n>}` field must name a card the FILER minted in its own queue (summit
scripts/place_intake.py refuses a pointer that is malformed, names an unenrolled repo, or names a
symbol absent from that queue). Nothing used to mint the card or write the entry; a filer did both
by hand. This module is the pure part: the words of the card and of the entry. The command
(nemik.ask_cli) runs the writer and writes the file. The design is docs/model.md's "summit asks as
waypoints": each open ask is a waypoint in the asker's queue, blocked on the owner.
"""

SLUG_CHARS = "abcdefghijklmnopqrstuvwxyz0123456789-"
TITLE_WIDTH = 100


def slug_ok(slug: str) -> bool:
    """Say whether a slug is a usable BibTeX key and file name.

    Args:
        slug: The proposed key, for example ask-membudget-hold-records-no-waiter.

    Returns:
        True for lowercase letters, digits and hyphens, not starting with a hyphen.

    """
    return bool(slug) and slug[0] != "-" and all(c in SLUG_CHARS for c in slug)


def braces_balanced(text: str) -> bool:
    """Say whether a text's braces nest, so it can sit inside a BibTeX field.

    Args:
        text: The claim.

    Returns:
        True when every brace closes and none closes first.

    """
    depth = 0
    for char in text:
        depth += (char == "{") - (char == "}")
        if depth < 0:
            return False
    return depth == 0


def title(owner: str, claim: str) -> str:
    """Word the filer's waypoint title.

    Args:
        owner: The repo the ask is addressed to.
        claim: The ask's text.

    Returns:
        The owner and the claim's first line, cut to a title.

    """
    first = claim.strip().splitlines()[0] if claim.strip() else ""
    return f"Ask {owner}: {first[:TITLE_WIDTH]}"


def blocked_on(owner: str, owner_card: str) -> str:
    """Name what the filer's waypoint waits on.

    Args:
        owner: The repo the ask is addressed to.
        owner_card: The owner's card that answers it, as W<n>, or empty when none is known.

    Returns:
        `<owner>:W<n>` when the card is known, else the repo name.

    """
    return f"{owner}:{owner_card}" if owner_card else owner


def entry(slug: str, filer: str, owner: str, claim: str, symbol: str) -> str:
    """Write the floor entry for an ask.

    Args:
        slug: The BibTeX key and file name stem.
        filer: The repo filing the ask.
        owner: The repo the ask is addressed to.
        claim: The ask's text; its braces must balance.
        symbol: The filer's waypoint, W<n>.

    Returns:
        The `@misc` entry in the form summit's place_intake reads.

    """
    return (
        f"@misc{{{slug},\n"
        "  section = {ask},\n"
        f"  note    = {{kind=ask by={filer} to={owner}}},\n"
        f"  claim   = {{{claim.strip()}}},\n"
        f"  waypoint = {{{filer}:{symbol}}}\n"
        "}\n"
    )
