# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W438: the view's state colours, through the worst-view colour-blind distance.

mikemol.cvdcore (mtools:W1315, from el-openglo's cvd_gate) measures a colour pair's smallest
CAM02-UCS distance over a trichromat and three simulated deficiencies, and the Okabe-Ito
palette's own tightest pair is the floor. State fills are not all above it, and need not be:
every state but ready also carries a glyph (WCAG 1.4.1, nemik:W381). So the rule here is: a
pair of state colours under the floor must differ in their mark, and the count of such pairs
may not grow.
"""

from itertools import combinations

from mikemol.cvdcore import reference_floor, worst_view_dE
from pagetext import page_text

STATES = ("ready", "working", "blocked", "landed", "done", "dropped", "other")
MARKS = "const STATE_MARK = {"
DARK = "@media (prefers-color-scheme: dark)"
HEX = 6
# Pairs a theme may hold under the floor, as counted when this test was written (nemik:W438):
# light has working/other and ready/blocked, dark those two and ready/working. A new pair
# under the floor fails until it is separated or counted here on purpose.
UNDER_FLOOR = {"light": 2, "dark": 3}


def _page() -> str:
    """Read the view's page out of the package.

    Returns:
        The text of web/index.html.

    """
    return page_text()


def _themes() -> dict[str, dict[str, tuple[int, int, int]]]:
    """Read the state colours of each theme out of the page's stylesheet.

    Returns:
        {"light": {state: (r, g, b)}, "dark": {...}}.

    """
    light, _, dark = _page().partition(DARK)
    out: dict[str, dict[str, tuple[int, int, int]]] = {}
    for name, css in (("light", light), ("dark", dark)):
        found: dict[str, tuple[int, int, int]] = {}
        for state in STATES:
            token = f"--{state}: #"
            at = css.find(token)
            if at < 0:
                continue
            code = css[at + len(token) : at + len(token) + HEX]
            found[state] = (int(code[0:2], 16), int(code[2:4], 16), int(code[4:6], 16))
        out[name] = found
    return out


def _marks() -> dict[str, str]:
    """Read the glyph each state carries from the page's STATE_MARK table.

    Returns:
        {state: mark}, the mark empty for ready.

    """
    _, found, rest = _page().partition(MARKS)
    assert found, "the page's STATE_MARK table moved"
    marks: dict[str, str] = {}
    for entry in rest.partition("}")[0].split(","):
        key, _, value = entry.partition(":")
        marks[key.strip()] = value.strip().strip('"')
    return marks


def test_every_state_has_a_colour_in_both_themes() -> None:
    """The six state colours are read from the light and the dark stylesheet."""
    for name, colours in _themes().items():
        assert set(colours) == set(STATES), name


def test_every_state_has_a_mark_entry() -> None:
    """The mark table names all six states, so a missing glyph cannot pass as equal."""
    assert set(_marks()) == set(STATES)


def test_a_pair_of_state_colours_under_the_floor_differs_in_its_mark() -> None:
    """Colour alone does not carry the pair: its two states have different glyphs."""
    floor = reference_floor()[0]
    marks = _marks()
    for name, colours in _themes().items():
        for one, other in combinations(STATES, 2):
            distance, view = worst_view_dE(colours[one], colours[other])
            if distance < floor:
                assert marks[one] != marks[other], (name, one, other, view, distance)


def test_the_pairs_under_the_floor_do_not_grow() -> None:
    """Counted per theme against UNDER_FLOOR."""
    floor = reference_floor()[0]
    for name, colours in _themes().items():
        under = [
            (one, other)
            for one, other in combinations(STATES, 2)
            if worst_view_dE(colours[one], colours[other])[0] < floor
        ]
        assert len(under) <= UNDER_FLOOR[name], (name, under)
