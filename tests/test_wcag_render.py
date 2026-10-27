# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W664, W667: WCAG facts read off the rendered page, judged by the Rego policy.

Contrast, focus and marks (W646, W658, W659) are read from the page's source. What a browser
lays out and computes is only known once the page runs, so a browser dumps each control's box
and its accessible name and data/wcag.rego judges 2.5.8 Target Size (Minimum: 24 by 24 CSS
pixels, or a 24 px circle that meets no other target) and 4.1.2 and 2.5.3 (a control has a
name, and the name contains the text it shows).
"""

import webpage

from nemik.wcagjudge import Row, judge_names, judge_order, judge_targets


def test_tab_goes_down_and_across_a_line_not_up_or_back() -> None:
    """A step to the next control may go right or down; up a line or left along one fails."""
    row = [_box("a", 0, 0, 30, 24), _box("b", 40, 0, 30, 24), _box("c", 0, 40, 30, 24)]
    assert not judge_order(row)
    up = judge_order([_box("low", 0, 40, 30, 24), _box("high", 0, 0, 30, 24)])
    assert [(str(f["from"]), str(f["to"])) for f in up] == [("low", "high")]
    back = judge_order([_box("right", 40, 0, 30, 24), _box("left", 0, 0, 30, 24)])
    assert [(str(f["from"]), str(f["to"])) for f in back] == [("right", "left")]


def test_tab_visits_the_pages_controls_in_reading_order() -> None:
    """2.4.3 over the controls on screen, in document order (the order Tab visits them).

    A control scrolled out of its list is left out: its box lies outside the list, and says
    nothing about where Tab goes next.
    """
    shown = [t for t in _page_rows(TARGETS) if not t["clipped"]]
    assert len(shown) > MIN_TOOLBAR
    assert not judge_order(shown)


CONTROLS = (
    "button, a[href], input, select, summary, [role=button], "
    '[tabindex]:not([tabindex="-1"])'
)

# a checkbox is activated through its label, so its target is the control and its labels together
TARGETS = (
    """() => [...document.querySelectorAll('"""
    + CONTROLS
    + """')]
  .filter(e => e.getClientRects().length)
  .map(e => {
    const boxes = [e, ...(e.labels ? [...e.labels] : [])].map(n => n.getBoundingClientRect());
    const x1 = Math.min(...boxes.map(b => b.left)), y1 = Math.min(...boxes.map(b => b.top));
    const x2 = Math.max(...boxes.map(b => b.right)), y2 = Math.max(...boxes.map(b => b.bottom));
    // scrolled out of a clipping ancestor: its box says nothing about where Tab leads
    const clipped = (() => { const b = e.getBoundingClientRect();
      for (let p = e.parentElement; p; p = p.parentElement) {
        const o = getComputedStyle(p).overflowY, r = p.getBoundingClientRect();
        if (['auto', 'scroll', 'hidden'].includes(o) && (b.bottom > r.bottom || b.top < r.top))
          return true; }
      return false; })();
    return { clipped, name: e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') +
                   (e.textContent ? ' ' + e.textContent.trim().slice(0, 24) : ''),
             x: Math.round(x1 * 10) / 10, y: Math.round(y1 * 10) / 10 + window.scrollY,
             w: Math.round((x2 - x1) * 10) / 10, h: Math.round((y2 - y1) * 10) / 10 }; })"""
)

# The accessible name as a browser computes it, approximated: aria-labelledby, aria-label, the
# control's labels, its text, then title. The visible text is what it shows, minus aria-hidden
# parts, as letters and digits only (a glyph is decoration, not a label).
NAMES = (
    """() => [...document.querySelectorAll('"""
    + CONTROLS
    + """')]
  .filter(e => e.getClientRects().length)
  .map(e => {
    const text = n => (n.textContent || '').replace(/\\s+/g, ' ').trim();
    const shown = n => { const c = n.cloneNode(true);
      c.querySelectorAll('[aria-hidden=true]').forEach(h => h.remove());
      return text(c); };
    const by = (e.getAttribute('aria-labelledby') || '').split(' ').filter(Boolean)
      .map(id => document.getElementById(id)).filter(Boolean).map(text).join(' ');
    const labels = e.labels ? [...e.labels].map(text).join(' ') : '';
    const plain = s => s.replace(/[^\\p{L}\\p{N}]+/gu, ' ').trim();
    const accessible = plain(by || e.getAttribute('aria-label') || labels || shown(e) ||
      e.getAttribute('title') || '');
    const visible = plain(shown(e));
    const id = e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') + ' ' + visible.slice(0, 24);
    return { target: id, accessible, visible: e.tagName === 'INPUT' ? '' : visible }; })"""
)

# one page load per script: the tests read the same rows, and a load starts a server and a browser
SEEN: dict[str, list[Row]] = {}
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


def _row(target: str, accessible: str, visible: str) -> Row:
    """Build one name row.

    Args:
        target: What the control is.
        accessible: Its computed accessible name.
        visible: The letters and digits it shows.

    Returns:
        The row as the policy reads it.

    """
    return {"target": target, "accessible": accessible, "visible": visible}


def test_a_control_with_a_name_that_holds_its_text_passes() -> None:
    """The name may say more than the label shows, never less."""
    rows = [_row("b", "save the file", "save"), _row("icon", "close", "")]
    assert not judge_names(rows)


def test_a_control_with_no_name_fails_4_1_2() -> None:
    """An empty or blank name leaves a screen reader nothing to say."""
    found = judge_names([_row("empty", "", ""), _row("blank", "  ", "")])
    assert sorted(str(f["target"]) for f in found) == ["blank", "empty"]
    assert all(f["criterion"] == "4.1.2" for f in found)


def test_a_name_that_leaves_out_the_shown_text_fails_2_5_3() -> None:
    """Speech control says what it sees: a button showing Save must answer to Save."""
    found = judge_names([_row("b", "store the document", "Save")])
    assert [(str(f["target"]), f["criterion"]) for f in found] == [("b", "2.5.3")]


def _page_rows(script: str) -> list[Row]:
    """Run a script on the real page and read the rows it returns.

    Args:
        script: A JavaScript function that returns a list of objects.

    Returns:
        The rows, as the policy reads them.

    """
    if script in SEEN:
        return SEEN[script]
    # nemik:W846: opened through the harness that lists the requests that failed or got an error
    # status, so a script lost under load names the asset instead of only popLater
    raw = webpage.evaluated(script)
    rows: list[Row] = []
    if isinstance(raw, list):
        rows = [{str(k): v for k, v in r.items()} for r in raw if isinstance(r, dict)]
    SEEN[script] = rows
    return rows


def test_the_toolbar_meets_target_size() -> None:
    """The controls above the card lists are 24 px or spaced clear of their neighbours."""
    bar = [t for t in _page_rows(TARGETS) if float(str(t["y"])) < TOOLBAR]
    assert len(bar) > MIN_TOOLBAR
    assert not judge_targets(bar)


def test_the_card_lists_meet_target_size() -> None:
    """List rows hold 24 px buttons and links (nemik:W665).

    The first rows below the toolbar stand for the lists (judging every target is quadratic in
    the policy and runs minutes).
    """
    rows = [t for t in _page_rows(TARGETS) if float(str(t["y"])) >= TOOLBAR][:ROWS]
    assert len(rows) == ROWS
    assert not judge_targets(rows)


def test_every_control_on_the_page_has_a_name_that_holds_its_text() -> None:
    """4.1.2 and 2.5.3 over every button, link, input, select and summary the page draws."""
    rows = _page_rows(NAMES)
    assert len(rows) > MIN_TOOLBAR
    assert not judge_names(rows)
