# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W714: flags blocks.annotate derives, as functions of plain card edges.

blocks.annotate writes derived triples into an rdflib graph. Each flag here is the same derivation
over `repo:W<n>` strings, so it can run where rdflib cannot (the browser port, nemik:W508). The
graph version stays the reference; tests/test_cardflags.py checks the two agree on a fixture queue.
The module imports nothing, so the Codon census compiles it. One flag so far: allBlockersLanded.
"""


def all_blockers_landed(
    waits: dict[str, list[str]],
    cited: dict[str, int],
    landed: set[str],
    done: set[str],
) -> set[str]:
    """Find the open cards whose every blocker has already landed (nemik:W110).

    A block on a card that is done, or dropped to residue, is stale: the waiter should have been
    lifted to ready, or its blocked_on trimmed. Only a card that waits on at least one landed card
    and whose blocked_on entries are all of them is flagged.

    Args:
        waits: card -> the cards it waits for, as resolved references.
        cited: card -> how many distinct blocked_on entries it has, resolved or not.
        landed: The cards that are done or dropped.
        done: The cards whose own state is done, which are never flagged.

    Returns:
        The cards that wait on landed cards and on nothing else.

    """
    out: set[str] = set()
    for card, targets in waits.items():
        if card in done:
            continue
        gone = [t for t in targets if t in landed]
        if gone and len(gone) == cited.get(card, 0):
            out.add(card)
    return out
