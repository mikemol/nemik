# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W714: flags blocks.annotate derives, as functions of plain card edges.

blocks.annotate writes derived triples into an rdflib graph. Each flag here is the same derivation
over `repo:W<n>` strings, so it can run where rdflib cannot (the browser port, nemik:W508). The
graph version stays the reference; tests/test_cardflags.py checks the two agree on a fixture queue.
The module imports only `re`, so the Codon census compiles it. Flags so far: allBlockersLanded,
readyBehindOpen, unresolvedBlocker.
"""

import re

CAL_BLOCK = re.compile(r"cal:[a-z][a-z0-9-]{0,31}/\S+")
HOST_BLOCK = re.compile(r"host:[A-Za-z0-9][A-Za-z0-9._@-]*")
WITNESSES = "nemik-witnesses"


def unresolved_blockers(
    cited: dict[str, list[str]],
    resolved: set[str],
    human: set[str],
    witnessed: set[str],
) -> dict[str, list[str]]:
    """Find the blocked_on entries nemik can resolve to no party (the operator's 2026-09-26 defect).

    A blocked card whose blocked_on names nothing nemik can resolve (no workstream, waypoint or
    operator) draws no edge at all. A condition is resolved by its form (cal:<label>/<uid>,
    host:<id>), and `nemik-witnesses` is a party only for a card that has a witness (nemik:W520).

    Args:
        cited: blocked card -> its blocked_on entries, as written.
        resolved: The blocked cards that wait for at least one resolvable card.
        human: The blocked cards whose blocked_kind is human (drawn to an operator lane).
        witnessed: The cards that declare a witness.

    Returns:
        card -> the entries that resolve to no party, for each card that has any.

    """
    out: dict[str, list[str]] = {}
    for card, texts in cited.items():
        if card in resolved or card in human:
            continue
        bad = [
            t
            for t in (x.strip() for x in texts)
            if not (
                CAL_BLOCK.fullmatch(t)
                or HOST_BLOCK.fullmatch(t)
                or (t == WITNESSES and card in witnessed)
            )
        ]
        if bad:
            out[card] = bad
    return out


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


UMBRELLA = 2  # open enablers of its own repo that make a ready card an umbrella


def ready_behind_open(
    enablers: dict[str, list[str]], ready: set[str], open_cards: set[str]
) -> dict[str, list[str]]:
    """Find the ready cards an open card enables, with those enablers (nemik:W465).

    The flow model already treats such a card as waiting while its fill says ready. Umbrellas (two
    or more open enablers of the card's own repo) are left out: ReadyUmbrellaShape reports them.

    Args:
        enablers: card -> the cards that enable it, as `repo:W<n>` references.
        ready: The cards whose state is ready.
        open_cards: The cards that exist and are not done.

    Returns:
        card -> its open enablers, sorted, for each ready card that has any and is no umbrella.

    """
    out: dict[str, list[str]] = {}
    for card in sorted(ready):
        held = [c for c in enablers.get(card, []) if c in open_cards]
        own = [c for c in held if c.partition(":")[0] == card.partition(":")[0]]
        if held and len(own) < UMBRELLA:
            out[card] = sorted(held)
    return out
