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
After the cards come the repo's activities from the log (nemik:W949, docs/federation-log.md), read
from the file nemik-hostroot --log-activities writes: the collection says so in its summary when
that file is missing or unreadable, since absence is not a verdict.
Everything here is derived from the queue graph and nothing is delivered: an inbox, a signature or
a push to another server crosses nemik's read-only boundary and is the operator's decision, so this
stops at the outbox document.
"""

import json
from pathlib import Path

from rdflib import Graph
from rdflib.namespace import DCTERMS

from nemik.adapter import NEMIK, OSLC_CM, workstream_uri
from nemik.logactivities import read_log

CONTEXT = ["https://www.w3.org/ns/activitystreams", "https://forgefed.org/ns"]
LOG_KEYS = ("id", "type", "actor", "object", "target", "content", "published")
LOG_ABSENT = (
    "The log's activities are not part of this collection: no log file was read "
    "(docs/federation-log.md)."
)


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


def log_part(
    actor: str, log_path: Path | None, withheld: frozenset[str]
) -> tuple[list[dict[str, object]], dict[str, str]]:
    """Read the log's activities one actor published, as outbox items (nemik:W949).

    Args:
        actor: The workstream IRI, `urn:nemik:<repo>`.
        log_path: The file nemik-hostroot --log-activities wrote, or None for no file.
        withheld: Card IRIs that stay out of the document whole; an activity naming one is dropped.

    Returns:
        (the items, oldest first as the file holds them; the keys to add to the collection): none
        and a summary saying so when the file is not given, missing or unreadable.

    """
    if log_path is None:
        return [], {"summary": LOG_ABSENT}
    try:
        found = read_log(log_path.read_text(encoding="utf-8"))[1]
    except (OSError, ValueError):
        return [], {"summary": LOG_ABSENT}
    items: list[dict[str, object]] = [
        {key: a[key] for key in LOG_KEYS if key in a}
        for a in found
        if a.get("actor") == actor
        and a.get("object") not in withheld
        and a.get("target") not in withheld
    ]
    return items, {}


def outbox(
    repo: str,
    queue: Graph,
    withheld: frozenset[str] = frozenset(),
    log_path: Path | None = None,
) -> str:
    """Render a repo's outbox as an ActivityStreams OrderedCollection.

    Args:
        repo: The repo's name.
        queue: The merged queue graph.
        withheld: Card IRIs that stay out of the document whole (luthen's withheld list).
        log_path: The file of log activities (nemik:W949), whose repo's own come after the cards.

    Returns:
        The collection as JSON-LD text, the cards in card-IRI order and then the log's activities
        in the file's order, so the bytes are stable.

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
    logged, extra = log_part(ws, log_path, withheld)
    items.extend(logged)
    document: dict[str, object] = {
        "@context": CONTEXT,
        "id": f"{ws}/outbox",
        "type": "OrderedCollection",
        "attributedTo": ws,
        "totalItems": len(items),
        "orderedItems": items,
        **extra,
    }
    return json.dumps(document, indent=1)
