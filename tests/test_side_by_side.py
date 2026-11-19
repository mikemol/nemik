# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2018: each repo's schema-1 surfaces census, aligned by surface, no live repo read."""

import json
from typing import TYPE_CHECKING

import pytest
from side_by_side import (
    ABSENT,
    BAD_INPUT,
    Absent,
    CensusError,
    align,
    differs,
    main,
    parse,
    render,
)

if TYPE_CHECKING:
    from pathlib import Path


def _doc(repo: str, *surfaces: tuple[str, bool]) -> dict[str, object]:
    """Build a schema-1 document in which each surface carries `declared` and empty lists.

    Returns:
        The document.

    """
    return {
        "schema": 1,
        "repo": repo,
        "surfaces": [
            {
                "surface": name,
                "declared": declared,
                "changed_by": [],
                "loaded_by": [],
                "reviewed_by": [],
            }
            for name, declared in surfaces
        ],
    }


A = _doc("alpha", ("hooks", True), ("gate", True))
B = _doc("beta", ("gate", True), ("skills", False))


def test_two_documents_are_aligned_by_surface_in_order_of_first_appearance() -> None:
    """Rows are the union of the surfaces; a repo that lists a surface gets its cell."""
    repos, rows = align([parse(B, "b"), parse(A, "a")])
    assert repos == ["alpha", "beta"]
    assert [r.surface for r in rows] == ["hooks", "gate", "skills"]
    by = {r.surface: r.cells for r in rows}
    assert by["gate"][0] == by["gate"][1]
    cell = by["gate"][0]
    assert not isinstance(cell, Absent)
    assert cell["declared"] is True


def test_a_surface_a_repo_does_not_list_is_the_absent_type_not_false() -> None:
    """The cell is ABSENT, a type of its own: not None, not a dict, not a declared False."""
    _, rows = align([parse(A, "a"), parse(B, "b")])
    by = {r.surface: r.cells for r in rows}
    assert by["hooks"][1] is ABSENT
    assert by["skills"][0] is ABSENT
    declared_false = by["skills"][1]
    assert not isinstance(declared_false, Absent)
    assert declared_false["declared"] is False
    assert not isinstance(ABSENT, dict)
    assert ABSENT is not None


def test_a_row_is_marked_only_when_its_cells_are_not_all_present_and_equal() -> None:
    """The shared, equal surface is unmarked; the missing and the differing are marked."""
    c = _doc("gamma", ("gate", False))
    _, rows = align([parse(A, "a"), parse(B, "b"), parse(c, "c")])
    marked = {r.surface: differs(r) for r in rows}
    assert marked == {"hooks": True, "gate": True, "skills": True}
    d = _doc("delta", ("hooks", True), ("gate", True))
    _, same = align([parse(A, "a"), parse(d, "d")])
    assert [differs(r) for r in same] == [False, False]


def test_the_table_prints_a_dash_for_an_absent_cell_and_a_star_on_a_differing_row() -> (
    None
):
    """One line per surface under a header, a column per repo."""
    repos, rows = align([parse(A, "a"), parse(B, "b")])
    lines = render(repos, rows).splitlines()
    assert lines[0].split() == ["surface", "alpha", "beta"]
    assert lines[1].split() == ["*", "hooks", "[true,[],[],[]]", "-"]
    # the marker column is one character and two spaces wide, blank on an unmarked row
    assert [ln[3:].split()[0] for ln in lines[1:]] == ["hooks", "gate", "skills"]
    assert [ln[0] for ln in lines[1:]] == ["*", " ", "*"]


BAD = [
    ({"schema": 2, "repo": "x", "surfaces": []}, "not a schema-1"),
    ([], "not a schema-1"),
    ({"schema": 1, "surfaces": []}, "no repo name"),
    ({"schema": 1, "repo": "x"}, "no surfaces list"),
    ({"schema": 1, "repo": "x", "surfaces": [{"declared": True}]}, "no name"),
    (
        {"schema": 1, "repo": "x", "surfaces": [{"surface": "s", "declared": 1}]},
        "surface s lacks changed_by, loaded_by, reviewed_by",
    ),
]


@pytest.mark.parametrize(("doc", "fragment"), BAD)
def test_a_document_that_is_not_a_census_is_refused_with_its_source_named(
    doc: object, fragment: str
) -> None:
    """Nothing is guessed: the error says where the bad document came from and why."""
    with pytest.raises(CensusError, match=fragment) as raised:
        parse(doc, "some/where.json")
    assert str(raised.value).startswith("some/where.json:")


def test_a_surface_listed_twice_and_two_documents_for_one_repo_are_refused() -> None:
    """Both would silently drop a row, so both are errors."""
    twice = _doc("x", ("s", True), ("s", False))
    with pytest.raises(CensusError, match="listed twice"):
        parse(twice, "x.json")
    with pytest.raises(CensusError, match="same repo"):
        align([parse(A, "a1"), parse(A, "a2")])


def test_main_reads_the_files_and_prints_the_table(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The command takes one file per repo; a bad file exits 2 and says which."""
    first, second = tmp_path / "a.json", tmp_path / "b.json"
    first.write_text(json.dumps(A), encoding="utf-8")
    second.write_text(json.dumps(B), encoding="utf-8")
    assert main([str(first), str(second)]) == 0
    assert "skills" in capsys.readouterr().out
    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")
    assert main([str(first), str(bad)]) == BAD_INPUT
    assert "bad.json" in capsys.readouterr().err
