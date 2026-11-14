# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W982: the retros of a queue enter the graph, so the retro shapes judge real retros.

The shapes had only ever run on fixtures: nothing read a queue's `retros` list into the graph. The
ingest (nemik.retroingest, called from nemik.adapter) reads the scaffold form, a retro that carries
a precommit, and leaves the older free form out; these tests hold the mapping, the cut-over and the
shapes' verdict on a retro that comes through a queue file.
"""

import json
from typing import TYPE_CHECKING

from rdflib import RDF, Literal, URIRef

from nemik.adapter import BASE, NEMIK, queue_graph
from nemik.check import shapes, survey
from nemik.retroingest import all_triples, in_scope, triples
from nemik.shaclinc import findings

if TYPE_CHECKING:
    from pathlib import Path

    from rdflib import Graph

VIOLATION = "http://www.w3.org/ns/shacl#Violation"


def _retro(ident: str = "nemik:R1") -> dict[str, object]:
    """Build a retro in the scaffold form, every field set.

    Returns:
        A retro the shapes judge clean.

    """
    return {
        "id": ident,
        "card": "W1",
        "trigger": "the gate refused a stack",
        "root": "nothing checked the registry targets with the stack's own",
        "contributing": ["a rushed submit", "a missing test target"],
        "precommit": "run the registry targets with the stack",
        "frozen_timeline": "sha256:abc",
        "delta": "two registry targets failed that the stack's own did not run",
        "sustain": ["the event-ordered wait"],
        "enforcement_layer": "gate",
        "recurring": True,
        "one_off": False,
        "findings": [
            {
                "finding_card": "W2",
                "finding_owner": "nemik session",
                "due": "2026-11-20",
                "finding_witness": "the registry targets run in the stack's own run",
            },
            {"certify_change": "W3 ready to done"},
        ],
        "handoff": {"instrument": "mikemol-commit", "channel": "a card", "operator": "self"},
    }


def _queue(tmp_path: Path, retros: list[dict[str, object]]) -> Path:
    """Write a queue with one waypoint and these retros.

    Returns:
        The queue file.

    """
    state: dict[str, object] = {
        "version": 1,
        "project_root": str(tmp_path),
        "counter": 1,
        "residue": [],
        "waypoints": [
            {
                "symbol": "W1",
                "title": "t",
                "status": "ready",
                "blocked_on": [],
                "enables": [],
                "evidence": "",
            }
        ],
        "retros": retros,
    }
    path = tmp_path / "paths-forward.json"
    path.write_text(json.dumps(state), encoding="utf-8")
    return path


def _messages(key: str, g: Graph) -> list[tuple[str, str]]:
    """Judge a graph against the shapes.

    Returns:
        (severity, message) for each finding.

    """
    return [(str(sev), msg) for _, sev, msg in findings(key, g, shapes())]


def test_only_a_retro_with_a_precommit_is_in_scope() -> None:
    """The scaffold form carries a precommit; the older free form does not."""
    assert in_scope({"precommit": "run it first"})
    assert not in_scope({"id": "nemik:R1", "trigger": "t", "root": "r"})
    assert not in_scope({"precommit": ""})
    assert not in_scope({"precommit": "   "})
    assert not in_scope({"precommit": 3})


def test_a_retro_reads_as_its_class_text_lists_and_flags() -> None:
    """Every documented field reaches a triple, booleans as the text the G9 shape reads."""
    got = {(p, o) for s, p, o, _ in triples(_retro()) if s == "retro/nemik:R1"}
    assert ("a", "Retro") in got
    assert ("trigger", "the gate refused a stack") in got
    assert ("frozenTimeline", "sha256:abc") in got
    assert ("enforcementLayer", "gate") in got
    assert ("contributing", "a rushed submit") in got
    assert ("sustain", "the event-ordered wait") in got
    assert ("recurring", "true") in got


def test_a_false_flag_is_absent_and_a_string_is_not_a_flag() -> None:
    """Only the JSON boolean true makes the flag: false and the text 'true' do not."""
    retro = _retro()
    retro["recurring"] = "true"
    got = {p for _, p, _, _ in triples(retro)}
    assert "recurring" not in got
    assert "oneOff" not in got


def test_findings_and_a_handoff_are_their_own_nodes_linked_from_the_retro() -> None:
    """One RetroFinding per finding and a RetroHandoff for the handoff, each linked by a node."""
    rows = triples(_retro())
    linked = [(p, o) for s, p, o, node in rows if s == "retro/nemik:R1" and node]
    assert ("finding", "retro/nemik:R1/finding/0") in linked
    assert ("finding", "retro/nemik:R1/finding/1") in linked
    assert ("handoff", "retro/nemik:R1/handoff") in linked
    first = {(p, o) for s, p, o, _ in rows if s == "retro/nemik:R1/finding/0"}
    assert ("findingCard", "W2") in first
    assert ("due", "2026-11-20") in first
    second = {(p, o) for s, p, o, _ in rows if s == "retro/nemik:R1/finding/1"}
    assert ("certifyChange", "W3 ready to done") in second
    hand = {(p, o) for s, p, o, _ in rows if s == "retro/nemik:R1/handoff"}
    assert ("handoffOperator", "self") in hand


def test_a_retro_with_no_id_reads_as_nothing() -> None:
    """Nothing to name the node by, so nothing is emitted."""
    assert triples({"precommit": "x", "trigger": "t"}) == []


def test_the_cut_over_leaves_the_older_retros_out() -> None:
    """A list of one scaffold retro and two older ones reads only the scaffold one."""
    older: dict[str, object] = {"id": "nemik:R0", "card": "W0", "trigger": "t", "root": "r"}
    listed: list[dict[str, object]] = [older, _retro("nemik:R1"), {**older, "id": "nemik:R2"}]
    rows = all_triples(listed)
    subjects = {s for s, _, _, _ in rows if "/" in s and s.count("/") == 1}
    assert subjects == {"retro/nemik:R1"}
    assert all_triples("not a list") == []


def test_a_queue_with_retros_puts_the_scaffold_ones_in_the_graph(tmp_path: Path) -> None:
    """The adapter reads the retros list: a scaffold retro is a nemik:Retro node, an old one not."""
    older: dict[str, object] = {"id": "nemik:R0", "card": "W0", "trigger": "t", "root": "r"}
    g = queue_graph("a", _queue(tmp_path, [older, _retro("nemik:R1")]))
    retros = set(g.subjects(RDF.type, NEMIK.Retro))
    assert retros == {URIRef(f"{BASE}a/retro/nemik:R1")}
    assert (URIRef(f"{BASE}a/retro/nemik:R1"), NEMIK.recurring, Literal("true")) in g


def test_a_clean_retro_through_a_queue_draws_no_violation(tmp_path: Path) -> None:
    """The shapes judge the retro that came through a queue file, and a complete one passes."""
    g = queue_graph("a", _queue(tmp_path, [_retro()]))
    violations = [m for sev, m in _messages("retro-clean", g) if sev == VIOLATION]
    assert violations == []


def test_a_retro_that_breaks_a_shape_is_refused_through_a_queue(tmp_path: Path) -> None:
    """MUTANT: an unknown enforcement layer reaches the shape and is refused, not vacuously."""
    bad = _retro()
    bad["enforcement_layer"] = "banana"
    g = queue_graph("a", _queue(tmp_path, [bad]))
    said = [m for sev, m in _messages("retro-bad", g) if sev == VIOLATION]
    assert any("enforcement layer must be one of" in m for m in said)


def test_a_retro_that_equals_trigger_and_root_is_refused(tmp_path: Path) -> None:
    """The G3 shape reads a real retro: a root equal to the trigger is a Violation."""
    bad = _retro()
    bad["root"] = bad["trigger"]
    g = queue_graph("a", _queue(tmp_path, [bad]))
    said = [m for sev, m in _messages("retro-root", g) if sev == VIOLATION]
    assert any("the root equals the trigger" in m for m in said)


def test_a_retro_finding_is_reported_by_the_survey_under_its_repo(tmp_path: Path) -> None:
    """The survey files a finding under the repo in its focus node, so a retro's must carry it.

    A node under `urn:nemik:retro/...` is filed under a repo called "retro" and reported nowhere,
    which is how the first version of this ingest changed nothing in nemik-check.
    """
    bad = _retro()
    bad["enforcement_layer"] = "banana"
    queue = _queue(tmp_path, [bad])
    root = tmp_path / "root"
    (root / "a" / ".claude").mkdir(parents=True)
    (root / "a" / ".claude" / "paths-forward.json").write_text(
        queue.read_text(encoding="utf-8"), encoding="utf-8"
    )
    reported = {name: list(found) for name, _, found in survey(root, check=True)}
    mine = reported["a"]
    assert any(
        sev == "Violation" and focus.startswith("retro/") and "enforcement layer" in msg
        for sev, focus, msg in mine
    )
    assert "retro" not in reported


def _handed_to_another(probe: str) -> dict[str, object]:
    """Build a scaffold retro whose handoff goes to another operator.

    Args:
        probe: The handoff's self_probe, or an empty text for none.

    Returns:
        The retro.

    """
    retro = _retro()
    handoff: dict[str, object] = {
        "instrument": "a letter",
        "channel": "mtools inbox",
        "operator": "other",
    }
    if probe:
        handoff["self_probe"] = probe
    retro["handoff"] = handoff
    return retro


def test_a_handoff_to_another_operator_needs_its_self_probe_recorded(tmp_path: Path) -> None:
    """MUTANT: the same handoff is refused without a self probe and passes with one executed."""
    without = queue_graph("a", _queue(tmp_path, [_handed_to_another("")]))
    said = [m for sev, m in _messages("retro-no-probe", without) if sev == VIOLATION]
    assert any("no self probe recorded executed-and-failed" in m for m in said)
    other = tmp_path / "other"
    other.mkdir()
    probed = queue_graph("a", _queue(other, [_handed_to_another("executed-and-failed")]))
    kept = [m for sev, m in _messages("retro-probe", probed) if sev == VIOLATION]
    assert not any("self probe" in m for m in kept)
