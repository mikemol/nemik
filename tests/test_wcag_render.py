# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W664: WCAG facts read off the rendered page, judged by the Rego policy.

Contrast, focus and marks (W646, W658, W659) are read from the page's source. A target's size
is only known once it is laid out, so a browser dumps each control's box and data/wcag.rego
judges 2.5.8 Target Size (Minimum): a pointer target is at least 24 by 24 CSS pixels, or sits
where a 24 px circle centred on it meets no other target.
"""

import os
from pathlib import Path

import pytest
import webpage
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from nemik.wcagjudge import Row, judge_targets


def _absolute(path: str) -> str:
    """Make a path absolute.

    Args:
        path: A path, possibly relative to the test's working directory.

    Returns:
        The absolute path.

    """
    return str(Path(path).resolve())


# a checkbox is activated through its label, so its target is the control and its labels together
TARGETS = """() => [...document.querySelectorAll(
    'button, a[href], input, select, summary, [role=button], [tabindex]:not([tabindex="-1"])')]
  .filter(e => e.getClientRects().length)
  .map(e => {
    const boxes = [e, ...(e.labels ? [...e.labels] : [])].map(n => n.getBoundingClientRect());
    const x1 = Math.min(...boxes.map(b => b.left)), y1 = Math.min(...boxes.map(b => b.top));
    const x2 = Math.max(...boxes.map(b => b.right)), y2 = Math.max(...boxes.map(b => b.bottom));
    return { name: e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') +
                   (e.textContent ? ' ' + e.textContent.trim().slice(0, 24) : ''),
             x: Math.round(x1 * 10) / 10, y: Math.round(y1 * 10) / 10 + window.scrollY,
             w: Math.round((x2 - x1) * 10) / 10, h: Math.round((y2 - y1) * 10) / 10 }; })"""

TOOLBAR = 150
MIN_TOOLBAR = 10
ROWS = 60


def _box(name: str, x: float, y: float, w: float, h: float) -> Row:
    """Build one target box.

    Args:
        name: What the target is.
        x: Left edge in CSS pixels.
        y: Top edge.
        w: Width.
        h: Height.

    Returns:
        The box as the policy reads it.

    """
    return {"name": name, "x": x, "y": y, "w": w, "h": h}


def test_a_large_target_passes() -> None:
    """24 by 24 meets the bar, however close its neighbours."""
    assert not judge_targets([_box("a", 0, 0, 24, 24), _box("b", 25, 0, 24, 24)])


def test_a_small_target_alone_passes_by_spacing() -> None:
    """16 by 16 with nothing within a 24 px circle's reach is allowed."""
    assert not judge_targets([_box("lone", 0, 0, 16, 16), _box("far", 100, 0, 30, 30)])


def test_a_small_target_beside_another_fails() -> None:
    """Two 16 px targets 4 px apart: their circles meet, so each is reported."""
    found = judge_targets([_box("a", 0, 0, 16, 16), _box("b", 20, 0, 16, 16)])
    assert sorted(str(f["target"]) for f in found) == ["a", "b"]
    assert all(f["criterion"] == "2.5.8" for f in found)


def test_a_small_target_within_reach_of_a_large_one_fails() -> None:
    """A 16 px target 3 px from a large target: its circle reaches the large box."""
    found = judge_targets([_box("tiny", 0, 0, 16, 16), _box("big", 19, 0, 40, 40)])
    assert [str(f["target"]) for f in found] == ["tiny"]


def _page_targets() -> list[Row]:
    """Measure the real page's pointer targets.

    Returns:
        One box per control.

    """
    exe = os.environ.get("NEMIK_CHROMIUM")
    with webpage.served() as url, sync_playwright() as p:
        try:
            browser = p.chromium.launch(executable_path=_absolute(exe) if exe else None)
        except PlaywrightError as e:
            pytest.skip(f"chromium unavailable: {e}")
        page = browser.new_page(viewport={"width": 1700, "height": 1250})
        page.goto(url)
        page.wait_for_function(webpage.CY_READY, timeout=60000)
        raw: object = page.evaluate(TARGETS)
        browser.close()
    if not isinstance(raw, list):
        return []
    return [{str(k): v for k, v in r.items()} for r in raw if isinstance(r, dict)]


def test_the_toolbar_meets_target_size() -> None:
    """The controls above the card lists are 24 px or spaced clear of their neighbours."""
    bar = [t for t in _page_targets() if float(str(t["y"])) < TOOLBAR]
    assert len(bar) > MIN_TOOLBAR
    assert not judge_targets(bar)


def test_the_card_lists_meet_target_size() -> None:
    """List rows hold 24 px buttons and links (nemik:W665).

    The first rows below the toolbar stand for the lists (judging every target is quadratic in
    the policy and runs minutes).
    """
    rows = [t for t in _page_targets() if float(str(t["y"])) >= TOOLBAR][:ROWS]
    assert len(rows) == ROWS
    assert not judge_targets(rows)
