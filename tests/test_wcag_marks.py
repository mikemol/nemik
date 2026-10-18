# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W659: WCAG 1.4.1: the card states are not told apart by colour alone."""

from importlib.resources import files

from nemik.wcagfacts import marks
from nemik.wcagjudge import judge

TOKENS = ":root { --bg: #ffffff; --ink: #000000; }"
CRITERION = "1.4.1"
TABLE = 'const STATE_MARK = { ready: "", working: "▸ ", blocked: "‖ " };'
RULE = """{ selector: 'node[state = "unclaimed"]', style: { "border-style": "dashed" } },
{ selector: 'node[minted_during = "interrupt"]', style: { shape: "diamond" } },"""


def _unmarked(page: str) -> list[str]:
    """Judge a page and name the states reported under 1.4.1.

    Args:
        page: The page's text.

    Returns:
        The states of the 1.4.1 violations.

    """
    found = judge(TOKENS + "\n" + page)["violations"]
    return sorted(str(v["state"]) for v in found if v.get("criterion") == CRITERION)


def test_facts_name_each_states_non_colour_marks() -> None:
    """A glyph, a border style and a shape are read; a state with none is listed empty."""
    found = marks(TABLE + RULE)
    assert found["working"] == ["glyph"]
    assert found["unclaimed"] == ["border-style"]
    assert found["interrupt"] == ["shape"]
    assert found["ready"] == []


def test_one_unmarked_state_is_the_baseline() -> None:
    """Every state but ready is marked: ready is the one the others differ from."""
    glyphs = 'working: "a", blocked: "b", done: "c", dropped: "d", other: "e"'
    page = "const STATE_MARK = { " + glyphs + " };\n" + RULE
    assert _unmarked(page) == []


def test_two_unmarked_states_differ_by_colour_alone() -> None:
    """Ready and other both carry nothing, so each is reported."""
    assert _unmarked(TABLE + RULE) == ["done", "dropped", "other", "ready"]


def test_the_real_page_judged() -> None:
    """index.html: only ready, the baseline the marked states differ from, has no mark.

    other (a state outside the six, the legend's fifth colour) carries "* " (nemik:W661).
    """
    html = files("nemik").joinpath("web/index.html").read_text(encoding="utf-8")
    assert _unmarked(html) == []
    assert marks(html)["other"] == ["glyph"]


def test_a_page_with_no_state_table_has_no_states_to_judge() -> None:
    """A stylesheet alone draws no card states, so 1.4.1 has nothing to report."""
    assert marks("body { color: red; }") == {}
    assert _unmarked("body { color: red; }") == []
