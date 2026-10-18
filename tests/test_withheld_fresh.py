# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W647: a withheld list whose as_of is stale, missing or malformed is refused."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from nemik.withheld import WithheldError
from nemik.withheldage import require_fresh

NOW = datetime(2026, 10, 18, 2, 0, 0, tzinfo=UTC).timestamp()
LIMIT = 900


def _list(tmp_path: Path, as_of: object) -> Path:
    """Write a version-1 list with the given as_of.

    Args:
        tmp_path: A scratch directory.
        as_of: The stamp, of any type.

    Returns:
        The file.

    """
    doc: dict[str, object] = {"version": 1, "as_of": as_of, "items": []}
    path = tmp_path / "withheld.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def test_a_recent_list_passes(tmp_path: Path) -> None:
    """A minute old is within fifteen."""
    require_fresh(_list(tmp_path, "2026-10-18T01:59:00Z"), LIMIT, NOW)


def test_a_list_past_the_bound_is_refused(tmp_path: Path) -> None:
    """Sixteen minutes old is over the bound and the message says how old."""
    with pytest.raises(WithheldError, match="960 s old"):
        require_fresh(_list(tmp_path, "2026-10-18T01:44:00Z"), LIMIT, NOW)


def test_the_fifteen_day_old_list_is_refused(tmp_path: Path) -> None:
    """The list that sat stale from 2026-10-03 would have been refused."""
    with pytest.raises(WithheldError, match="producer has stopped"):
        require_fresh(_list(tmp_path, "2026-10-03T12:30:19Z"), LIMIT, NOW)


@pytest.mark.parametrize("stamp", [None, 17, "x", "2026-10-18T01:59:00"])
def test_a_missing_or_malformed_stamp_is_refused(tmp_path: Path, stamp: object) -> None:
    """No stamp, a number, text that is not a time, or a time with no offset: refused."""
    with pytest.raises(WithheldError):
        require_fresh(_list(tmp_path, stamp), LIMIT, NOW)


def test_a_stamp_far_in_the_future_is_refused(tmp_path: Path) -> None:
    """A clock that is an hour ahead is not trusted."""
    with pytest.raises(WithheldError, match="future"):
        require_fresh(_list(tmp_path, "2026-10-18T03:00:00Z"), LIMIT, NOW)


def test_a_missing_file_is_refused(tmp_path: Path) -> None:
    """The producer removes the file on a refusal; a reader then fails closed."""
    with pytest.raises(WithheldError, match="cannot read"):
        require_fresh(tmp_path / "none.json", LIMIT, NOW)
