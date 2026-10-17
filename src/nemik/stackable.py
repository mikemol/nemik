# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W613: which ready cards can be committed together as one stack.

A stack is several commits gated once, so its entries must not share a file. Each ready card
declares a manifest of exact repo-relative files it will create or edit (nemik:W612; never a
directory or a glob). Two cards overlap when their manifests share a file. The pick is greedy in
rank order: a card joins when it overlaps neither a card already picked nor a file in flight.
Greedy is not the maximum set of disjoint cards (a maximum independent set, NP-hard), but it is
how a stack is built by hand, it keeps the highest-ranked cards, and it is linear in the manifests.
"""


def pick(
    cards: list[str], manifests: list[list[str]], in_flight: list[str]
) -> list[str]:
    """Pick the cards that can stack, most urgent first.

    Args:
        cards: The ready cards' citations, in rank order.
        manifests: Each card's planned files, parallel to `cards`; an empty manifest is a card that
            is not planned, which never stacks.
        in_flight: Files already staged or in a gate.

    Returns:
        The citations that are pairwise disjoint and disjoint from `in_flight`, in rank order.

    """
    taken = set(in_flight)
    chosen: list[str] = []
    for cite, files in zip(cards, manifests, strict=True):
        if not files or taken.intersection(files):
            continue
        chosen.append(cite)
        taken.update(files)
    return chosen
