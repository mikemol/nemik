# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W854: nemik-history --waits --publish writes a document nemik-serve serves with its age."""

from datetime import UTC, datetime
from http import HTTPStatus
from pathlib import Path

from nemik.histdocs import decode
from nemik.history import Opts, emit
from nemik.serve import history_response

ROWS = {"alpha": {"ready": {"n": 3, "median_days": 1.5, "p90_days": 4.0}}}
NOON = datetime(2026, 10, 22, 12, 0, 0, tzinfo=UTC)


def _publish(directory: Path) -> None:
    """Publish the waits rows as the command would."""
    args = Opts()
    args.json = False
    args.publish = directory
    assert emit(args, "waits", ROWS)


def test_publish_writes_a_stamped_document_and_prints_nothing(tmp_path: Path) -> None:
    """The file is a stamp line then the rows as JSON."""
    _publish(tmp_path)
    as_of, body = decode((tmp_path / "waits.json").read_text(encoding="utf-8"))
    assert as_of
    assert '"median_days": 1.5' in body
    assert not list(tmp_path.glob(".*.part")), "the partial file was renamed away"


def test_without_publish_or_json_the_caller_prints_the_text_form() -> None:
    """The emitter declines, so the command falls through to its own lines."""
    args = Opts()
    args.json = False
    args.publish = None
    assert not emit(args, "waits", ROWS)


def test_the_route_serves_the_document_with_its_age(tmp_path: Path) -> None:
    """A fresh document is served not stale, wrapped with its mode and stamp."""
    _publish(tmp_path)
    code, _, body = history_response(tmp_path, "/history/waits.json", datetime.now(UTC))
    text = body.decode("utf-8")
    assert code == HTTPStatus.OK
    assert '"mode": "waits"' in text
    assert '"stale": false' in text
    assert '"median_days": 1.5' in text


def test_a_document_older_than_the_bound_is_served_stale(tmp_path: Path) -> None:
    """Years later the same file answers with stale true, not a refusal."""
    _publish(tmp_path)
    far = datetime(2099, 1, 1, tzinfo=UTC)
    code, _, body = history_response(tmp_path, "/history/waits.json", far)
    assert code == HTTPStatus.OK
    assert '"stale": true' in body.decode("utf-8")


def test_no_directory_unknown_mode_or_missing_file_is_not_found(
    tmp_path: Path,
) -> None:
    """Never a guessed board, and a path cannot name another file."""
    codes = [
        history_response(None, "/history/waits.json", NOON)[0],
        history_response(tmp_path, "/history/waits.json", NOON)[0],
        history_response(tmp_path, "/history/../x.json", NOON)[0],
        history_response(tmp_path, "/history/oldest.json", NOON)[0],
    ]
    assert codes == [HTTPStatus.NOT_FOUND] * len(codes)
