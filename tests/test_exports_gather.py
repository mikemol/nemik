# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W873: nemik-exports uses a repo's own export when it can be trusted, else derives it."""

import json
import os
from pathlib import Path

import pytest

from nemik.exportcli import main

QUEUE: dict[str, list[dict[str, object]]] = {
    "waypoints": [
        {"symbol": "W1", "title": "one", "status": "ready"},
        {"symbol": "W2", "title": "two", "status": "ready"},
    ]
}
OLD, NEW = 1_000_000_000, 2_000_000_000
LUTHEN: dict[str, object] = {
    "version": 1,
    "as_of": "2026-10-23T00:00:00Z",
    "items": [{"ref": "beta:W2", "field": "evidence", "rule": "address-literal"}],
}
CARDS = [{"symbol": "W1", "title": "x"}]


def _own(repo: str, named: str) -> str:
    """Make the text of a repo's own export.

    Args:
        repo: The repo whose directory it sits in.
        named: The repo the export says it belongs to.

    Returns:
        The JSON text: version 2, one whole card, and the repo's W2 withheld.

    """
    body = {"version": 2, "repo": named, "cards": CARDS, "withheld": [f"{repo}:W2"]}
    return json.dumps(body)


def _fleet(root: Path) -> None:
    """Make five repos, each with a queue, in the five states an own export can be in.

    alpha: a fresh valid own export. beta: a valid one older than its queue. gamma: a fresh one
    that names another repo. delta: a fresh one that is not JSON. epsilon: none.
    """
    exports = {
        "alpha": _own("alpha", "alpha"),
        "beta": _own("beta", "beta"),
        "gamma": _own("gamma", "other"),
        "delta": "{not json",
    }
    for repo in ("alpha", "beta", "gamma", "delta", "epsilon"):
        state = root / repo / ".claude" / "paths-forward.json"
        state.parent.mkdir(parents=True)
        state.write_text(json.dumps(QUEUE), encoding="utf-8")
        stale = repo == "beta"
        os.utime(state, ns=((NEW if stale else OLD),) * 2)
        if repo in exports:
            own = state.with_name("paths-forward.export.json")
            own.write_text(exports[repo], encoding="utf-8")
            os.utime(own, ns=((OLD if stale else NEW),) * 2)


def _run(tmp_path: Path) -> Path:
    """Run nemik-exports over the fleet with luthen's list withholding beta:W2.

    Args:
        tmp_path: A scratch directory.

    Returns:
        The exports directory.

    """
    root = tmp_path / "fleet"
    _fleet(root)
    listing = tmp_path / "withheld.json"
    listing.write_text(json.dumps(LUTHEN), encoding="utf-8")
    out = tmp_path / "exports"
    argv = ["--root", str(root), "--withheld", str(listing), "--out", str(out)]
    main(argv)
    return out


def test_a_fresh_valid_own_export_is_written_as_it_stands(tmp_path: Path) -> None:
    """Alpha's own export, its whole card and its own withheld ref, is the one served."""
    text = (_run(tmp_path) / "alpha.json").read_text(encoding="utf-8")
    assert '"title": "x"' in text
    assert '"withheld": ["alpha:W2"]' in text


def test_a_stale_wrong_or_unreadable_export_is_derived_from_luthens_list(
    tmp_path: Path,
) -> None:
    """Beta (older than its queue), gamma (another repo's) and delta (not JSON) are derived."""
    out = _run(tmp_path)
    for repo in ("beta", "gamma", "delta"):
        text = (out / f"{repo}.json").read_text(encoding="utf-8")
        assert '"title"' not in text
        assert '"symbol": "W1"' in text


def test_a_repo_with_no_own_export_is_derived_as_before(tmp_path: Path) -> None:
    """Beta's ref luthen withholds is withheld; epsilon, not in the list, publishes both."""
    out = _run(tmp_path)
    assert '"withheld": ["beta:W2"]' in (out / "beta.json").read_text(encoding="utf-8")
    epsilon = (out / "epsilon.json").read_text(encoding="utf-8")
    assert '{"symbol": "W1"}, {"symbol": "W2"}' in epsilon


def test_the_command_says_how_many_came_from_the_repos_own(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The original line is kept for readers of it; the own count follows on its own line."""
    _run(tmp_path)
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("5 export(s) written to ")
    assert lines[1] == "1 of them from the repo's own export"
