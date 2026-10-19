# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W681: where a repo's working time went, one row per tick line that names a card.

W485 asks whether sessions spend their time on leaves, on interior cards that unblock others, or on
directed work. A ledger tick says which card was worked and when (nemik.metrics.ticks reads them);
the queue says what the card is. Three facts per tick:
- weight: how many cards sit downstream of it, following `enables` edges transitively;
- leaf: nothing waits on it (no `enables`, and no card names it in `blocked_on`);
- directed: the card was minted by a peer or the operator, not by another card (its `caused_by` is
  not a waypoint symbol). The ledger holds no record of a directive, so minting is the proxy: a card
  that someone asked for is directed work however it was later ranked.

A row is (stamp, symbol, weight, leaf, directed), a plain tuple so it sorts by time. The module
imports only json, so the Codon census compiles it.
"""

import json

WorkRow = tuple[str, str, int, bool, bool]
Cards = dict[str, dict[str, list[str]]]


def cards_of(queue_text: str) -> Cards:
    """Read a queue file's cards by symbol, keeping the lists that make the edges.

    Args:
        queue_text: The text of a paths-forward.json.

    Returns:
        For each waypoint its `enables`, `blocked_on` and `caused_by` as lists of text (caused_by
        a list of one or none); empty when the text is not a queue.

    """
    out: Cards = {}
    try:
        doc: object = json.loads(queue_text)
    except ValueError:
        return out
    if not isinstance(doc, dict):
        return out
    items = doc.get("waypoints")
    if not isinstance(items, list):
        return out
    for card in items:
        if isinstance(card, dict):
            cause = card.get("caused_by")
            out[str(card.get("symbol"))] = {
                "enables": _texts(card.get("enables")),
                "blocked_on": _texts(card.get("blocked_on")),
                "caused_by": [cause] if isinstance(cause, str) and cause else [],
            }
    return out


def _texts(value: object) -> list[str]:
    """Read a field that should hold a list of symbols.

    Args:
        value: The field, as json parsed it.

    Returns:
        Its entries as text; empty when it is not a list.

    """
    return [str(entry) for entry in value] if isinstance(value, list) else []


def downstream(cards: Cards, symbol: str) -> int:
    """Count the cards reached from one by `enables` edges, transitively.

    Args:
        cards: The queue's cards by symbol.
        symbol: The card to start from.

    Returns:
        How many distinct cards lie downstream; a cycle is walked once.

    """
    seen: set[str] = set()
    todo = list(cards.get(symbol, {}).get("enables", []))
    while todo:
        nxt = todo.pop()
        if nxt in seen or nxt == symbol:
            continue
        seen.add(nxt)
        todo.extend(cards.get(nxt, {}).get("enables", []))
    return len(seen)


def is_leaf(cards: Cards, symbol: str) -> bool:
    """Say whether nothing waits on a card.

    Args:
        cards: The queue's cards by symbol.
        symbol: The card.

    Returns:
        True when it enables nothing and no card names it in `blocked_on`.

    """
    if cards.get(symbol, {}).get("enables"):
        return False
    return not any(symbol in other.get("blocked_on", []) for other in cards.values())


def is_directed(cards: Cards, symbol: str) -> bool:
    """Say whether a card was asked for by someone rather than found by another card.

    Args:
        cards: The queue's cards by symbol.
        symbol: The card.

    Returns:
        True when its `caused_by` is set and is not a waypoint of this queue.

    """
    causes = cards.get(symbol, {}).get("caused_by", [])
    return len(causes) > 0 and causes[0] not in cards


def working_rows(ticks: list[tuple[str, str]], queue_text: str) -> list[WorkRow]:
    """Describe each tick that worked a card the queue holds.

    Args:
        ticks: (stamp, symbol) for each ledger tick line that names a card.
        queue_text: The text of the repo's paths-forward.json.

    Returns:
        One (stamp, symbol, weight, leaf, directed) row per tick whose card the queue holds,
        oldest first.

    """
    cards = cards_of(queue_text)
    return sorted(
        (
            stamp,
            symbol,
            downstream(cards, symbol),
            is_leaf(cards, symbol),
            is_directed(cards, symbol),
        )
        for stamp, symbol in ticks
        if symbol in cards
    )


KINDS = ("directed", "leaf", "interior")


def tick_kinds(rows: list[WorkRow]) -> dict[str, int]:
    """Count a repo's working ticks by what kind of card they worked (nemik:W485).

    The three kinds are exclusive, taken in order: a directed card (someone asked for it) is
    directed whatever else it is; of the rest, a card nothing waits on is a leaf, and any other is
    interior (it unblocks something).

    Args:
        rows: What `working_rows` returned.

    Returns:
        tick count per kind in KINDS, each present, zero when no tick was of that kind.

    """
    counts = dict.fromkeys(KINDS, 0)
    for _, _, _, leaf, directed in rows:
        if directed:
            counts["directed"] += 1
        elif leaf:
            counts["leaf"] += 1
        else:
            counts["interior"] += 1
    return counts


def open_leaf_stamps(queue_text: str) -> list[str]:
    """Give the `issued_at` of every open leaf of a queue, the cards that could be worked now.

    An open leaf is a card that is not done or dropped and that nothing waits on (the same leaf
    `working_rows` uses). The stamps are text, oldest first, so the caller decides how to age them;
    a leaf with no `issued_at` is left out rather than counted as new (nemik:W485).

    Args:
        queue_text: The text of a paths-forward.json.

    Returns:
        The stamps, sorted; empty when the text is not a queue.

    """
    cards = cards_of(queue_text)
    try:
        doc: object = json.loads(queue_text)
    except ValueError:
        return []
    if not isinstance(doc, dict):
        return []
    items = doc.get("waypoints")
    if not isinstance(items, list):
        return []
    out: list[str] = []
    for card in items:
        if not isinstance(card, dict):
            continue
        symbol = str(card.get("symbol"))
        stamp = card.get("issued_at")
        if card.get("status") in {"done", "dropped"} or not isinstance(stamp, str):
            continue
        if symbol in cards and is_leaf(cards, symbol):
            out.append(stamp)
    return sorted(out)


Edge = tuple[str, str, str]


def cross_repo(ref: str, repo: str) -> bool:
    """Say whether a reference names a card of some other repo (nemik:W547).

    Args:
        ref: A reference as a queue writes it, `W<n>` or `repo:W<n>`.
        repo: The repo whose view this is.

    Returns:
        True for `other:W<n>` where other is not `repo`.

    """
    head, sep, _ = ref.partition(":")
    return bool(sep) and head != repo


def edges_of(queues: dict[str, str], repo: str, symbol: str) -> list[Edge]:
    """List the cross-repo edges of a done or dropped card, one per letter owed (nemik:W547).

    When a card lands, the repos that were waiting on it, were caused by it, or were enabled by it
    want a letter. Three kinds of edge, all across repos (an edge inside the card's own repo is that
    repo's business): another repo's card lists this one in `blocked_on`; another repo's card names
    this one as its `caused_by`; this card's own `enables` names a card of another repo. The
    delivery record that makes a letter go out once, and the letter writer, come after this walk.

    Args:
        queues: Each repo's name and the text of its paths-forward.json.
        repo: The repo that holds the card.
        symbol: The card's symbol, `W<n>`.

    Returns:
        (kind, other repo, other symbol) for each edge, sorted, kind one of blocked_on, caused_by or
        enables. For the first two the other card is the one that names this card; for enables it is
        the one this card names.

    """
    mine = f"{repo}:{symbol}"
    out: set[Edge] = set()
    for other, text in queues.items():
        if other == repo:
            continue
        for sym, card in cards_of(text).items():
            if mine in card.get("blocked_on", []):
                out.add(("blocked_on", other, sym))
            if mine in card.get("caused_by", []):
                out.add(("caused_by", other, sym))
    own = cards_of(queues.get(repo, "")).get(symbol, {})
    for ref in own.get("enables", []):
        if cross_repo(ref, repo):
            head, _, tail = ref.partition(":")
            out.add(("enables", head, tail))
    return sorted(out)
