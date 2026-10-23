# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""Tests for waitemit: the wait series as gauges (nemik:W885)."""

from pathlib import Path

from mikemol.otlp.sender import Post, SendError

from nemik.waitemit import COUNT, ENDPOINT, OLDEST, POSITION, emit, gauge_samples
from nemik.waitrows import UNRANKED, Edge

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
