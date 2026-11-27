# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2552: a superseded retro leaves the judged set through a graph edge, so the cache sees it.

The sustain and handoff-probe clauses once matched the superseded retro by the TEXT of an IRI
(STRENDS) against a literal `supersedes`. No edge linked the superseder to the retro it retired, so
the incremental SHACL run (nemik.shaclinc, which re-judges only the neighbourhood of a changed
triple) never reached the retro again: a verdict cached before the superseder existed outlived it
(nemik:R22 and nemik:R497, 2026-11-26: a fresh run said clear, the cached one said refused). These
tests plant that pair for both clauses and check the join itself, not a string.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from rdflib import RDF, Graph
from rdflib.namespace import SH

from nemik.adapter import BASE, NEMIK, queue_graph
from nemik.check import shapes
from nemik.shaclinc import findings
from nemik.shapedepth import radius

if TYPE_CHECKING:
    from pathlib import Path

PROBE = "another operator with no self probe"
THIN = "thin: no sustain"
FILLER = 12
SUSTAIN_RADIUS = 1
PROBE_RADIUS = 2


def _retro(
    ident: str,
    *,
    supersedes: str = "",
    thin: bool = False,
    unprobed: bool = False,
) -> dict[str, object]:
    """Build a scaffold-form retro the shapes judge clean unless told otherwise.

    Args:
        ident: The retro's id.
        supersedes: The id of the retro it supersedes, or none.
        thin: Leave out the sustain, so the sustain shape refuses it.
        unprobed: Hand off to another operator with no self probe, so the probe shape refuses it.

    Returns:
        The retro record, as a queue's `retros` list holds it.

    """
    handoff: dict[str, object] = {"instrument": "mikemol-commit", "channel": "a card"}
    handoff["operator"] = "other" if unprobed else "self"
    retro: dict[str, object] = {
        "id": ident,
        "card": "W1",
        "trigger": "the gate refused a stack",
        "root": "nothing checked the registry targets with the stack's own",
        "contributing": ["a rushed submit"],
        "precommit": "run the registry targets with the stack",
        "frozen_timeline": "sha256:abc",
        "delta": "two registry targets failed that the stack's own did not run",
        "enforcement_layer": "gate",
        "recurring": True,
        "one_off": False,
        "findings": [{"certify_change": "W3 ready to done"}],
        "handoff": handoff,
    }
    if not thin:
        retro["sustain"] = ["the event-ordered wait"]
    if supersedes:
        retro["supersedes"] = supersedes
    return retro


def _graph(folder: Path, repo: str, retros: list[dict[str, object]]) -> Graph:
    """Write a repo's queue with these retros and read it as the survey does.

    Returns:
        The repo's queue graph.

    """
    folder.mkdir(parents=True, exist_ok=True)
    waypoint: dict[str, object] = {
        "symbol": "W1",
        "title": "t",
        "status": "ready",
        "blocked_on": [],
        "enables": [],
        "evidence": "",
    }
    state: dict[str, object] = {
        "version": 1,
        "project_root": str(folder),
        "counter": 1,
        "residue": [],
        "waypoints": [waypoint],
        "retros": retros,
    }
    path = folder / "paths-forward.json"
    path.write_text(json.dumps(state), encoding="utf-8")
    return queue_graph(repo, path)


def _filler(repo: str) -> list[dict[str, object]]:
    """Make retros that pass every shape, so the graph is wider than one neighbourhood.

    Returns:
        FILLER clean retros of the repo.

    """
    return [_retro(f"{repo}:R{100 + n}") for n in range(FILLER)]


def _refused(key: str, g: Graph, needle: str) -> list[str]:
    """Judge a graph and name the retros whose result carries the needle.

    Returns:
        The sorted retro ids (a handoff result names its retro).

    """
    ids: list[str] = []
    for focus, _, message in findings(key, g, shapes()):
        if needle in message:
            ids.append(str(focus).split("/retro/", 1)[1].removesuffix("/handoff"))
    return sorted(ids)


