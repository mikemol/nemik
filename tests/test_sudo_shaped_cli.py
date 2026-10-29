# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1265: the Warning shape and nemik-operator --sudo-shaped for root-shaped operator acts."""

import json
from pathlib import Path

import pytest
from rdflib import RDF, Graph, Literal, URIRef
from rdflib.namespace import XSD

from nemik.adapter import NEMIK, OSLC_CM
from nemik.blocks_cli import operator_main
from nemik.check import shapes
from nemik.shaclinc import findings

SAID = "names a root-shaped command"


def _judged(key: str, blocked_on: str, *, excused: bool) -> list[str]:
    """Judge one blocked card against the shapes.

    Args:
        key: A cache key unique to the case (findings() caches by key).
        blocked_on: The card's blocked_on text.
        excused: Whether the card's evidence has an 'apply loop cannot:' line.

    Returns:
        The messages the shapes report.

    """
    g = Graph()
    card = URIRef(f"urn:test:card/{key}")
    g.add((card, RDF.type, OSLC_CM.ChangeRequest))
    g.add((card, OSLC_CM.state, NEMIK.Blocked))
    g.add((card, NEMIK.blockedOn, Literal(blocked_on)))
    if excused:
        g.add((card, NEMIK.applyLoopCannot, Literal("true", datatype=XSD.boolean)))
    return [m for _, _, m in findings(f"root-{key}", g, shapes())]


def _says(messages: list[str]) -> bool:
    """Say whether any message is the root-shaped shape's.

    Returns:
        True when one of the messages is the shape's.

    """
    return any(SAID in m for m in messages)


def test_an_act_ask_naming_sudo_is_warned() -> None:
    """The case the host retro R96 caught."""
    assert _says(_judged("sudo", "operator: act sudo install -d /srv/x", excused=False))


def test_the_apply_loop_line_clears_the_warning() -> None:
    """A card that says why the apply loop cannot carry it is not warned."""
    assert not _says(
        _judged("excused", "operator: act sudo install -d /srv/x", excused=True)
    )


def test_a_decide_ask_and_a_longer_word_are_not_warned() -> None:
    """Only an act ask, and only a whole word, counts."""
    assert not _says(
        _judged("decide", "operator: decide whether to mount it", excused=False)
    )
    assert not _says(
        _judged("longer", "operator: act review the rootless notes", excused=False)
    )


def _root(tmp_path: Path, blocked_on: str, evidence: str) -> Path:
    """Write one repo's queue under a root.

    Returns:
        The root directory holding the repo.

    """
    queue = tmp_path / "a" / ".claude"
    queue.mkdir(parents=True)
    card = {
        "symbol": "W1",
        "title": "t",
        "status": "blocked",
        "blocked_on": [blocked_on],
        "blocked_kind": "human",
        "evidence": evidence,
    }
    state = {
        "version": 1,
        "project_root": str(tmp_path / "a"),
        "counter": 1,
        "residue": [],
        "waypoints": [card],
    }
    (queue / "paths-forward.json").write_text(json.dumps(state), encoding="utf-8")
    return tmp_path


def test_the_mode_exits_1_and_prints_the_flagged_ask(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A root-shaped act ask with no excuse prints and exits 1."""
    root = _root(tmp_path, "operator: act sudo install -d /srv/x", "nothing")
    with pytest.raises(SystemExit) as stopped:
        operator_main(["--sudo-shaped", "--root", str(root)])
    assert stopped.value.code == 1
    assert "a:W1" in capsys.readouterr().out


def test_the_mode_exits_0_when_the_card_is_excused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The same ask with an apply-loop line prints nothing and does not exit."""
    root = _root(
        tmp_path,
        "operator: act sudo install -d /srv/x",
        "apply loop cannot: the key is the operator's, luthen:W9",
    )
    operator_main(["--sudo-shaped", "--root", str(root)])
    assert not capsys.readouterr().out
