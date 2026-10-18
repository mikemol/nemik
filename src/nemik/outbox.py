# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W354: a repo's cards as a ForgeFed outbox, read-only (ActivityStreams 2.0 JSON-LD).

ForgeFed extends ActivityPub with the verbs a forge speaks about tickets. A workstream is the actor
(nemik.ttl types it so); each card is a Ticket, and its state is the activity the actor last did:
- a ready or blocked card is an Offer of the ticket;
- a working card is an Accept of it (the actor took it on);
- a done card is a Resolve of it.
Everything here is derived from the queue graph and nothing is delivered: an inbox, a signature or
a push to another server crosses nemik's read-only boundary and is the operator's decision, so this
stops at the outbox document.
"""

import json

from rdflib import Graph
from rdflib.namespace import DCTERMS

from nemik.adapter import NEMIK, OSLC_CM, workstream_uri

CONTEXT = ["https://www.w3.org/ns/activitystreams", "https://forgefed.org/ns"]


def verb(state: str) -> str:
    """Name the activity a card's state stands for.

    Args:
        state: The card's OSLC state IRI.

    Returns:
        Resolve for done, Accept for working, otherwise Offer.

    """
    if state == str(NEMIK.Done):
        return "Resolve"
    if state == str(NEMIK.Working):
        return "Accept"
    return "Offer"


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
        ticket: dict[str, object] = {"type": "Ticket", "id": str(card)}
        if title is not None:
            ticket["summary"] = str(title)
        activity: dict[str, object] = {
            "type": verb(str(state)),
            "actor": ws,
            "object": ticket,
        }
        # The activity happened when the card was last worked; one never worked, when issued.
        when = queue.value(card, NEMIK.lastWorked) or queue.value(card, DCTERMS.created)
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
