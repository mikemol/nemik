# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""waitlog: which card has waited longest per pair of repos, as OTLP log records (nemik:W886).

The wait gauges (waitemit) carry the two repos as labels and never a card symbol, since a symbol
would multiply the series. The symbols belong here: one log record per waiting-and-blocking pair
naming the card that has waited longest and the card it waits on, sent to the log store luthen
names `victorialogs-http`, so the dashboard's number links to a card a reader can open.
"""

import json
from typing import TYPE_CHECKING

from mikemol.endpoints.resolve import base_url
from mikemol.otlp.logs import Entry, request
from mikemol.otlp.metrics import resource_here
from mikemol.otlp.sender import LOGS_PATH, Post, SendError, post, send

from nemik.waitrows import Oldest

if TYPE_CHECKING:
    from google.protobuf.message import Message

ENDPOINT = "victorialogs-http"
SERVICE = "nemik-waits"
NAMESPACE = "nemik"
FAILED = -1
CONTEXT = "https://www.w3.org/ns/activitystreams"


def _iri(cite: str) -> str:
    """Name a card by IRI, as the queue graph does.

    Returns:
        `urn:nemik:<repo>/W<n>` for `<repo>:W<n>`.

    """
    repo, _, symbol = cite.partition(":")
    return f"urn:nemik:{repo}/{symbol}"


def activity(
    waiting: str,
    waiting_cite: str,
    ticks: int,
    blocker_cite: str,
    time_ns: int,
) -> str:
    """Word one wait as an ActivityStreams Update (nemik:W944, docs/federation-log.md).

    Args:
        waiting: The waiting card's repo, the actor.
        waiting_cite: The waiting card, `<repo>:W<n>`.
        ticks: How many ticks it has waited.
        blocker_cite: The card it waits on.
        time_ns: When the reading was true, in Unix nanoseconds.

    Returns:
        A JSON object whose id is the pair and the instant, so a re-sent record has the same id,
        and whose `content` is the sentence the record carried before.

    """
    document = {
        "@context": CONTEXT,
        "id": f"urn:nemik:wait:{waiting_cite.replace(':', '/')}/"
        f"{blocker_cite.replace(':', '/')}/{time_ns}",
        "type": "Update",
        "actor": f"urn:nemik:{waiting}",
        "object": _iri(waiting_cite),
        "target": _iri(blocker_cite),
        "content": f"{waiting_cite} has waited {ticks} ticks on {blocker_cite}",
    }
    return json.dumps(document, sort_keys=True)


def entries(oldest: list[Oldest], time_ns: int) -> list[Entry]:
    """Write one log record per pair of repos.

    Args:
        oldest: Per pair, the longest-waiting card and its blocker.
        time_ns: When the readings were true, in Unix nanoseconds.

    Returns:
        The records, the two repos as attributes and an ActivityStreams Update as the body.

    """
    return [
        Entry(
            activity(waiting, waiting_cite, ticks, blocker_cite, time_ns),
            time_ns,
            "INFO",
            {"waiter": waiting, "blocker": blocking},
        )
        for waiting, blocking, ticks, waiting_cite, blocker_cite in oldest
    ]


def emit(
    oldest: list[Oldest], time_ns: int, environ: dict[str, str], poster: Post = post
) -> int:
    """Send the records to the log store, one request each.

    Args:
        oldest: Per pair, the longest-waiting card and its blocker.
        time_ns: When the readings were true, in Unix nanoseconds.
        environ: The environment the endpoint name resolves through.
        poster: The HTTP seam, replaced in tests.

    Returns:
        The number of records sent; 0 when there is nothing to send, FAILED when the endpoint is
        unnamed or a send failed.

    """
    records = entries(oldest, time_ns)
    if not records:
        return 0
    base = base_url(ENDPOINT, environ)
    if base is None:
        return FAILED
    resource = resource_here(SERVICE, NAMESPACE)
    for record in records:
        built: Message = request(resource, record)
        try:
            send(base.rstrip("/") + LOGS_PATH, built.SerializeToString(), poster)
        except SendError:
            return FAILED
    return len(records)
