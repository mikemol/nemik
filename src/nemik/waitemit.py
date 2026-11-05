# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""waitemit: the cross-repo wait series as OTLP gauges, from the host (nemik:W885, W836, W579).

luthen's fleet flow dashboard (luthen-observability:W1196) wants the wait edges as series. This
reads the merged queue graph the way nemik-rank does, groups the cross-repo wait edges per pair
of repos (waitseries), and sends three gauges per pair through mikemol.otlp to the metrics store
luthen names `vmsingle-http`: the oldest wait in loop ticks, how many cards wait, and the best
rank position among the blockers (0 when none is a ready leaf). The labels are the two repos
only; a card symbol is never a label, and the cards go in log records (waitlog, nemik:W886). It
runs on the host (`python -m nemik.waitemit`), since the pod has neither the queues of the other
repos nor luthen's endpoints file.
"""

import argparse
import os
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

from mikemol.endpoints.resolve import base_url
from mikemol.otlp.metrics import Resource, Sample, gauges, resource_here
from mikemol.otlp.sender import METRICS_PATH, Post, SendError, post, send
from rdflib import Graph

from nemik import waitlog
from nemik.check import survey
from nemik.score import load_weights
from nemik.waitrows import UNRANKED, Edge, oldest_waits, wait_edges
from nemik.waitseries import samples
from nemik.wake import WakeRow, read_liveness, roster, workstreams

if TYPE_CHECKING:
    from google.protobuf.message import Message

ENDPOINT = "vmsingle-http"
SERVICE = "nemik-waits"
NAMESPACE = "nemik"
OLDEST = "nemik_wait_oldest_ticks"
COUNT = "nemik_wait_cards"
POSITION = "nemik_wait_blocker_position"
WAKE_REQUIRED = "nemik_wake_required"
WAKE_WAITERS = "nemik_wake_waiters"


class _Options(argparse.Namespace):
    """The command line, typed."""

    root: Path


def _best_positions(edges: list[Edge]) -> dict[tuple[str, str], int]:
    """Find, per pair of repos, the best rank position among its blockers.

    Returns:
        (waiting repo, blocking repo) -> the smallest position above UNRANKED, else UNRANKED.

    """
    best: dict[tuple[str, str], int] = {}
    for waiting, blocking, _, place in edges:
        pair = (waiting, blocking)
        have = best.get(pair, UNRANKED)
        if place != UNRANKED and (have == UNRANKED or place < have):
            have = place
        best[pair] = have
    return best


def gauge_samples(edges: list[Edge], time_ns: int) -> list[Sample]:
    """Turn the wait edges into three gauge samples per pair of repos.

    Args:
        edges: The cross-repo wait edges with their blocker positions.
        time_ns: When the readings were true, in Unix nanoseconds.

    Returns:
        The oldest-wait, card-count and blocker-position samples, repo labels only.

    """
    best = _best_positions(edges)
    out: list[Sample] = []
    for sample in samples([(w, b, ticks) for w, b, ticks, _ in edges]):
        labels = {"waiter": sample.waiter, "blocker": sample.blocker}
        place = best[sample.waiter, sample.blocker]
        out.extend(
            [
                Sample(OLDEST, sample.oldest, time_ns, labels, "{tick}"),
                Sample(COUNT, sample.count, time_ns, labels, "{card}"),
                Sample(POSITION, place, time_ns, labels),
            ]
        )
    return out


def wake_samples(rows: list[WakeRow], repos: list[str], time_ns: int) -> list[Sample]:
    """Turn the wake roster into two gauges per workstream (nemik:W1604, luthen's W1928).

    `nemik_wake_required` is 1 when something waits on the workstream and its session is not awake,
    0 otherwise; `nemik_wake_waiters` is how many cards wait on it. Every workstream in `repos`
    reads a value, so a 0 is a reading and a missing series means nemik could not tell. The roster
    is built without alarms, so the owner of a fired alarm is not counted here.

    Returns:
        Two samples per workstream, labelled by repo alone, in repo order.

    """
    waiting = {row["repo"]: len(row.get("waiting", [])) for row in rows}
    asleep = {row["repo"] for row in rows if row.get("state") != "awake"}
    out: list[Sample] = []
    for repo in sorted({*repos, *waiting}):
        waiters = waiting.get(repo, 0)
        required = 1 if waiters and repo in asleep else 0
        labels = {"repo": repo}
        out.extend(
            [
                Sample(WAKE_REQUIRED, required, time_ns, labels),
                Sample(WAKE_WAITERS, waiters, time_ns, labels, "{card}"),
            ]
        )
    return out


def wake_readings(g: Graph, root: Path, time_ns: int) -> tuple[Sample, ...]:
    """Read the wake gauges, or none when luthen's liveness could not be read.

    Without liveness every blocker reads `unknown`, which would make each waiting workstream
    wake-required, so nothing is sent: a missing series is "could not tell", never "nothing waits".

    Returns:
        The samples; empty when there is no liveness.

    """
    live, _ = read_liveness(root, None)
    if not live:
        return ()
    return tuple(wake_samples(roster(g, live), workstreams(g), time_ns))


def payload(resource: Resource, readings: list[Sample]) -> bytes:
    """Serialise the readings as one OTLP metrics request.

    Returns:
        The protobuf body.

    """
    request: Message = gauges(resource, readings)
    return request.SerializeToString()


def emit(
    edges: list[Edge],
    time_ns: int,
    environ: dict[str, str],
    poster: Post = post,
    more: tuple[Sample, ...] = (),
) -> int:
    """Send the wait series to the metrics store.

    Args:
        edges: The cross-repo wait edges with their blocker positions.
        time_ns: When the readings were true, in Unix nanoseconds.
        environ: The environment the endpoint name resolves through.
        poster: The HTTP seam, replaced in tests.
        more: Further readings sent in the same request (the wake gauges, nemik:W1604).

    Returns:
        The number of samples sent; 0 when there is nothing to send, -1 when the endpoint is
        unnamed or the send failed.

    """
    readings = [*gauge_samples(edges, time_ns), *more]
    if not readings:
        return 0
    base = base_url(ENDPOINT, environ)
    if base is None:
        return -1
    body = payload(resource_here(SERVICE, NAMESPACE), readings)
    try:
        send(base.rstrip("/") + METRICS_PATH, body, poster)
    except SendError as error:
        sys.stderr.write(f"nemik-waitemit: {error}\n")
        return -1
    return len(readings)


def main(argv: list[str] | None = None) -> int:
    """Survey the fleet's queues and emit the wait series and its log records.

    Returns:
        0 when both were sent or nothing waits; 1 when an endpoint was unnamed or a send failed.

    """
    parser = argparse.ArgumentParser(
        prog="python -m nemik.waitemit", description=__doc__
    )
    parser.add_argument("--root", type=Path, default=Path.home() / "github")
    options = parser.parse_args(argv, namespace=_Options())
    g = Graph()
    for _, queue_graph, _ in survey(options.root):
        if queue_graph is not None:
            g += queue_graph
    now = time.time_ns()
    environ = dict(os.environ)
    sent = emit(
        wait_edges(g, load_weights()),
        now,
        environ,
        post,
        wake_readings(g, options.root, now),
    )
    logged = waitlog.emit(oldest_waits(g), now, environ)
    if sent < 0 or logged < 0:
        return 1
    sys.stdout.write(f"nemik-waitemit: {sent} samples, {logged} log records\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
