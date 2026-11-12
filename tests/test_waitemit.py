# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""Tests for waitemit: the wait series as gauges (nemik:W885) and the wake gauges (nemik:W1604)."""


from typing import TYPE_CHECKING

from mikemol.otlp.sender import Post, SendError
from rdflib import Graph

from nemik.waitemit import (
    COUNT,
    ENDPOINT,
    OLDEST,
    POSITION,
    WAKE_REQUIRED,
    WAKE_WAITERS,
    emit,
    gauge_samples,
    wake_readings,
    wake_samples,
)
from nemik.waitrows import UNRANKED, Edge

if TYPE_CHECKING:
    from pathlib import Path

    from nemik.wake import Waiter, WakeRow

NOW = 1_700_000_000_000_000_000
OK = 200
REFUSED = 400
EDGES: list[Edge] = [
    ("alpha", "beta", 7, 3),
    ("alpha", "beta", 2, UNRANKED),
    ("alpha", "beta", 4, 1),
    ("gamma", "beta", 6, UNRANKED),
]
SAMPLES_SENT = 6
BEST_PLACE = 1
OLDEST_ALPHA = 7
CARDS_ALPHA = 3
WAITER: Waiter = {"blocked": "x:W1", "claimed_by": [], "title": "a card"}
ROSTER: list[WakeRow] = [
    {"repo": "alpha", "state": "asleep", "waiting": [WAITER, WAITER]},
    {"repo": "beta", "state": "awake", "waiting": [WAITER]},
    {"repo": "delta", "state": "idle", "waiting": [WAITER]},
    {"repo": "echo", "state": "unknown", "waiting": [WAITER]},
]
KNOWN = ["alpha", "beta", "delta", "echo", "gamma"]
TWO_WAITERS = 2


def _endpoints(tmp_path: Path, url: str) -> dict[str, str]:
    path = tmp_path / "endpoints.json"
    path.write_text(f'{{"{ENDPOINT}": "{url}"}}', encoding="utf-8")
    return {"MIKEMOL_ENDPOINTS": str(path)}


def _answer(status: int) -> Post:
    def poster(url: str, body: bytes) -> int:
        del url, body
        return status

    return poster


def test_three_gauges_per_pair() -> None:
    """Each pair of repos gives an oldest wait, a card count and a best blocker position."""
    made = gauge_samples(EDGES, NOW)
    assert len(made) == SAMPLES_SENT
    by_name = {(s.name, (s.labels or {})["waiter"]): s.value for s in made}
    assert by_name[OLDEST, "alpha"] == OLDEST_ALPHA
    assert by_name[COUNT, "alpha"] == CARDS_ALPHA
    assert by_name[POSITION, "alpha"] == BEST_PLACE
    assert by_name[POSITION, "gamma"] == UNRANKED


def test_labels_are_the_two_repos_only() -> None:
    """A card symbol is never a label."""
    for sample in gauge_samples(EDGES, NOW):
        assert set(sample.labels or {}) == {"waiter", "blocker"}
        assert sample.time_ns == NOW


def test_nothing_waiting_sends_nothing() -> None:
    """No edge means no request and no endpoint lookup."""
    assert emit([], NOW, {}, _answer(OK)) == 0


def test_unnamed_endpoint_is_a_failure(tmp_path: Path) -> None:
    """An endpoints file without the name is a failure, not a guessed address."""
    environ = {"MIKEMOL_ENDPOINTS": str(tmp_path / "missing.json")}
    assert emit(EDGES, NOW, environ, _answer(OK)) == -1


def test_emit_posts_one_request_to_the_metrics_path(tmp_path: Path) -> None:
    """One request carries every sample, to luthen's metrics path, as three metrics."""
    seen: list[tuple[str, bytes]] = []

    def poster(url: str, body: bytes) -> int:
        seen.append((url, body))
        return OK

    environ = _endpoints(tmp_path, "http://host:8428/")
    assert emit(EDGES, NOW, environ, poster) == SAMPLES_SENT
    assert len(seen) == 1
    assert seen[0][0] == "http://host:8428/opentelemetry/v1/metrics"
    for name in (OLDEST, COUNT, POSITION):
        assert name.encode() in seen[0][1]


def test_refused_send_is_a_failure(tmp_path: Path) -> None:
    """A 400 from the store is reported, not swallowed."""
    environ = _endpoints(tmp_path, "http://host:8428")
    assert emit(EDGES, NOW, environ, _answer(REFUSED)) == -1


def test_unreachable_send_is_a_failure(tmp_path: Path) -> None:
    """A send error is reported, not raised."""

    def poster(url: str, body: bytes) -> int:
        del body
        raise SendError(url)

    environ = _endpoints(tmp_path, "http://host:8428")
    assert emit(EDGES, NOW, environ, poster) == -1


def test_wake_is_required_only_where_a_sleeper_has_waiters() -> None:
    """Asleep, idle and unknown with a waiter read 1; awake, and a workstream no one waits on, 0."""
    made = {
        (s.name, (s.labels or {})["repo"]): s.value
        for s in wake_samples(ROSTER, KNOWN, NOW)
    }
    assert [made[WAKE_REQUIRED, repo] for repo in KNOWN] == [1, 0, 1, 1, 0]


def test_the_waiters_are_counted_per_workstream() -> None:
    """The count is the roster row's waiting length, and 0 for a workstream not on the roster."""
    made = {
        (s.name, (s.labels or {})["repo"]): s.value
        for s in wake_samples(ROSTER, KNOWN, NOW)
    }
    assert made[WAKE_WAITERS, "alpha"] == TWO_WAITERS
    assert made[WAKE_WAITERS, "gamma"] == 0


def test_the_wake_gauges_carry_the_repo_label_only() -> None:
    """Two samples per known workstream, labelled by repo alone, stamped with the reading time."""
    made = wake_samples(ROSTER, KNOWN, NOW)
    assert len(made) == TWO_WAITERS * len(KNOWN)
    for sample in made:
        assert set(sample.labels or {}) == {"repo"}
        assert sample.time_ns == NOW


def test_no_liveness_sends_no_wake_gauges(tmp_path: Path) -> None:
    """Without luthen's liveness every blocker reads unknown, so nothing is sent at all."""
    assert wake_readings(Graph(), tmp_path, NOW) == ()


def test_the_wake_gauges_ride_the_same_request(tmp_path: Path) -> None:
    """One request carries the wait gauges and the wake gauges, and the count includes both."""
    seen: list[bytes] = []

    def poster(url: str, body: bytes) -> int:
        del url
        seen.append(body)
        return OK

    more = tuple(wake_samples(ROSTER, KNOWN, NOW))
    environ = _endpoints(tmp_path, "http://host:8428/")
    assert emit(EDGES, NOW, environ, poster, more) == SAMPLES_SENT + len(more)
    assert len(seen) == 1
    for name in (WAKE_REQUIRED, WAKE_WAITERS):
        assert name.encode() in seen[0]
