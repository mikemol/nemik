# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W647: nemik-serve --withheld-max-age refuses a stale list before building anything."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from nemik.serve import main

FLEET = Path(__file__).parent / "fixtures" / "fleet"
REFUSED = 2  # the exit code of a refused build


def _list(tmp_path: Path, as_of: str) -> Path:
    """Write an empty version-1 list with the given as_of.

    Args:
        tmp_path: A scratch directory.
        as_of: The stamp.

    Returns:
        The file.

    """
    doc: dict[str, object] = {"version": 1, "as_of": as_of, "items": []}
    path = tmp_path / "withheld.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def _args(tmp_path: Path, withheld: Path) -> list[str]:
    """Spell a static build with the freshness bound.

    Args:
        tmp_path: A scratch directory for the output.
        withheld: The list.

    Returns:
        The command line after the program name.

    """
    return [
        "--root",
        str(FLEET),
        "--static",
        str(tmp_path / "out"),
        "--withheld",
        str(withheld),
        "--withheld-max-age",
        "900",
    ]


def test_a_stale_list_stops_the_build_with_exit_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The fifteen-day-old list: exit 2, the reason on stderr, nothing written."""
    with pytest.raises(SystemExit) as stop:
        main(_args(tmp_path, _list(tmp_path, "2026-10-03T12:30:19Z")))
    assert stop.value.code == REFUSED
    assert "producer has stopped" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


def test_a_fresh_list_builds(tmp_path: Path) -> None:
    """A list stamped now passes the bound and the build writes its files."""
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    main(_args(tmp_path, _list(tmp_path, now)))
    assert (tmp_path / "out" / "graph.json").exists()
