# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2357: historic retro handoffs read as Info by the result's identity, never its text."""

import re
from pathlib import Path

import pytest
from rdflib import RDF, Graph, Literal, URIRef

from nemik.adapter import BASE, NEMIK
from nemik.check import (
    demoted,
    parse_retro_baseline,
    repo_rows,
    retro_baseline,
    shapes,
)
from nemik.retrobaseline import (
    HISTORIC,
    PROBE_SHAPE,
    STALE,
    demote,
    is_probe,
    retro_id,
    shrink,
    stale,
    violators,
)
from nemik.shaclinc import identified

ROOT = Path(__file__).resolve().parents[1]
OTHER_SHAPE = "https://github.com/mikemol/nemik/ns#RetroHandoffShape"
HANDOFF = "retro/gcalculus:R1/handoff"
NEW = "retro/gcalculus:R2/handoff"
SAID = "the probe shape's message, whatever it says"
ID = re.compile(r"[a-z0-9-]+:R\d+")


def test_a_handoff_symbol_names_its_retro() -> None:
    """The id is the repo-qualified retro between `retro/` and `/handoff`."""
    assert retro_id(HANDOFF) == "gcalculus:R1"


@pytest.mark.parametrize(
    "symbol", ["retro/gcalculus:R1/finding/0", "W12", "retro//handoff", "--"]
)
def test_a_focus_that_is_no_retro_handoff_is_refused(symbol: str) -> None:
    """No empty-text sentinel: the probe shape targets handoffs, so another focus is a defect."""
    with pytest.raises(ValueError, match="not a retro handoff's focus"):
        retro_id(symbol)


def test_a_probe_result_on_a_focus_that_is_no_handoff_is_refused() -> None:
    """A probe-shape Violation whose focus is not a handoff stops the read, never slips past."""
    rows = [("Violation", "W12", SAID, PROBE_SHAPE)]
    with pytest.raises(ValueError, match="not a retro handoff's focus"):
        demote(rows, {"gcalculus:R1"})


@pytest.mark.parametrize(
    ("row", "probe"),
    [
        (("Violation", HANDOFF, SAID, PROBE_SHAPE), True),
        (("Violation", HANDOFF, SAID, OTHER_SHAPE), False),
        (("Info", HANDOFF, SAID, PROBE_SHAPE), False),
        (("Warning", "W12", SAID, PROBE_SHAPE), False),
    ],
)
def test_a_probe_is_a_violation_of_the_probe_shape(
    row: tuple[str, str, str, str], *, probe: bool
) -> None:
    """The predicate reads severity and shape, nothing else."""
    assert is_probe(row) is probe


def test_a_baselined_retro_of_the_probe_shape_reads_as_info() -> None:
    """The demotion keeps the message and says why."""
    rows = [("Violation", HANDOFF, SAID, PROBE_SHAPE)]
    assert demote(rows, {"gcalculus:R1"}) == [("Info", HANDOFF, HISTORIC + SAID)]


def test_another_shape_on_the_same_handoff_stays_a_violation() -> None:
    """The planted case github-00 asked for: same focus node, other shape, still Violation."""
    rows = [
        ("Violation", HANDOFF, SAID, PROBE_SHAPE),
        ("Violation", HANDOFF, "a missing channel", OTHER_SHAPE),
    ]
    got = demote(rows, {"gcalculus:R1"})
    assert got[1] == ("Violation", HANDOFF, "a missing channel")
    assert got[0][0] == "Info"


def test_the_message_text_is_never_what_is_matched() -> None:
    """A reworded message is still demoted, and the old text on another shape is not."""
    reworded = [("Violation", HANDOFF, "anything at all", PROBE_SHAPE)]
    assert demote(reworded, {"gcalculus:R1"})[0][0] == "Info"
    same_text = [("Violation", HANDOFF, SAID, OTHER_SHAPE)]
    assert demote(same_text, {"gcalculus:R1"})[0][0] == "Violation"


def test_an_unbaselined_retro_or_another_repos_same_number_stays_a_violation() -> None:
    """The key carries the repo, so gcalculus:R1 does not cover github:R1."""
    rows = [
        ("Violation", NEW, SAID, PROBE_SHAPE),
        ("Violation", "retro/github:R1/handoff", SAID, PROBE_SHAPE),
    ]
    assert [r[0] for r in demote(rows, {"gcalculus:R1"})] == ["Violation"] * 2


