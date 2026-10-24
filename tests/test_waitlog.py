# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""Tests for waitlog: the longest-waiting card per pair as log records (nemik:W886)."""

from pathlib import Path

from mikemol.otlp.sender import Post

from nemik.waitlog import ENDPOINT, FAILED, emit, entries
from nemik.waitrows import Oldest

NOW = 1_700_000_000_000_000_000
OK = 200
REFUSED = 400
OLDEST: list[Oldest] = [
    ("beta", "alpha", 7, "beta:W5", "alpha:W1"),
    ("gamma", "alpha", 2, "gamma:W9", "alpha:W3"),
]
LOGS_URL = "http://host:9428/insert/opentelemetry/v1/logs"


def _endpoints(tmp_path: Path, url: str) -> dict[str, str]:
    path = tmp_path / "endpoints.json"
    path.write_text(f'{{"{ENDPOINT}": "{url}"}}', encoding="utf-8")
    return {"MIKEMOL_ENDPOINTS": str(path)}


def _answer(status: int) -> Post:
    def poster(url: str, body: bytes) -> int:
        del url, body
        return status

    return poster


def test_a_record_names_the_cards_and_labels_the_repos() -> None:
    """The body carries both cites; the attributes carry only the two repos."""
    first = entries(OLDEST, NOW)[0]
    assert first.body == (
        '{"@context": "https://www.w3.org/ns/activitystreams", '
        '"actor": "urn:nemik:beta", '
        '"content": "beta:W5 has waited 7 ticks on alpha:W1", '
        f'"id": "urn:nemik:wait:beta/W5/alpha/W1/{NOW}", '
        '"object": "urn:nemik:beta/W5", '
        '"target": "urn:nemik:alpha/W1", '
        '"type": "Update"}'
    )
    assert dict(first.labels or {}) == {"waiter": "beta", "blocker": "alpha"}
    assert first.time_ns == NOW


def test_nothing_waiting_sends_nothing() -> None:
    """No pair means no request and no endpoint lookup."""
    assert emit([], NOW, {}, _answer(OK)) == 0


def test_one_request_per_record_to_the_logs_path(tmp_path: Path) -> None:
    """Each record goes to luthen's logs path and the cites are in the payload."""
    seen: list[tuple[str, bytes]] = []

    def poster(url: str, body: bytes) -> int:
        seen.append((url, body))
        return OK

    environ = _endpoints(tmp_path, "http://host:9428/")
    assert emit(OLDEST, NOW, environ, poster) == len(OLDEST)
    assert [url for url, _ in seen] == [LOGS_URL, LOGS_URL]
    assert b"beta:W5" in seen[0][1]
    assert b"gamma:W9" in seen[1][1]


def test_unnamed_endpoint_and_refused_send_are_failures(tmp_path: Path) -> None:
    """No guessed address, and a 400 is reported."""
    missing = {"MIKEMOL_ENDPOINTS": str(tmp_path / "missing.json")}
    assert emit(OLDEST, NOW, missing, _answer(OK)) == FAILED
    named = _endpoints(tmp_path, "http://host:9428")
    assert emit(OLDEST, NOW, named, _answer(REFUSED)) == FAILED
