# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2514: the retros with zero sustain rows are a counted, shrink-only baseline."""

import json
import re
from pathlib import Path

import pytest

from nemik.check import (
    SUSTAIN_BASELINE,
    demoted,
    parse_retro_baseline,
    sustain_baseline,
)
from nemik.retrobaseline import (
    SUSTAIN_HISTORIC,
    SUSTAIN_SHAPE,
    demote_thin,
    shrink,
    stale,
    sustain_id,
    sustain_retros,
)
from nemik.tomlview import table, tables

ROOT = Path(__file__).resolve().parents[1]
HANDOFF_SHAPE = "https://github.com/mikemol/nemik/ns#RetroHandoffProbeShape"
SAID = "thin: no sustain. whatever it says"
ID = re.compile(r"[a-z0-9-]+:R\d+")
PATH = "src/nemik/data/retro-sustain-baseline.json"


def _decoded(name: str) -> object:
    """Read a committed JSON file as an opaque value.

    Returns:
        What json.loads read, typed as object.

    """
    loaded: object = json.loads((ROOT / name).read_text(encoding="utf-8"))
    return loaded


def _thin(retro: str) -> tuple[str, str, str, str]:
    """Build a sustain-shape Violation on a retro, as nemik.check files it.

    Returns:
        The row: severity, focus symbol, message and source shape.

    """
    return ("Violation", f"retro/{retro}", SAID, SUSTAIN_SHAPE)


def test_a_retro_symbol_names_its_id() -> None:
    """The focus of the sustain shape is the retro, `retro/<repo>:R<n>`."""
    assert sustain_id("retro/github:R12") == "github:R12"


@pytest.mark.parametrize(
    "symbol", ["retro/", "W12", "retro/github:R1/handoff", "--", "retros/a:R1"]
)
def test_a_focus_that_is_no_retro_is_refused(symbol: str) -> None:
    """The shape targets retros, so another focus is a defect, never a result to read past."""
    with pytest.raises(ValueError, match="not a retro's focus"):
        sustain_id(symbol)


def test_the_thin_retros_are_the_sustain_shapes_results_at_any_severity() -> None:
    """Sorted and distinct; another shape's result on the same retro is not one."""
    rows = [
        ("Info", "retro/b:R2", SAID, SUSTAIN_SHAPE),
        ("Warning", "retro/a:R1", SAID, SUSTAIN_SHAPE),
        ("Info", "retro/a:R1", SAID, SUSTAIN_SHAPE),
        ("Violation", "retro/c:R3/handoff", SAID, HANDOFF_SHAPE),
    ]
    assert sustain_retros(rows) == ["a:R1", "b:R2"]


def test_the_message_text_is_never_what_is_matched() -> None:
    """A reworded message from the shape still counts; the old text from another shape does not."""
    reworded = [("Info", "retro/a:R1", "anything", SUSTAIN_SHAPE)]
    other = [("Info", "retro/a:R1", SAID, HANDOFF_SHAPE)]
    assert sustain_retros(reworded) == ["a:R1"]
    assert sustain_retros(other) == []


def test_the_baseline_only_shrinks() -> None:
    """A newly thin retro is never added; one that gained sustain rows is dropped and reported."""
    assert shrink(["a:R1", "a:R2"], ["a:R1", "b:R9"]) == ["a:R1"]
    assert stale(["a:R1", "a:R2"], ["a:R1", "b:R9"]) == ["a:R2"]


def test_a_refusal_names_the_sustain_file_not_the_handoff_one() -> None:
    """A corrupt file is named by its own name."""
    with pytest.raises(TypeError, match=SUSTAIN_BASELINE):
        parse_retro_baseline("{}", SUSTAIN_BASELINE)
    with pytest.raises(ValueError, match=SUSTAIN_BASELINE):
        parse_retro_baseline("[1]", SUSTAIN_BASELINE)
    text = '["b:R2", "a:R1"]'
    assert parse_retro_baseline(text, SUSTAIN_BASELINE) == ["a:R1", "b:R2"]


def test_the_committed_baseline_is_sorted_distinct_and_well_formed() -> None:
    """The file the package ships, read the way nemik-check reads it."""
    ids = sustain_baseline()
    assert ids
    assert ids == sorted(set(ids))
    assert all(ID.fullmatch(ident) for ident in ids)


def test_the_baseline_is_a_registered_ratchet_declared_only_at_its_birth() -> None:
    """Registered in ratchets.json; rebaselines.json names it once, its birth at the seed's count.

    The gate counts a new ratchet as a rise from 0, so its birth is declared with the operator's
    warrant (host 695f3e0a line 225627). A second entry naming it would declare a later rise.
    Both files are read as JSON, so a reformat cannot turn this red.
    """
    registered = tables(table(_decoded("ratchets.json")).get("ratchets"))
    ours = [row for row in registered if row.get("path") == PATH]
    assert [row.get("kind") for row in ours] == ["baseline"]
    declared = tables(table(_decoded("rebaselines.json")).get("rebaselines"))
    births = [row for row in declared if row.get("ratchet") == PATH]
    assert len(births) == 1
    assert births[0].get("old") == 0
    assert births[0].get("new") == len(sustain_baseline())


SEED = {
    "github:R242",
    "github:R244",
    "github:R253",
    "github:R254",
    "github:R255",
    "luthen-observability:R5",
    "luthen-observability:R6",
    "luthen-observability:R7",
    "luthen-observability:R8",
}


def test_the_baseline_holds_only_the_nine_it_was_born_with() -> None:
    """Nothing joins after birth: the shape is a Violation, so a new thin retro is not baselined.

    The nine are the count measured at the land (six thin when the 268 was measured, three written
    after the warrant). A supersession may shrink the file, never grow it past these.
    """
    assert set(sustain_baseline()) <= SEED


def test_a_thin_retro_outside_the_baseline_keeps_its_violation() -> None:
    """MUTANT: demoting every thin retro would make a retro thin tomorrow read as Info."""
    found = demote_thin([_thin("a:R1"), _thin("a:R2")], {"a:R1"})
    assert found[0][0] == "Info"
    assert found[0][2].startswith(SUSTAIN_HISTORIC)
    assert found[1] == _thin("a:R2")


def test_a_baselined_retro_is_demoted_by_identity_not_message() -> None:
    """Another shape's result on a baselined retro keeps its severity."""
    other = ("Violation", "retro/a:R1/handoff", "other", HANDOFF_SHAPE)
    assert demote_thin([other], {"a:R1"}) == [other]


def test_demoted_files_a_baselined_retro_that_is_no_longer_thin_as_info() -> None:
    """A baseline cannot hold a dead entry silently; a retro still thin does not say so."""
    found = demoted({"a": [_thin("a:R1")], "b": []}, [], ["a:R1", "b:R7"])
    assert [row[0] for row in found["a"]] == ["Info"]
    assert len(found["b"]) == 1
    severity, symbol, message = found["b"][0]
    assert (severity, symbol) == ("Info", "retro/b:R7")
    assert "no longer thin" in message


def test_demoted_leaves_a_new_thin_retro_a_violation_with_a_baseline_given() -> None:
    """The check as wired: a thin retro not in the baseline is a Violation on its repo."""
    found = demoted({"a": [_thin("a:R2")]}, [], ["a:R1"])
    assert ("Violation", "retro/a:R2", SAID) in found["a"]