def _after_a_superseder(
    folder: Path,
    key: str,
    needle: str,
    failing: dict[str, object],
) -> tuple[list[str], list[str]]:
    """Judge a queue before R2 supersedes the failing R1, again after, and once fresh.

    Args:
        folder: A scratch folder.
        key: A cache key unique to the case.
        needle: The message text naming the shape under test.
        failing: The failing retro, a:R1.

    Returns:
        The refused ids of the incremental run (same key, after) and of a fresh run (new key).

    """
    older = _graph(folder / "x", "a", [failing, *_filler("a")])
    fixer = _retro("a:R2", supersedes="a:R1")
    newer = _graph(folder / "y", "a", [failing, fixer, *_filler("a")])
    assert _refused(key, older, needle) == ["a:R1"]
    return _refused(key, newer, needle), _refused(f"{key}-fresh", newer, needle)


def test_the_sustain_verdict_after_a_superseder_equals_a_fresh_run(
    tmp_path: Path,
) -> None:
    """MUTANT: the string clause leaves the cached thin verdict standing after R2 supersedes R1."""
    thin = _retro("a:R1", thin=True)
    incremental, fresh = _after_a_superseder(tmp_path, "incr-sustain", THIN, thin)
    assert fresh == []
    assert incremental == fresh


def test_the_probe_verdict_after_a_superseder_equals_a_fresh_run(
    tmp_path: Path,
) -> None:
    """MUTANT: the string clause leaves the cached probe verdict standing after R2 supersedes R1."""
    bad = _retro("a:R1", unprobed=True)
    incremental, fresh = _after_a_superseder(tmp_path, "incr-probe", PROBE, bad)
    assert fresh == []
    assert incremental == fresh


def test_the_supersedes_object_is_the_superseded_retros_own_node(
    tmp_path: Path,
) -> None:
    """The edge is a graph join: R2's supersedes reaches the node that holds R1's own fields."""
    retros = [_retro("a:R1", thin=True), _retro("a:R2", supersedes="a:R1")]
    g = _graph(tmp_path, "a", retros)
    pairs = [
        (str(other), str(retro))
        for other, _, retro in g.triples((None, NEMIK.supersedes, None))
        if (retro, RDF.type, NEMIK.Retro) in g
        and g.value(g.value(retro, NEMIK.handoff), NEMIK.handoffOperator) is not None
    ]
    assert pairs == [(f"{BASE}a/retro/a:R2", f"{BASE}a/retro/a:R1")]


def test_two_repos_each_holding_an_r1_are_kept_apart(tmp_path: Path) -> None:
    """Repo b's supersedes reaches only b's own R1; naming a's id from b retires nothing of a's."""
    a = _graph(tmp_path / "a", "a", [_retro("a:R1", unprobed=True)])
    b = _graph(
        tmp_path / "b",
        "b",
        [
            _retro("b:R1", unprobed=True),
            _retro("b:R2", supersedes="b:R1"),
            _retro("b:R3", supersedes="a:R1"),
        ],
    )
    merged = Graph()
    merged += a
    merged += b
    assert _refused("two-repos", merged, PROBE) == ["a:R1"]


def test_each_supersession_clause_reads_its_superseder_within_the_radius() -> None:
    """The clauses are edge patterns the walker follows: one hop for sustain, two for the probe."""
    texts = [str(t) for t in shapes().objects(None, SH.select)]
    clauses = [t for t in texts if "supersedes" in t]
    sustain = [t for t in clauses if "ns#sustain>" in t]
    probe = [t for t in clauses if "ns#handoffOperator>" in t]
    assert len(sustain) == 1
    assert len(probe) == 1
    assert radius(sustain) == SUSTAIN_RADIUS
    assert radius(probe) == PROBE_RADIUS
