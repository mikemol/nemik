# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W989: paydown cards rank above feature cards while their repo is behind its ratchets.

A repo is behind a ratchet when ratchetpace (nemik:W987) says so. A paydown card is an open card
whose touches name the ratchet's file, `file:<repo-relative path>` with the write suffix ignored
(nemik:W988; no new tag, the writer refuses a `ratchet:` prefix). While the repo is behind, the
operator's ruling (host 695f3e0a lines 92679, 93549) puts those cards ahead of everything else, so
the ranking lifts them to the front and leaves every other order as it was. Plain strings and
lists only, no import, so the Codon census compiles it and the browser port can run it.
"""


def paydown_cards(touches: dict[str, list[str]], ratchets: list[str]) -> list[str]:
    """Pick the cards that pay down the given ratchets.

    Args:
        touches: Each open card's symbol and its touches tags.
        ratchets: The ratchets the repo is behind on, as repo-relative paths.

    Returns:
        The symbols of the cards touching one of those ratchet files, sorted.

    """
    want = {f"file:{ratchet}" for ratchet in ratchets}
    found: set[str] = set()
    for symbol, tags in touches.items():
        for tag in tags:
            if tag.removesuffix("!w") in want:
                found.add(symbol)
    return sorted(found)


def lift_paydown(order: list[str], paydown: list[str]) -> list[str]:
    """Move the paydown cards to the front of a ranking, each group in its own order.

    Args:
        order: The ranked symbols, best first.
        paydown: The symbols that pay down a ratchet the repo is behind on.

    Returns:
        The paydown cards in their ranked order, then every other card in its ranked order.

    """
    lifted = set(paydown)
    return [s for s in order if s in lifted] + [s for s in order if s not in lifted]
