# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W862, W863: nemik-serve answers /check/letters.json and /check/fold.json."""

import json
from http import HTTPStatus
from pathlib import Path

from nemik.letters import report
from nemik.serve import Model

EMPTY: dict[str, list[dict[str, object]]] = {"waypoints": []}


def _fleet(root: Path) -> None:
    """Make alpha and beta, and put in alpha's inbox a letter addressed to beta.

    The letter is misdelivered, and no waypoint cites it, so it is an orphan too. Beta has an
    inbox, so the fold report can offer to copy the letter there.
    """
    for repo in ("alpha", "beta"):
        state = root / repo / ".claude" / "paths-forward.json"
        state.parent.mkdir(parents=True)
        state.write_text(json.dumps(EMPTY), encoding="utf-8")
        (root / repo / "inbox").mkdir()
    (root / "alpha" / "inbox" / "2026-10-22-hello.md").write_text(
        "# gamma -> beta: hello\n", encoding="utf-8"
    )


def _said(model: Model, name: str) -> str:
    """Answer a report route and check it says 200.

    Returns:
        The response body as text.

    """
    code, _, body = model.check_reply(f"/check/{name}.json")
    assert code == HTTPStatus.OK
    return body.decode("utf-8")


def test_letters_route_carries_the_text_the_command_prints(tmp_path: Path) -> None:
    """One implementation: the route's text is letters.report over the same fleet."""
    _fleet(tmp_path)
    model = Model(tmp_path)
    model.refresh()
    lines = report(tmp_path, {"alpha", "beta"})[0]
    assert lines, "the misdelivered letter is reported"
    assert json.dumps("\n".join(lines))[1:-1] in _said(model, "letters")


def test_fold_route_adds_the_plan_the_command_prints(tmp_path: Path) -> None:
    """The fold report lists the `--add` for the orphan and the `cp` for the redelivery."""
    _fleet(tmp_path)
    model = Model(tmp_path)
    model.refresh()
    text = _said(model, "fold")
    assert "--add" in text
    assert "cp " in text
    assert "inbox/2026-10-22-hello.md" in text
