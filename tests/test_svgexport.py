# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W900: the SVG the PDF is made from draws what the canvas draws, in the page's colours.

The oracle is the page's accessibility chain, not a look at a picture: every card label keeps the
4.5:1 contrast against its fill on the canvas (WCAG 1.4.3, unclaimed cards too, W903, measured
with wcagfacts.luminance), no visible card or edge is dropped, and every dashed wait line keeps
its dash (its ruler-sequence pattern is its identity, nemik:W388).
"""

import re

import webpage
from playwright.sync_api import sync_playwright

from nemik.pdf import SVG_EXPORT
from nemik.wcagfacts import luminance

MIN_CONTRAST = 4.5

# what the canvas has drawn, and what the SVG says, both read from the page
FACTS = """() => {
  const shown = cy.elements().filter(x => x.style('display') !== 'none');
  const doc = new DOMParser().parseFromString(graphSvg(cy), 'image/svg+xml');
  const bg = getComputedStyle(document.body).backgroundColor;
  const governed = n => !n.isParent() && n.style('label');
  return {
    bg,
    labelled: shown.nodes().filter(n => n.style('label')).length,
    edges: shown.edges().length,
    dashed: shown.edges().filter(e => e.style('line-style') === 'dashed').length,
    texts: doc.querySelectorAll('text:not(#legend *)').length,
    legend: [...doc.querySelectorAll('#legend text')].map(t => t.textContent),
    paths: doc.querySelectorAll('path').length,
    dashedPaths: doc.querySelectorAll('path[stroke-dasharray]').length,
    images: doc.querySelectorAll('image').length,
    cards: shown.nodes().filter(governed).map(n => ({
      ink: n.style('color'), fill: n.style('background-color'),
      alpha: n.numericStyle('background-opacity'),
    })),
  };
}"""

RGB = re.compile(r"rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)")


def _channels(colour: str) -> list[int]:
    """Read a computed `rgb(r, g, b)` as three 0 to 255 channels.

    Returns:
        The red, green and blue channels.

    """
    found = RGB.match(colour)
    assert found, colour
    return [round(float(c)) for c in found.groups()]


def _lum(channels: list[int]) -> float:
    """Measure a colour's WCAG relative luminance through wcagfacts.

    Returns:
        The relative luminance.

    """
    return luminance("#" + "".join(f"{c:02x}" for c in channels))


def _contrast(ink: str, fill: str, alpha: float, bg: str) -> float:
    """Measure the WCAG contrast of a label over its fill blended onto the page.

    Returns:
        The ratio, 1 to 21.

    """
    blended = [
        round(alpha * f + (1 - alpha) * b)
        for f, b in zip(_channels(fill), _channels(bg), strict=True)
    ]
    light, dark = sorted([_lum(_channels(ink)), _lum(blended)], reverse=True)
    return (light + 0.05) / (dark + 0.05)


def _count(facts: dict[object, object], key: str) -> int:
    """Read one counted fact.

    Returns:
        The number the page reported.

    """
    value = facts.get(key)
    assert isinstance(value, int), key
    return value


def _weak(facts: dict[object, object]) -> list[str]:
    """List the labelInk-governed cards whose label is under the bar.

    Returns:
        Each such card as text.

    """
    cards = facts.get("cards")
    assert isinstance(cards, list)
    bg = str(facts.get("bg"))
    return [
        str(card)
        for card in cards
        if isinstance(card, dict)
        and _contrast(
            str(card.get("ink")),
            str(card.get("fill")),
            float(card.get("alpha", 1)),
            bg,
        )
        < MIN_CONTRAST
    ]


def test_the_svg_keeps_the_canvas_cards_edges_dashes_and_contrast() -> None:
    """Nothing visible is dropped, no picture is embedded, and the labels stay legible."""
    with webpage.served() as url, sync_playwright() as p:
        # nemik:W846: launched_page names the requests that failed if the page breaks on load
        browser, page = webpage.launched_page(p, url)
        try:
            page.add_script_tag(path=str(SVG_EXPORT))
            facts: object = page.evaluate(FACTS)
        finally:
            browser.close()
    assert isinstance(facts, dict)
    assert _count(facts, "texts") == _count(facts, "labelled")
    assert _count(facts, "paths") == _count(facts, "edges")
    assert _count(facts, "dashedPaths") == _count(facts, "dashed")
    assert _count(facts, "images") == 0
    # nemik:W1251: the printed graph carries its own key, one entry for every card state
    legend = facts.get("legend")
    assert isinstance(legend, list)
    states = (
        "ready",
        "working",
        "blocked",
        "landed",
        "done",
        "dropped",
        "unclaimed",
        "other",
    )
    for state in states:
        assert any(state in str(entry) for entry in legend), state
    weak = _weak(facts)
    assert not weak, f"{len(weak)} labels under {MIN_CONTRAST}:1: {weak[:3]}"
