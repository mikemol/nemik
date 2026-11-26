# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2514: a retro's sustain as one text is read, as the writer's schema accepts it."""

from nemik.retroingest import triples

SUBJECT = "retro/resumes:R1"
KEEP = "Keep: (1) the cold review; (2) the card map"
NONE_GIVEN: list[dict[str, object]] = [
    {"sustain": ""},
    {"sustain": "  "},
    {"sustain": []},
    {},
]


def _retro(fields: dict[str, object]) -> dict[str, object]:
    """Build a retro with the fields a case sets.

    Returns:
        A retro with an id and the given fields.

    """
    return {"id": "resumes:R1", **fields}


def test_a_sustain_text_is_one_sustain_item() -> None:
    """MUTANT: reading only a list drops a text and calls a retro that kept things thin."""
    assert (SUBJECT, "sustain", KEEP, False) in triples(_retro({"sustain": KEEP}))


def test_a_sustain_list_is_one_item_per_text() -> None:
    """The list form is unchanged."""
    got = triples(_retro({"sustain": ["a", "b"]}))
    assert (SUBJECT, "sustain", "a", False) in got
    assert (SUBJECT, "sustain", "b", False) in got


def test_an_empty_or_blank_sustain_is_still_none() -> None:
    """A blank text, an empty list and an absent field all leave the retro thin."""
    for fields in NONE_GIVEN:
        sustain = [t for t in triples(_retro(fields)) if t[1] == "sustain"]
        assert sustain == [], fields


def test_contributing_reads_a_text_the_same_way() -> None:
    """The other list field has the same schema, so the same reading."""
    got = triples(_retro({"contributing": "one cause"}))
    assert (SUBJECT, "contributing", "one cause", False) in got
