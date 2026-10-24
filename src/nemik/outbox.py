# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W354: a repo's cards as a ForgeFed outbox, read-only (ActivityStreams 2.0 JSON-LD).

ForgeFed extends ActivityPub with the vocabulary a forge speaks about tickets. A workstream is the
actor (nemik.ttl types it so); each card is a Ticket, and the Ticket carries its own state
(nemik:W939, docs/federation-recommendations.md R1): `isResolved` says whether it is closed,
`resolved` when it was, and `context` the tracker it lives in. Its edges (nemik:W940) are
`dependsOn` (what it waits for) and `dependedBy` (what it enables), as card identifiers, which
name another repo's card when the edge crosses repos. The activities are events only:
- a card being minted is a Create of the ticket, published when it was issued;
- a card being closed is a Resolve of it, published when it was last worked.
A ready, blocked or working card has had one event, its minting. Working is not said as an Accept:
in ForgeFed an Accept answers a request, and the standard has no working state to put it in.
Everything here is derived from the queue graph and nothing is delivered: an inbox, a signature or
a push to another server crosses nemik's read-only boundary and is the operator's decision, so this
stops at the outbox document.
"""

import json

from rdflib import Graph
from rdflib.namespace import DCTERMS

from nemik.adapter import NEMIK, OSLC_CM, workstream_uri

CONTEXT = ["https://www.w3.org/ns/activitystreams", "https://forgefed.org/ns"]


def is_resolved(state: str) -> bool:
    """Say whether a card's state is closed.

    Args:
        state: The card's OSLC state IRI.

    Returns:
        True for done.

    """
    return state == str(NEMIK.Done)


def is_card(iri: str) -> bool:
    """Say whether an IRI names a card, not a workstream or the operator (those are no Ticket).

    Args:
        iri: A node the queue graph points at.

    Returns:
        True when its last path segment is W followed by digits.

    """
    tail = iri.rpartition("/")[2]
    return tail.startswith("W") and tail[1:].isdigit()


def verb(state: str) -> str:
    """Name the event a card's state last produced.

    Args:
        state: The card's OSLC state IRI.

    Returns:
        Resolve for done, otherwise Create (the minting).

    """
    return "Resolve" if is_resolved(state) else "Create"


def outbox(repo: str, queue: Graph, withheld: frozenset[str] = frozenset()) -> str:
    """Render a repo's outbox as an ActivityStreams OrderedCollection.

    Args:
        repo: The repo's name.
        queue: The merged queue graph.
        withheld: Card IRIs that stay out of the document whole (luthen's withheld list).

    Returns:
        The collection as JSON-LD text, items in card-IRI order so the bytes are stable.

    """
    ws = str(workstream_uri(repo))
    items: list[dict[str, object]] = []
    for card in sorted(queue.subjects(NEMIK.workstream, workstream_uri(repo)), key=str):
        state = queue.value(card, OSLC_CM.state)
        if state is None or str(card) in withheld:
            continue
        title = queue.value(card, DCTERMS.title)
        closed = is_resolved(str(state))
        # A close happened when the card was last worked; a minting when it was issued.
        issued = queue.value(card, DCTERMS.created)
        worked = queue.value(card, NEMIK.lastWorked)
        when = (worked or issued) if closed else issued
        ticket: dict[str, object] = {
            "type": "Ticket",
            "id": str(card),
            "context": ws,
            "isResolved": closed,
        }
        if title is not None:
            ticket["summary"] = str(title)
        # nemik:W940: the card's edges travel with it, as ForgeFed's dependsOn and its inverse.
        waits = {str(t) for t in queue.objects(card, NEMIK.waitsFor)}
        enables = {str(t) for t in queue.objects(card, NEMIK.enables)}
        if depends := sorted(t for t in waits if is_card(t)):
            ticket["dependsOn"] = depends
        if depended := sorted(t for t in enables if is_card(t)):
            ticket["dependedBy"] = depended
        if closed and when is not None:
            ticket["resolved"] = str(when)
        activity: dict[str, object] = {
            "type": verb(str(state)),
            "actor": ws,
            "object": ticket,
        }
        if when is not None:
            activity["published"] = str(when)
        items.append(activity)
    document: dict[str, object] = {
        "@context": CONTEXT,
        "id": f"{ws}/outbox",
        "type": "OrderedCollection",
        "attributedTo": ws,
        "totalItems": len(items),
        "orderedItems": items,
    }
    return json.dumps(document, indent=1)