def test_the_violators_are_the_probe_shapes_violations_only() -> None:
    """Sorted and distinct; another shape's result and an Info are not violators."""
    rows = [
        ("Violation", "retro/b:R2/handoff", SAID, PROBE_SHAPE),
        ("Violation", "retro/a:R1/handoff", SAID, PROBE_SHAPE),
        ("Violation", "retro/a:R1/handoff", SAID, PROBE_SHAPE),
        ("Violation", "retro/c:R3/handoff", SAID, OTHER_SHAPE),
        ("Info", "retro/d:R4/handoff", SAID, PROBE_SHAPE),
    ]
    assert violators(rows) == ["a:R1", "b:R2"]


def test_the_baseline_only_shrinks() -> None:
    """A new violator is never added; one that stopped violating is dropped and reported."""
    assert shrink(["a:R1", "a:R2"], ["a:R1", "b:R9"]) == ["a:R1"]
    assert stale(["a:R1", "a:R2"], ["a:R1", "b:R9"]) == ["a:R2"]


def test_a_baselined_retro_that_no_longer_violates_is_said_on_its_repo() -> None:
    """A dead entry is an Info line on a surveyed repo, and nothing on a repo not surveyed."""
    rows = {"gcalculus": [("Violation", HANDOFF, SAID, PROBE_SHAPE)]}
    found = demoted(rows, ["gcalculus:R1", "gcalculus:R7", "absent:R1"])
    dead = ("Info", "retro/gcalculus:R7/handoff", f"gcalculus:R7 {STALE}")
    assert dead in found["gcalculus"]
    assert "absent" not in found


def test_a_baseline_text_reads_as_its_sorted_ids() -> None:
    """The pure parse of the file's text."""
    assert parse_retro_baseline('["b:R2", "a:R1"]') == ["a:R1", "b:R2"]
    assert parse_retro_baseline("[]") == []


def test_a_baseline_that_is_not_a_list_is_refused_not_read_as_empty() -> None:
    """A corrupt file must not demote nothing in silence: nemik-check names it instead."""
    with pytest.raises(TypeError, match="not a JSON list"):
        parse_retro_baseline('{"gcalculus:R1": 1}')


def test_a_baseline_item_that_is_not_text_is_refused() -> None:
    """Every item is a retro id's text."""
    with pytest.raises(ValueError, match="not a retro id"):
        parse_retro_baseline('["gcalculus:R1", 12]')


def _handoff(g: Graph, ident: str, **fields: str) -> None:
    repo = ident.partition(":")[0]
    node = URIRef(f"{BASE}{repo}/retro/{ident}/handoff")
    g.add((node, RDF.type, NEMIK.RetroHandoff))
    for name, value in fields.items():
        g.add((node, NEMIK[name], Literal(value)))


def test_a_new_retro_beside_a_baselined_one_still_violates_end_to_end() -> None:
    """Through SHACL: R1 is baselined, R2 is new; R1's missing channel is another shape's."""
    g = Graph()
    _handoff(g, "gcalculus:R1", handoffInstrument="i", handoffOperator="other")
    _handoff(
        g,
        "gcalculus:R2",
        handoffInstrument="i",
        handoffChannel="c",
        handoffOperator="other",
    )
    rows = repo_rows(identified("w2357", g, shapes()), ["gcalculus"])
    probes = sorted(
        sym for _, sym, _, shape in rows["gcalculus"] if shape == PROBE_SHAPE
    )
    assert probes == [HANDOFF, NEW]
    found = demoted(rows, ["gcalculus:R1"])["gcalculus"]
    assert [sev for sev, sym, _ in found if sym == NEW] == ["Violation"]
    assert sorted(sev for sev, sym, _ in found if sym == HANDOFF) == [
        "Info",
        "Violation",
    ]


def test_the_committed_baseline_is_sorted_distinct_and_well_formed() -> None:
    """The file the package ships, read the way nemik-check reads it."""
    ids = retro_baseline()
    assert ids
    assert ids == sorted(set(ids))
    assert all(ID.fullmatch(ident) for ident in ids)


def test_the_baseline_is_a_ratchet_declared_only_at_its_birth() -> None:
    """Registered in ratchets.json; rebaselines.json names it once, its birth at 296.

    The gate counts a new ratchet as a rise from 0, so its birth is declared with the operator's
    warrant. A second entry naming it would declare a later rise: the baseline only shrinks.
    """
    path = "src/nemik/data/retro-handoff-baseline.json"
    declared = (ROOT / "ratchets.json").read_text(encoding="utf-8")
    assert f'{{"path": "{path}", "kind": "baseline"}}' in declared
    rebaselines = (ROOT / "rebaselines.json").read_text(encoding="utf-8")
    named = f'"ratchet": "{path}"'
    assert rebaselines.count(named) == 1
    assert f'{named},\n   "old": 0,\n   "new": 296,' in rebaselines
