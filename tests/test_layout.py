"""nemik:W125: the web view's layout quality, measured on a fixed fleet-shaped graph and held to
budgets, in both colour schemes.

The operator's objective (2026-09-28): minimize the 95th-percentile edge length, inside boxes and
across them, with every label inside its shape. tests/fixtures/fleet/ is the fleet's real shape with
its content removed (make_fleet.py). Metrics and screenshots are written as test outputs
(bazel: bazel-testlogs/test_layout/test.outputs/; host: the pytest tmp dir), so a layout change
is compared by reading two files, not by re-deriving a harness.
"""

import json
import os
import socket
import subprocess
import time
from pathlib import Path

import installed
import pytest

sync_api = pytest.importorskip("playwright.sync_api")

FLEET = Path(__file__).parent / "fixtures" / "fleet"

# Budgets from the fixture as generated 2026-09-28, plus ~10% slack. Tighten them when the layout
# improves; a change that needs them loosened is a regression. History (cross p95, intra p95, area):
#   W125 labels inside:            2548, 387, 14.2M px^2
#   W126 skyline packing, spacing: 2200, 370, 10.8M px^2
#   W127 fit zoom in the 1360x1200 graph pane: 0.37 (unchanged: the strict packing still wins here)
#   W118 rows reordered toward partners: 2209, 329 (cross total 86381 -> 74166, cross p50 1091 -> 761)
#   W139 measured (in-box crossings, upward cross-box edges): before W118 105, 16; now 109, 16
#   W141 fixture regenerated from the live fleet (455 -> 501 open nodes): 2381, 324, 4106x3022,
#        fit 0.328, crossings 195, upward 15. A bigger graph, not a worse layout: re-based, ~10% headroom.
# (The per-repo dagre layout these numbers measured was retired 2026-10-09: the rank forest is the
# only view, so FOREST_BUDGET below is the only budget. The history stays as residue.)
# The rank forest (W135), same rules. History (cross p95, fit zoom):
#   W135 forest, strict packing:            3654, 0.223 (2038x5352: a column on a landscape pane)
#   W127 packing may set a box beside the boxes it depends on: 2009, 0.458 (2319x2583)
#   W139 measured (in-box crossings, upward cross-box edges): strict 214, 16; loose (W127) 214, 17
#   W179 fruit class ranked as one row (W178): 2010, 0.458; in-box crossings 214 -> 310. The rise is
#        the price of a new constraint (rank order honours the fruit class), not a layout regression
#        (operator 2026-10-01); the budget is re-based on it, same ~10% headroom as before.
#   W141 regenerated fixture (501 open nodes): 2357, 0.45; crossings 190, upward 20. Re-based.
#   W381 (2026-10-12): a state glyph now begins every non-ready card's label (WCAG 1.4.1), widening
#        those labels and so the boxes' packing; upward measured 24 on the host. The price of the a11y
#        constraint, not a layout regression; upward re-based with the same ~10% headroom. (A first set
#        of glyphs missing from the gate's headless-Chrome fonts drew as wide boxes and dropped fit_zoom
#        to 0.367 there; the glyphs were changed to ones every base font has, not the budget.) With
#        those, the gate measured fit_zoom 0.407: the glyphs' real width; re-based to 0.37 with the
#        same headroom. The first view's readability is W340's 8 px floor, not this number.
FOREST_BUDGET = {
    "cross_p95": 2600,
    "fit_zoom": 0.37,
    "intra_crossings": 340,
    "cross_upward": 26,
}

METRICS = """() => {
  const unit = n => n.isChild() ? n.parent().id() : n.id();
  // nemik:W139: what W118 and W127 could worsen unseen.
  //   intra_crossings: pairs of edges in the same box whose straight segments cross (edges sharing
  //     an end are not counted: they meet, they do not cross).
  //   cross_upward: cross-box edges whose downstream end is drawn above its upstream end. An
  //     enables edge points downstream; a waits edge points waiter -> blocker, i.e. upstream.
  const shape = () => {
    const seg = e => [e.source().position(), e.target().position()];
    const turn = (a, b, c) => Math.sign((b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x));
    const meets = ([p, q], [r, s]) => turn(p, q, r) * turn(p, q, s) < 0 && turn(r, s, p) * turn(r, s, q) < 0;
    const byBox = new Map();
    let up = 0;
    cy.edges().forEach(e => { if (!e.visible()) return;
      const [a, b] = [unit(e.source()), unit(e.target())];
      if (a === b) { if (!byBox.has(a)) byBox.set(a, []); byBox.get(a).push(e); return; }
      const [hi, lo] = e.hasClass("waits") ? [e.target(), e.source()] : [e.source(), e.target()];
      if (lo.position().y < hi.position().y - 1) up++; });
    let crossings = 0;
    for (const L of byBox.values())
      for (let i = 0; i < L.length; i++) for (let j = i + 1; j < L.length; j++) {
        const [e, f] = [L[i], L[j]];
        if (e.connectedNodes().intersection(f.connectedNodes()).length) continue;
        if (meets(seg(e), seg(f))) crossings++;
      }
    return { intra_crossings: crossings, cross_upward: up };
  };
  const X = [], I = [];
  cy.edges().forEach(e => { if (!e.visible()) return;
    const p = e.source().position(), q = e.target().position();
    (unit(e.source()) === unit(e.target()) ? I : X).push(Math.hypot(p.x - q.x, p.y - q.y)); });
  const q = (L, f) => { const s = [...L].sort((a, b) => a - b); return Math.round(s[Math.min(s.length - 1, Math.floor(f * s.length))] || 0); };
  const sum = L => Math.round(L.reduce((a, b) => a + b, 0));
  const bb = cy.elements().boundingBox();
  // A label is inside its shape when its box lies within the node's own box (labels excluded).
  const outside = cy.nodes("[symbol], .actor").filter(n => n.visible()).filter(n => {
    const l = n.boundingBox({ includeNodes: false, includeLabels: true, includeOverlays: false });
    const b = n.boundingBox({ includeLabels: false, includeOverlays: false });
    return l.x1 < b.x1 - 1 || l.x2 > b.x2 + 1 || l.y1 < b.y1 - 1 || l.y2 > b.y2 + 1;
  }).map(n => n.data("label"));
  return { cross_n: X.length, cross_p50: q(X, .5), cross_p95: q(X, .95), cross_total: sum(X),
           intra_n: I.length, intra_p50: q(I, .5), intra_p95: q(I, .95), intra_total: sum(I),
           width: Math.round(bb.w), height: Math.round(bb.h), labels_outside: outside,
           ...shape(),
           // nemik:W127: the scale the first draw fits the whole graph to, in this viewport.
           fit_zoom: Math.round(1000 * Math.min(cy.width() / (bb.w + 40), cy.height() / (bb.h + 40))) / 1000 };
}"""


@pytest.fixture(scope="module")
def server():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = {**installed._bin()[1], "PYTHONHASHSEED": "0"}
    proc = subprocess.Popen(
        [*installed.script("nemik-serve"), "--root", str(FLEET), "--port", str(port)],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(100):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
            break
        except OSError:
            time.sleep(0.1)
    yield f"http://127.0.0.1:{port}/"
    proc.terminate()
    proc.wait()


NODE_OVERLAPS = """() => {
  const ns = cy.nodes("[symbol], .actor").filter(n => n.visible());
  const hit = (a, b) => a.x1 < b.x2 && b.x1 < a.x2 && a.y1 < b.y2 && b.y1 < a.y2;
  // the node body, not its halo rings (nemik:W335: bounds-expansion makes boundingBox() include them)
  const body = n => { const p = n.position(), w = n.outerWidth() / 2, h = n.outerHeight() / 2; return { x1: p.x - w, x2: p.x + w, y1: p.y - h, y2: p.y + h }; };
  const out = [];
  ns.forEach(a => ns.forEach(b => { if (a.id() < b.id() && hit(body(a), body(b))) out.push(a.id() + " x " + b.id()); }));
  return out;
}"""


def test_repo_toggles_and_salience_order(server, tmp_path) -> None:
    # nemik:W306: the repo filter is toggles (none lit = all), and "salience order" puts the flow
    # salience on a ready card's label and widens edges by their current.
    out = Path(os.environ.get("TEST_UNDECLARED_OUTPUTS_DIR") or tmp_path)
    with sync_api.sync_playwright() as p:
        exe = os.environ.get("NEMIK_CHROMIUM")
        try:
            browser = p.chromium.launch(
                executable_path=os.path.abspath(exe) if exe else None
            )
        except sync_api.Error as e:
            pytest.skip(f"chromium unavailable: {e}")
        page = browser.new_page(viewport={"width": 1700, "height": 1250})
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(server)
        page.wait_for_function(
            "() => typeof cy !== 'undefined' && cy && cy.nodes('[symbol]').length > 0",
            timeout=60000,
        )
        everything = page.evaluate("() => cy.nodes('[symbol]').length")
        repos = page.evaluate(
            "() => [...document.querySelectorAll('#repos button')].map(b => b.dataset.repo)"
        )
        page.click(f"#repos button[data-repo='{repos[0]}']")
        page.wait_for_timeout(500)
        one = page.evaluate("() => cy.nodes('[symbol]').length")
        lit = page.evaluate(
            "() => [...document.querySelectorAll('#repos button')]"
            ".filter(b => b.getAttribute('aria-pressed') === 'true').length"
        )
        page.click(f"#repos button[data-repo='{repos[0]}']")  # unlit again: everything
        page.wait_for_timeout(500)
        again = page.evaluate("() => cy.nodes('[symbol]').length")
        page.check("#bySalience")
        page.wait_for_timeout(800)
        labelled = page.evaluate(
            "() => cy.nodes('[symbol]').filter(n => n.data('label').includes(' · ')).length"
        )
        widened = page.evaluate("() => cy.edges('[current > 0]').length")
        # nemik:W322: the cards on the longest open chain carry the halo class data
        assert page.evaluate("() => cy.nodes('[?on_path]').length") > 0
        # nemik:W335: one ring per scope, a legend naming each, and a selected card's cone gets its own ring
        assert page.evaluate("() => cy.nodes('[nrings > 0]').length") > 0
        assert (
            page.evaluate(
                "() => cy.nodes().filter(n => (n.data('rings') || []).includes('view')).length"
            )
            > 0
        )
        assert (
            page.evaluate("() => document.querySelectorAll('#pathkey span').length")
            == 4
        )
        ringed = page.evaluate("() => cy.nodes('[nrings > 0]')[0].id()")
        page.evaluate(f"() => cy.getElementById('{ringed}').emit('tap')")
        page.wait_for_timeout(300)
        assert (
            page.evaluate(
                "() => cy.nodes().filter(n => (n.data('rings') || []).includes('sel')).length"
            )
            > 0
        )
        page.screenshot(path=str(out / "salience-order.png"))
        browser.close()
    assert errors == []
    assert 0 < one < everything and lit == 1 and again == everything
    assert labelled > 0 and widened > 0


def test_the_history_panel_shows_the_weekly_roll_up_when_there_is_one(
    server, tmp_path
) -> None:
    # nemik:W307: history.json exists only in a host-side static build; the panel is hidden without it.
    doc = {
        "nemik": [
            {
                "week": "2026-W41",
                "opened": 5,
                "closed": 3,
                "open": 4,
                "blocked_share": 0.5,
                "oldest_blocked_days": 2.0,
            }
        ]
    }
    with sync_api.sync_playwright() as p:
        exe = os.environ.get("NEMIK_CHROMIUM")
        try:
            browser = p.chromium.launch(
                executable_path=os.path.abspath(exe) if exe else None
            )
        except sync_api.Error as e:
            pytest.skip(f"chromium unavailable: {e}")
        page = browser.new_page(viewport={"width": 1700, "height": 1250})
        page.route(
            "**/history.json",
            lambda route: route.fulfill(
                status=200, content_type="application/json", body=json.dumps(doc)
            ),
        )
        page.goto(server)
        page.wait_for_function("() => !document.getElementById('historyBox').hidden")
        text = page.inner_text("#history")
        browser.close()
    assert "W41" in text and "+5" in text and "50% blocked" in text


LEGIBILITY = """() => {
  const ns = cy.nodes("[symbol]").filter(n => n.visible()).filter(n => {
    const p = n.renderedPosition();
    return p.x >= 0 && p.y >= 0 && p.x <= cy.width() && p.y <= cy.height();
  });
  const z = cy.zoom();
  return { label_px: 10 * z, in_view: ns.length,
    min_target_px: Math.min(...ns.map(n => Math.min(n.outerWidth(), n.outerHeight()) * z)) };
}"""


def test_rolling_up_umbrellas_hides_their_work_and_a_double_click_expands_one(
    server,
) -> None:
    # nemik:W350: with "roll up umbrellas" on, fewer cards are drawn, an umbrella counts what it
    # hides, and a double-click on it brings exactly that many back.
    with sync_api.sync_playwright() as p:
        exe = os.environ.get("NEMIK_CHROMIUM")
        try:
            browser = p.chromium.launch(
                executable_path=os.path.abspath(exe) if exe else None
            )
        except sync_api.Error as e:
            pytest.skip(f"chromium unavailable: {e}")
        page = browser.new_page(viewport={"width": 1700, "height": 1250})
        page.goto(server)
        page.wait_for_function(
            "() => typeof cy !== 'undefined' && cy && cy.nodes('[symbol]').length > 0",
            timeout=60000,
        )
        page.click("#repos button[data-repo='nemik']")
        page.wait_for_timeout(500)
        full = page.evaluate("() => cy.nodes('[symbol]').length")
        page.check("#rollup")
        page.wait_for_timeout(600)
        rolled = page.evaluate("() => cy.nodes('[symbol]').length")
        umbrella = page.evaluate(
            "() => { const u = cy.nodes('[rollup > 0]')[0]; return u ? [u.id(), u.data('rollup')] : null; }"
        )
        assert umbrella is not None
        page.evaluate(f"() => cy.getElementById('{umbrella[0]}').emit('dbltap')")
        page.wait_for_timeout(600)
        opened = page.evaluate("() => cy.nodes('[symbol]').length")
        browser.close()
    assert rolled < full
    # the umbrella's own work is back (other umbrellas may stay rolled up)
    assert opened >= rolled + 1


def test_scope_rings_carry_distinct_ruler_motifs_pinned_to_paperkits(server) -> None:
    # nemik:W382/W419: each path scope gets its own ruler-sequence motif, now shipped by the server from
    # mtools' mikemol.rulerseq (paperkit's emit_f, hosted). The family is pinned to paperkit's published
    # motifs, and the rings actually drawn use pairwise-distinct dash patterns.
    with sync_api.sync_playwright() as p:
        exe = os.environ.get("NEMIK_CHROMIUM")
        try:
            browser = p.chromium.launch(
                executable_path=os.path.abspath(exe) if exe else None
            )
        except sync_api.Error as e:
            pytest.skip(f"chromium unavailable: {e}")
        page = browser.new_page(viewport={"width": 1700, "height": 1250})
        page.goto(server)
        # the legend is drawn once the first graph (and its patterns) has loaded
        page.wait_for_selector("#pathkey line", state="attached")
        motifs = page.evaluate("() => [0, 1, 2, 3].map(rulerMotif)")
        lengths = page.evaluate("() => data.ruler.f.map(p => p.length)")
        dashes = page.evaluate("() => SCOPES.map(scopeDash)")
        generates = page.evaluate("() => typeof emitF !== 'undefined'")
        legend = page.evaluate(
            "() => [...document.querySelectorAll('#pathkey line')]"
            ".map(l => l.getAttribute('stroke-dasharray'))"
        )
        browser.close()
    assert motifs == [
        "·",
        "·--",
        "·--····",
        "·--····--------",
    ]
    # len(F(n)) == n, so each shipped pattern decodes to its index
    assert lengths == list(range(len(lengths)))
    assert not generates  # the page renders the patterns; it no longer generates them
    assert len(set(dashes)) == 4 and all(dashes)
    assert legend == dashes


FANS = """() => {
  const fans = {};
  cy.edges(".waits").forEach(e => {
    const t = e.target().id();
    (fans[t] = fans[t] || []).push([e.source().id(), e.data("fan"), e.style("line-dash-pattern")]);
  });
  return Object.values(fans).filter(f => f.length > 1);
}"""


def test_blocker_lines_into_one_card_carry_distinct_decodable_ruler_patterns(
    server,
) -> None:
    # nemik:W388: lines crowding one blocker never share a dash pattern; each pattern decodes (one dot or
    # dash per unit of the natural it encodes, len(F(n)) == n) back to its source's place in the fan.
    with sync_api.sync_playwright() as p:
        exe = os.environ.get("NEMIK_CHROMIUM")
        try:
            browser = p.chromium.launch(
                executable_path=os.path.abspath(exe) if exe else None
            )
        except sync_api.Error as e:
            pytest.skip(f"chromium unavailable: {e}")
        page = browser.new_page(viewport={"width": 1700, "height": 1250})
        page.goto(server)
        page.wait_for_function(
            "() => typeof cy !== 'undefined' && cy && cy.edges('.waits').length > 0",
            timeout=60000,
        )
        fans = page.evaluate(FANS)
        browser.close()
    assert fans, "the fixture fleet has no card with two or more wait lines"
    for fan in fans:
        patterns = [str(pat) for _, _, pat in fan]
        assert len(set(patterns)) == len(patterns), fan
        sources = sorted(src for src, _, _ in fan)
        for src, n, pat in fan:
            # decode: one on/off pair per symbol, and n is the source's place in the fan
            assert len(str(pat).split()) // 2 == n, (src, n, pat)
            assert sources.index(src) + 1 == n


CONTRAST = """() => {
  const lum = css => { const [r, g, b] = css.match(/\\d+(\\.\\d+)?/g).slice(0, 3).map(v => {
    const c = +v / 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
  const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
  return cy.nodes("[symbol], .actor").filter(n => !n.hasClass("tile") && n.data("state") !== "unclaimed")
    .map(n => [n.data("state") || n.data("lane"), +ratio(n.style("color"), n.style("background-color")).toFixed(2)]);
}"""


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_every_card_label_meets_four_and_a_half_to_one(server, scheme) -> None:
    # nemik:W384 (W380 refuted the old claim): label text on every filled card and lane chip is at
    # least 4.5:1 against its fill (WCAG 1.4.3), in both themes.
    with sync_api.sync_playwright() as p:
        exe = os.environ.get("NEMIK_CHROMIUM")
        try:
            browser = p.chromium.launch(
                executable_path=os.path.abspath(exe) if exe else None
            )
        except sync_api.Error as e:
            pytest.skip(f"chromium unavailable: {e}")
        page = browser.new_page(
            viewport={"width": 1700, "height": 1250}, color_scheme=scheme
        )
        page.goto(server)
        page.wait_for_function(
            "() => typeof cy !== 'undefined' && cy && cy.nodes('[symbol]').length > 0",
            timeout=60000,
        )
        page.check("#showDone")
        page.wait_for_timeout(600)
        pairs = page.evaluate(CONTRAST)
        browser.close()
    assert pairs
    assert {s for s, _ in pairs} >= {"ready", "blocked", "done"}
    low = sorted({(s, r) for s, r in pairs if r < 4.5})
    assert low == [], low


def test_side_panel_sections_fold_and_the_choice_survives_a_reload(server) -> None:
    # nemik:W387: each section is a <details>; the long lists start closed, and a section the viewer
    # closes stays closed after a reload.
    with sync_api.sync_playwright() as p:
        exe = os.environ.get("NEMIK_CHROMIUM")
        try:
            browser = p.chromium.launch(
                executable_path=os.path.abspath(exe) if exe else None
            )
        except sync_api.Error as e:
            pytest.skip(f"chromium unavailable: {e}")
        page = browser.new_page(viewport={"width": 1700, "height": 1250})
        page.goto(server)
        page.wait_for_selector("details.sec")
        first = page.evaluate(
            "() => Object.fromEntries([...document.querySelectorAll('details.sec')].map(d => [d.id, d.open]))"
        )
        page.click("#sec-goals > summary")
        page.wait_for_timeout(300)
        hidden = page.evaluate(
            "() => [document.getElementById('sec-goals').open,"
            " document.getElementById('goals').checkVisibility()]"
        )
        page.reload()
        page.wait_for_selector("details.sec")
        kept = page.evaluate("() => document.getElementById('sec-goals').open")
        browser.close()
    assert first["sec-weather"] is False and first["sec-findings"] is False
    assert first["sec-legend"] is True and first["sec-goals"] is True
    # closed, and its body is not rendered (Chrome hides it with content-visibility, so it keeps a box)
    assert hidden == [False, False], hidden
    assert kept is False


@pytest.mark.parametrize("scheme", ["light", "dark"])  # nemik:W434
def test_the_default_view_is_legible(server, scheme) -> None:
    # nemik:W340: the first view never shrinks a label below 8 px or a node below 12 px on screen; when
    # the whole fleet would, it shows one repo at the floor and says so, with a way to fit everything.
    with sync_api.sync_playwright() as p:
        try:
            exe = os.environ.get("NEMIK_CHROMIUM")
            browser = p.chromium.launch(
                executable_path=os.path.abspath(exe) if exe else None
            )
        except sync_api.Error as e:
            pytest.skip(f"chromium unavailable: {e}")
        page = browser.new_page(
            viewport={"width": 1700, "height": 1250}, color_scheme=scheme
        )
        page.goto(server)
        page.wait_for_function(
            "() => typeof cy !== 'undefined' && cy && cy.nodes('[symbol]').length > 0",
            timeout=60000,
        )
        page.wait_for_timeout(500)
        m = page.evaluate(LEGIBILITY)
        note = page.inner_text("#legnote")
        # nemik:W433: the live region holds text only; a control inside it is re-announced with it
        controls_in_status = page.evaluate(
            "() => document.querySelectorAll('#legnote button, #legnote a').length"
        )
        # nemik:W317: every repo chip carries its health, and a non-green one a glyph, not colour alone
        chips = page.evaluate(
            "() => [...document.querySelectorAll('#repos button')]"
            ".map(b => [b.dataset.health, b.textContent])"
        )
        browser.close()
    assert chips and {h for h, _ in chips} <= {"green", "amber", "red"}
    assert all(
        text.startswith({"amber": "▲", "red": "■"}.get(h, text[:1]))
        for h, text in chips
    )
    assert m["in_view"] > 0
    assert m["label_px"] >= 8, m
    assert m["min_target_px"] >= 12, m
    assert note == "" or "readable size" in note
    assert controls_in_status == 0


def test_every_label_glyph_exists_in_this_browsers_fonts(server) -> None:
    # nemik:W398: a glyph the browser's fonts lack draws as a placeholder box, which once widened labels
    # only under the gate's headless Chrome. Each glyph the page puts in a label must measure differently
    # from a codepoint no font has (a private-use character), in the browser the test runs in.
    with sync_api.sync_playwright() as p:
        exe = os.environ.get("NEMIK_CHROMIUM")
        try:
            browser = p.chromium.launch(
                executable_path=os.path.abspath(exe) if exe else None
            )
        except sync_api.Error as e:
            pytest.skip(f"chromium unavailable: {e}")
        page = browser.new_page()
        page.goto(server)
        page.wait_for_function("() => typeof STATE_MARK === 'object'")
        missing = page.evaluate(
            "() => { const c = document.createElement('canvas').getContext('2d');"
            " c.font = 'bold 10px sans-serif';"
            " const box = c.measureText('\\u{10FFFD}').width;"
            " const glyphs = [...Object.values(STATE_MARK), '\\u25b2', '\\u25a0']"
            "   .map(s => s.trim()).filter(Boolean);"
            " return glyphs.filter(g => Math.abs(c.measureText(g).width - box) < 0.01); }"
        )
        browser.close()
    assert missing == [], f"not in this browser's fonts: {missing}"


@pytest.mark.parametrize("scheme", ["light", "dark"])  # nemik:W434
def test_context_cards_have_a_rendered_cue_of_their_own(server, scheme) -> None:
    # nemik:W385 (W380 refuted the data-flag proof): with one repo picked, the context cards drawn from
    # other repos RENDER a double border at full opacity, and no other card renders one.
    with sync_api.sync_playwright() as p:
        exe = os.environ.get("NEMIK_CHROMIUM")
        try:
            browser = p.chromium.launch(
                executable_path=os.path.abspath(exe) if exe else None
            )
        except sync_api.Error as e:
            pytest.skip(f"chromium unavailable: {e}")
        page = browser.new_page(
            viewport={"width": 1700, "height": 1250}, color_scheme=scheme
        )
        page.goto(server)
        page.wait_for_function(
            "() => typeof cy !== 'undefined' && cy && cy.nodes('[symbol]').length > 0",
            timeout=60000,
        )
        page.click("#repos button[data-repo='nemik']")
        page.wait_for_timeout(600)
        seen = page.evaluate(
            "() => cy.nodes('[symbol]').map(n => [!!n.data('ghost'),"
            " n.style('border-style'), +n.style('opacity')])"
        )
        browser.close()
    ghosts = [s for s in seen if s[0]]
    others = [s for s in seen if not s[0]]
    assert ghosts, "no context card was drawn"
    assert all(style == "double" and opacity == 1 for _, style, opacity in ghosts)
    assert not any(style == "double" for _, style, _ in others)


@pytest.mark.parametrize("scheme", ["light", "dark"])  # nemik:W434
def test_each_card_state_differs_by_more_than_its_fill(server, scheme) -> None:
    # nemik:W381 (W380 refuted the old claim): for every pair of states drawn, the cards differ in some
    # non-colour property, here the glyph that begins the label (ready has none, the rest each their own).
    with sync_api.sync_playwright() as p:
        exe = os.environ.get("NEMIK_CHROMIUM")
        try:
            browser = p.chromium.launch(
                executable_path=os.path.abspath(exe) if exe else None
            )
        except sync_api.Error as e:
            pytest.skip(f"chromium unavailable: {e}")
        page = browser.new_page(
            viewport={"width": 1700, "height": 1250}, color_scheme=scheme
        )
        page.goto(server)
        page.wait_for_function(
            "() => typeof cy !== 'undefined' && cy && cy.nodes('[symbol]').length > 0",
            timeout=60000,
        )
        page.check("#showDone")
        page.wait_for_timeout(600)
        prefixes = page.evaluate(
            # nemik:W477: a ready card behind an open enabler is drawn as a state of its own ("~ ")
            "() => { const m = {}; cy.nodes('[symbol]').forEach(n => { const s = n.data('state')"
            " === 'ready' && n.data('behind_open') ? 'ready-behind-open' : n.data('state');"
            " if (s === 'unclaimed') return; const l = n.data('label'), sym = n.data('symbol');"
            " (m[s] = m[s] || new Set()).add(l.slice(0, l.indexOf(sym))); });"
            " return Object.fromEntries(Object.entries(m).map(([s, v]) => [s, [...v]])); }"
        )
        browser.close()
    assert {"ready", "blocked", "done"} <= set(prefixes)
    # one prefix per state, and no two states share one
    assert all(len(v) == 1 for v in prefixes.values()), prefixes
    marks = [v[0] for v in prefixes.values()]
    assert len(set(marks)) == len(marks), prefixes


USE_OF_COLOUR = """() => {
  // nemik:W429: el-openglo's use-of-colour cases (policy/use_of_colour.rego's input), measured from
  // what the page RENDERS, not from its style tables. Every meaning carries hue; a cue counts only
  // when it is rendered and tells this meaning apart from its siblings.
  const cases = [];
  const byState = {};
  cy.nodes("[symbol]").forEach(n => {
    // the state mark is the label's leading run before the first letter or digit ("" for ready,
    // "? " for an unclaimed ask, "▸ " for working, ...): a card's symbol or cite starts alphanumeric
    // nemik:W477: a ready card behind an open enabler is drawn as a state of its own ("~ ")
    const s = n.data("state") === "ready" && n.data("behind_open") ? "ready-behind-open" : n.data("state");
    const label = n.data("label") || "";
    (byState[s] = byState[s] || new Set()).add(label.match(/^[^A-Za-z0-9]*/)[0]);
  });
  const prefixes = Object.fromEntries(Object.entries(byState).map(([s, p]) => [s, [...p]]));
  for (const [s, p] of Object.entries(prefixes)) {
    const mine = p.length === 1 ? p[0] : null;
    const others = Object.entries(prefixes).filter(([t]) => t !== s).flatMap(([, q]) => q);
    const distinct = mine !== null && !others.includes(mine);
    cases.push({ id: "card-state-" + s, file: "index.html", line: 0, meaning: "card is " + s,
                 colour: [{ kind: "hue" }], cues: distinct ? [{ kind: "text" }] : [] });
  }
  const dashes = SCOPES.map(scopeDash);
  SCOPES.forEach((s, i) => {
    const own = dashes[i] && dashes.indexOf(dashes[i]) === i;
    cases.push({ id: "scope-ring-" + s.id, file: "index.html", line: 0, meaning: s.label,
                 colour: [{ kind: "hue" }], cues: own ? [{ kind: "stroke" }] : [] });
  });
  const waits = cy.edges(".waits");
  if (waits.length)
    cases.push({ id: "wait-line", file: "index.html", line: 0, meaning: "waits on its target",
                 colour: [{ kind: "hue" }],
                 cues: waits.every(e => (e.data("dash") || []).length) ? [{ kind: "stroke" }] : [] });
  return { cases, withheld: [] };
}"""


@pytest.mark.parametrize("scheme", ["light", "dark"])  # nemik:W434
def test_every_meaning_the_view_colours_has_a_second_channel(
    server, tmp_path, scheme
) -> None:
    # nemik:W429/W431: the measurement above, evaluated with el-openglo's pinned requirement
    # (W430, policy/use_of_colour.rego) by the pinned opa: no denial, and something admitted.
    import json
    import shutil

    rego = os.environ.get("NEMIK_USE_OF_COLOUR_REGO")
    opa = shutil.which(os.environ.get("NEMIK_OPA", "opa"))
    if not rego or not opa:
        pytest.skip("pinned rego or opa unavailable (run under bazel)")
    with sync_api.sync_playwright() as p:
        exe = os.environ.get("NEMIK_CHROMIUM")
        try:
            browser = p.chromium.launch(
                executable_path=os.path.abspath(exe) if exe else None
            )
        except sync_api.Error as e:
            pytest.skip(f"chromium unavailable: {e}")
        page = browser.new_page(
            viewport={"width": 1700, "height": 1250}, color_scheme=scheme
        )
        page.goto(server)
        page.wait_for_selector("#pathkey line", state="attached")
        measured = page.evaluate(USE_OF_COLOUR)
        browser.close()
    data = tmp_path / "input.json"
    data.write_text(json.dumps(measured))
    query = "data.el.use_of_colour"
    cmd = [opa, "eval", "-f", "json", "-d", rego, "-i", str(data), query]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True)
    verdict = json.loads(out.stdout)["result"][0]["expressions"][0]["value"]
    assert verdict["deny"] == [], verdict["deny"]
    assert len(verdict["admitted"]) == len(measured["cases"]) >= 5


def test_a_static_build_refetches_only_the_pieces_whose_hash_moved(tmp_path) -> None:
    # nemik:W416: the page reads graph.json's pieces by hashes.json, draws the same graph, and on a
    # refresh fetches only the piece whose hash changed.
    import functools
    import http.server
    import json
    import threading

    from nemik.serve import build_static

    withheld = tmp_path / "withheld.json"
    withheld.write_text(json.dumps({"version": 1, "as_of": "x", "items": []}))
    out = tmp_path / "out"
    build_static(FLEET, out, withheld)
    whole = json.loads((out / "graph.json").read_text())
    fleet = json.loads((out / "graph" / "_fleet.json").read_text())
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(out)
    )
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{httpd.server_address[1]}/"
    try:
        with sync_api.sync_playwright() as p:
            exe = os.environ.get("NEMIK_CHROMIUM")
            try:
                browser = p.chromium.launch(
                    executable_path=os.path.abspath(exe) if exe else None
                )
            except sync_api.Error as e:
                pytest.skip(f"chromium unavailable: {e}")
            page = browser.new_page()
            page.goto(url)
            page.wait_for_function("() => typeof data !== 'undefined' && data")
            drawn = page.evaluate("() => data.nodes.length")
            first = page.evaluate("() => [...window.__pieceFetches]")
            one = fleet["repos"][0]
            hashes = json.loads((out / "hashes.json").read_text())
            hashes[f"graph/{one}.json"] = "moved"
            (out / "hashes.json").write_text(json.dumps(hashes))
            page.evaluate("() => load()")
            second = page.evaluate("n => window.__pieceFetches.slice(n)", len(first))
            browser.close()
    finally:
        httpd.shutdown()
    assert drawn == len(whole["nodes"])
    assert sorted(first) == sorted(
        ["graph/_fleet.json", *(f"graph/{r}.json" for r in fleet["repos"])]
    )
    assert second == [f"graph/{one}.json"]


def test_every_repo_chip_names_its_health_in_words(server) -> None:
    # nemik:W432: a chip's health was a glyph plus a title attribute; its accessible name now says
    # the repo, the status and the reasons, and the glyph is hidden from assistive tech.
    with sync_api.sync_playwright() as p:
        exe = os.environ.get("NEMIK_CHROMIUM")
        try:
            browser = p.chromium.launch(
                executable_path=os.path.abspath(exe) if exe else None
            )
        except sync_api.Error as e:
            pytest.skip(f"chromium unavailable: {e}")
        page = browser.new_page()
        page.goto(server)
        page.wait_for_selector("#repos button[data-repo]")
        chips = page.evaluate(
            "() => [...document.querySelectorAll('#repos button[data-repo]')].map(b => "
            "[b.dataset.repo, b.dataset.health, b.getAttribute('aria-label'), "
            "[...b.querySelectorAll('[aria-hidden=true]')].map(s => s.textContent).join('')])"
        )
        browser.close()
    assert chips
    for repo, status, name, hidden in chips:
        assert name.startswith(f"{repo}, health {status}"), name
        assert "▲" not in name and "■" not in name, name
        assert hidden == {"amber": "▲ ", "red": "■ "}.get(status, "")


def test_the_card_list_selects_and_expands_from_the_keyboard(server) -> None:
    # nemik:W435: selecting a card, reading it, and expanding an umbrella were pointer-only on the
    # canvas. The Cards list does each with focus and Enter alone.
    with sync_api.sync_playwright() as p:
        exe = os.environ.get("NEMIK_CHROMIUM")
        try:
            browser = p.chromium.launch(
                executable_path=os.path.abspath(exe) if exe else None
            )
        except sync_api.Error as e:
            pytest.skip(f"chromium unavailable: {e}")
        page = browser.new_page(viewport={"width": 1700, "height": 1250})
        page.goto(server)
        page.wait_for_function(
            "() => typeof cy !== 'undefined' && cy && cy.nodes('[symbol]').length > 0",
            timeout=60000,
        )
        page.click("#repos button[data-repo='nemik']")
        page.check("#rollup")
        page.wait_for_timeout(600)
        page.evaluate("() => { document.getElementById('sec-cards').open = true; }")
        listed = page.evaluate(
            "() => document.querySelectorAll('#cardlist button[data-card]').length"
        )
        drawn = page.evaluate(
            "() => cy.nodes('[symbol]')"
            ".filter(n => n.visible() && n.data('state') !== 'unclaimed').length"
        )
        first = page.locator("#cardlist button[data-card]").nth(1)
        target = first.get_attribute("data-card")
        first.focus()
        page.keyboard.press("Enter")
        page.wait_for_timeout(300)
        selected = page.evaluate("() => cy.nodes(':selected').map(n => n.id())")
        current = first.get_attribute("aria-current")
        focused = page.evaluate("() => document.activeElement.dataset.card")
        detail = page.inner_text("#detail")
        toggle = page.locator("#cardlist button[data-toggle]").first
        before = page.evaluate("() => cy.nodes('[symbol]').length")
        toggle.focus()
        page.keyboard.press("Enter")
        page.wait_for_timeout(600)
        after = page.evaluate("() => cy.nodes('[symbol]').length")
        expanded = page.evaluate(
            "() => document.activeElement.getAttribute('aria-expanded')"
        )
        browser.close()
    assert target is not None
    assert listed == drawn > 1
    assert selected == [target]
    assert current == "true" and focused == target
    assert target.rsplit("/", 1)[-1] in detail
    assert after > before
    assert expanded == "true"


def test_a_cite_link_in_the_panel_selects_its_card_and_announces_it(server) -> None:
    # nemik:W473: cite links in the Selected panel and the lanes did nothing; every one now goes
    # through the same select path as a tap, and the selection is spoken in a polite live region.
    with sync_api.sync_playwright() as p:
        exe = os.environ.get("NEMIK_CHROMIUM")
        try:
            browser = p.chromium.launch(
                executable_path=os.path.abspath(exe) if exe else None
            )
        except sync_api.Error as e:
            pytest.skip(f"chromium unavailable: {e}")
        page = browser.new_page(viewport={"width": 1700, "height": 1250})
        page.goto(server)
        page.wait_for_function(
            "() => typeof cy !== 'undefined' && cy && cy.nodes('[symbol]').length > 1",
            timeout=60000,
        )
        target = page.evaluate(
            "() => { const n = cy.nodes('[symbol]').filter(n => n.visible()"
            " && n.data('cite')).last().data();"
            " document.getElementById('detail').innerHTML = citeLink(n.cite);"
            " return { id: n.id, cite: n.cite }; }"
        )
        page.click("#detail a[data-cite]")
        page.wait_for_timeout(300)
        selected = page.evaluate("() => cy.nodes(':selected').map(n => n.id())")
        said = page.inner_text("#announce")
        live = page.get_attribute("#announce", "aria-live")
        detail = page.inner_text("#detail")
        browser.close()
    assert selected == [target["id"]]
    assert target["cite"] in said and live == "polite"
    assert target["cite"].rsplit(":", 1)[-1] in detail


def test_the_view_chain_is_drawn_end_to_end_with_its_length(server) -> None:
    # nemik:W482 (operator 2026-10-13: chains of 2 and 3 both ringed "longest, this view"). Each ring
    # was a piece of one longest chain that ran on into another repo's box; the chain's own edges now
    # draw it end to end, and the legend says how long it is.
    with sync_api.sync_playwright() as p:
        exe = os.environ.get("NEMIK_CHROMIUM")
        try:
            browser = p.chromium.launch(
                executable_path=os.path.abspath(exe) if exe else None
            )
        except sync_api.Error as e:
            pytest.skip(f"chromium unavailable: {e}")
        page = browser.new_page(viewport={"width": 1700, "height": 1250})
        page.goto(server)
        page.wait_for_function(
            "() => typeof cy !== 'undefined' && cy && cy.nodes('[symbol]').length > 0",
            timeout=60000,
        )
        page.wait_for_timeout(1000)
        got = page.evaluate(
            "() => { const on = new Set(viewChain);"
            " const ends = cy.edges('.onchain').map(e => [e.source().id(), e.target().id()]);"
            " const touched = new Set(ends.flat());"
            " return { longest: viewChain.longest, cards: on.size, edges: ends.length,"
            " stray: ends.filter(([a, b]) => !on.has(a) || !on.has(b)).length,"
            " untouched: [...on].filter(id => !touched.has(id)).length,"
            " legend: document.getElementById('pathkey').innerText }; }"
        )
        browser.close()
    assert got["longest"] > 1, "the fixture fleet has no chain to draw"
    assert got["edges"] >= got["longest"] - 1
    assert got["stray"] == 0, "a chain edge has an end off the chain"
    assert got["untouched"] == 0, "a card on the chain has no chain edge"
    assert f"({got['longest']} cards" in got["legend"]


def test_the_page_script_runs_without_errors(server) -> None:
    # nemik:W478: a redeclared const killed the whole page script, and every view test then failed
    # with "cy.nodes is not a function" (cy fell back to the #cy element). Name the cause instead.
    with sync_api.sync_playwright() as p:
        exe = os.environ.get("NEMIK_CHROMIUM")
        try:
            browser = p.chromium.launch(
                executable_path=os.path.abspath(exe) if exe else None
            )
        except sync_api.Error as e:
            pytest.skip(f"chromium unavailable: {e}")
        page = browser.new_page(viewport={"width": 1700, "height": 1250})
        errors: list[str] = []
        page.on("pageerror", lambda err: errors.append(str(err)))
        page.goto(server)
        page.wait_for_timeout(3000)
        browser.close()
    assert errors == []


def test_the_card_list_is_one_tab_stop_walked_by_arrows(server) -> None:
    # nemik:W478: the Cards list was a tab stop per card (hundreds of Tabs to cross it). Now the list
    # is one stop, the arrows walk it, Enter selects, and Tab leaves it.
    with sync_api.sync_playwright() as p:
        exe = os.environ.get("NEMIK_CHROMIUM")
        try:
            browser = p.chromium.launch(
                executable_path=os.path.abspath(exe) if exe else None
            )
        except sync_api.Error as e:
            pytest.skip(f"chromium unavailable: {e}")
        page = browser.new_page(viewport={"width": 1700, "height": 1250})
        page.goto(server)
        page.wait_for_function(
            "() => typeof cy !== 'undefined' && cy && cy.nodes('[symbol]').length > 1",
            timeout=60000,
        )
        page.evaluate("() => { document.getElementById('sec-cards').open = true; }")
        page.wait_for_timeout(300)
        stops = page.evaluate(
            "() => [...document.querySelectorAll('#cardlist button')]"
            ".filter(b => b.tabIndex === 0).length"
        )
        rows = page.evaluate(
            "() => [...document.querySelectorAll('#cardlist button[data-card]')]"
            ".map(b => b.dataset.card)"
        )
        page.locator("#cardlist button[tabindex='0']").focus()
        page.keyboard.press("ArrowDown")
        page.keyboard.press("ArrowDown")
        second = page.evaluate("() => document.activeElement.dataset.card")
        page.keyboard.press("End")
        last = page.evaluate("() => document.activeElement.dataset.card")
        page.keyboard.press("Home")
        page.keyboard.press("ArrowDown")
        page.keyboard.press("Enter")
        page.wait_for_timeout(300)
        selected = page.evaluate("() => cy.nodes(':selected').map(n => n.id())")
        page.keyboard.press("Tab")
        outside = page.evaluate(
            "() => !document.getElementById('cardlist').contains(document.activeElement)"
        )
        browser.close()
    assert len(rows) > 2
    assert stops == 1
    assert second == rows[2] and last == rows[-1]
    assert selected == [rows[1]]
    assert outside, "Tab stayed inside the list"


def test_the_card_popover_follows_the_hovercard_rules(server) -> None:
    # nemik:W462 (operator 2026-10-13: the card view as a popover on hover plus delay). WCAG 1.4.13:
    # not before the delay, hoverable (the pointer may move onto it), dismissible (Esc), and gone
    # once the pointer leaves both the card and the popover.
    with sync_api.sync_playwright() as p:
        exe = os.environ.get("NEMIK_CHROMIUM")
        try:
            browser = p.chromium.launch(
                executable_path=os.path.abspath(exe) if exe else None
            )
        except sync_api.Error as e:
            pytest.skip(f"chromium unavailable: {e}")
        page = browser.new_page(viewport={"width": 1700, "height": 1250})
        page.goto(server)
        page.wait_for_function(
            "() => typeof cy !== 'undefined' && cy && cy.nodes('[symbol]').length > 0",
            timeout=60000,
        )
        page.wait_for_timeout(800)
        card = page.evaluate(
            "() => { const n = cy.nodes('[symbol]').filter(n => n.visible()"
            " && n.data('state') !== 'unclaimed').first();"
            " const r = document.getElementById('cy').getBoundingClientRect(),"
            " p = n.renderedPosition();"
            " return { x: r.left + p.x, y: r.top + p.y, cite: n.data('cite') }; }"
        )
        hidden = "() => document.getElementById('pop').hidden"
        page.mouse.move(card["x"], card["y"])
        page.wait_for_timeout(150)
        early = page.evaluate(hidden)
        page.wait_for_timeout(600)
        shown = not page.evaluate(hidden)
        text = page.inner_text("#pop")
        box = page.locator("#pop").bounding_box()
        assert box is not None
        page.mouse.move(box["x"] + 10, box["y"] + 10, steps=4)
        page.wait_for_timeout(500)
        kept = not page.evaluate(hidden)
        page.keyboard.press("Escape")
        dismissed = page.evaluate(hidden)
        page.mouse.move(card["x"], card["y"])
        page.wait_for_timeout(700)
        page.mouse.move(5, 5)
        page.wait_for_timeout(500)
        left = page.evaluate(hidden)
        browser.close()
    assert early, "the popover opened before its delay"
    assert shown and card["cite"] in text
    assert kept, "the popover closed when the pointer moved onto it"
    assert dismissed, "Esc did not dismiss the popover"
    assert left, "the popover stayed after the pointer left"


def test_every_card_demand_crosses_carries_a_number(server) -> None:
    # nemik:W464: only the frontier absorbs salience, so a waiting card's label read blank though
    # demand ran through it (the operator read that as salience lost). With salience order on, every
    # drawn card with demand leaving it says how much, in parentheses beside the frontier's number.
    with sync_api.sync_playwright() as p:
        exe = os.environ.get("NEMIK_CHROMIUM")
        try:
            browser = p.chromium.launch(
                executable_path=os.path.abspath(exe) if exe else None
            )
        except sync_api.Error as e:
            pytest.skip(f"chromium unavailable: {e}")
        page = browser.new_page(viewport={"width": 1700, "height": 1250})
        page.goto(server)
        page.wait_for_function(
            "() => typeof cy !== 'undefined' && cy && cy.nodes('[symbol]').length > 0",
            timeout=60000,
        )
        page.check("#bySalience")
        page.wait_for_timeout(1000)
        bare = page.evaluate(
            "() => { const carries = new Set(data.edges.filter(e => e.current)"
            ".map(e => e.kind === 'waits' ? e.source : e.target));"
            " return cy.nodes('[symbol]').filter(n => n.visible()"
            " && carries.has(n.id()) && !/ · /.test(n.data('label')))"
            ".map(n => n.data('label')); }"
        )
        carried = page.evaluate(
            "() => cy.nodes('[symbol]').filter(n => / · \\(/.test(n.data('label'))).length"
        )
        browser.close()
    assert carried > 0, "the fixture fleet has no waiting card with demand to label"
    assert bare == []


def test_a_rolled_up_tile_says_what_it_hides(server) -> None:
    # nemik:W474: the treemap rebuilt tile labels from the bare repo and symbol, so a rolled-up
    # umbrella (luthen-observability:W43 hiding W111) read as a plain card and its work vanished.
    with sync_api.sync_playwright() as p:
        exe = os.environ.get("NEMIK_CHROMIUM")
        try:
            browser = p.chromium.launch(
                executable_path=os.path.abspath(exe) if exe else None
            )
        except sync_api.Error as e:
            pytest.skip(f"chromium unavailable: {e}")
        page = browser.new_page(viewport={"width": 1700, "height": 1250})
        page.goto(server)
        page.wait_for_function(
            "() => typeof cy !== 'undefined' && cy && cy.nodes('[symbol]').length > 0",
            timeout=60000,
        )
        page.check("#rollup")
        page.check("#treemap")
        page.wait_for_timeout(1500)
        tiles = page.evaluate(
            "() => cy.nodes('.tile').filter(n => n.visible() && n.data('rollup')"
            " && !n.hasClass('tinylabel') && n.data('label'))"
            ".map(n => ({ label: n.data('label'), rollup: n.data('rollup') }))"
        )
        browser.close()
    assert tiles, "the fixture fleet has no labelled rolled-up tile to check"
    for t in tiles:
        assert f"+{t['rollup']}" in t["label"], t


TILE_LABELS = """() => {
  const z = cy.zoom(), tiles = cy.nodes('.tile').filter(n => n.visible());
  const drawn = tiles.filter(n => !n.hasClass('tinylabel'));
  return { tiles: tiles.length, hidden: tiles.length - drawn.length,
           smallest: Math.min(...drawn.map(n => (n.data('fs') || 10) * z)),
           note: document.getElementById('legnote').textContent };
}"""
ZOOM_IN_4X = "() => cy.zoom({ level: cy.zoom() * 4, renderedPosition: { x: 0, y: 0 } })"


def test_treemap_labels_meet_the_floor_or_are_hidden_and_counted(server) -> None:
    # nemik:W390: no tile label is drawn under 8 px; the ones hidden are counted on the status line, and
    # zooming in brings them back.
    with sync_api.sync_playwright() as p:
        exe = os.environ.get("NEMIK_CHROMIUM")
        try:
            browser = p.chromium.launch(
                executable_path=os.path.abspath(exe) if exe else None
            )
        except sync_api.Error as e:
            pytest.skip(f"chromium unavailable: {e}")
        page = browser.new_page(viewport={"width": 1700, "height": 1250})
        page.goto(server)
        page.wait_for_function(
            "() => typeof cy !== 'undefined' && cy && cy.nodes('[symbol]').length > 0",
            timeout=60000,
        )
        page.check("#treemap")
        page.wait_for_function("() => cy.nodes('.tile').length > 0", timeout=60000)
        page.wait_for_timeout(300)
        fit = page.evaluate(TILE_LABELS)
        page.evaluate(ZOOM_IN_4X)
        page.wait_for_timeout(300)
        zoomed = page.evaluate(TILE_LABELS)
        browser.close()
    assert fit["tiles"] > 0
    assert fit["smallest"] >= 8, fit
    assert zoomed["smallest"] >= 8, zoomed
    if fit["hidden"]:
        assert f"{fit['hidden']} tiles too small" in fit["note"], fit
        assert zoomed["hidden"] < fit["hidden"], (fit, zoomed)


NON_TEXT_CONTRAST = """() => {
  // nemik:W437: WCAG 1.4.11, 3:1 for graphical objects that carry meaning, measured on rendered colours
  const rgb = c => { const x = document.createElement('div'); x.style.color = c; document.body.appendChild(x);
    const m = getComputedStyle(x).color.match(/\\d+(\\.\\d+)?/g).map(Number); x.remove(); return m.slice(0, 3); };
  const lum = c => { const [r, g, b] = rgb(c).map(v => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
  const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
  const bg = getComputedStyle(document.body).backgroundColor;
  const out = {};
  SCOPES.forEach(s => { out['ring ' + s.id] = ratio(scopeColor(s.color), bg); });
  const w = cy.edges('.waits')[0];
  if (w) out['wait line'] = ratio(w.style('line-color'), bg);
  const e = cy.edges().filter(x => !x.hasClass('waits') && x.visible())[0];
  if (e) out['enables line'] = ratio(e.style('line-color'), bg);
  return out;
}"""


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_meaningful_strokes_reach_three_to_one(server, scheme) -> None:
    with sync_api.sync_playwright() as p:
        exe = os.environ.get("NEMIK_CHROMIUM")
        try:
            browser = p.chromium.launch(
                executable_path=os.path.abspath(exe) if exe else None
            )
        except sync_api.Error as e:
            pytest.skip(f"chromium unavailable: {e}")
        page = browser.new_page(
            viewport={"width": 1700, "height": 1250}, color_scheme=scheme
        )
        page.goto(server)
        page.wait_for_selector("#pathkey line", state="attached")
        ratios = page.evaluate(NON_TEXT_CONTRAST)
        browser.close()
    low = {k: round(v, 2) for k, v in ratios.items() if v < 3}
    assert len(ratios) >= 5
    assert not low, f"{scheme}: under 3:1 against the page: {low}"


GLYPH_ROLES = """() => {
  // nemik:W456: every glyph a card label can carry, by the role it plays; a glyph in two roles makes
  // a label ambiguous ("‖ W503 ▸ 3" once read as working)
  const glyphs = s => [...s].filter(c => c.trim() && !/[A-Za-z0-9]/.test(c));
  return {
    state: [...Object.values(STATE_MARK).flatMap(glyphs), "?"],
    rollup: glyphs(ROLLUP_MARK),
    expanded: glyphs(EXPANDED_MARK),
    salience: ["·"],
  };
}"""


def test_no_label_glyph_plays_two_roles(server) -> None:
    with sync_api.sync_playwright() as p:
        exe = os.environ.get("NEMIK_CHROMIUM")
        try:
            browser = p.chromium.launch(
                executable_path=os.path.abspath(exe) if exe else None
            )
        except sync_api.Error as e:
            pytest.skip(f"chromium unavailable: {e}")
        page = browser.new_page(viewport={"width": 1700, "height": 1250})
        page.goto(server)
        page.wait_for_function(
            "() => typeof cy !== 'undefined' && cy && cy.nodes('[symbol]').length > 0",
            timeout=60000,
        )
        roles = page.evaluate(GLYPH_ROLES)
        page.click("#repos button[data-repo='nemik']")
        page.check("#rollup")
        page.wait_for_timeout(600)
        rolled = page.evaluate(
            "() => cy.nodes('[rollup > 0]').map(n => [n.data('label'), n.data('rollup')])"
        )
        browser.close()
    seen: dict[str, str] = {}
    for role, glyphs in roles.items():
        for g in glyphs:
            assert seen.setdefault(g, role) == role, (
                f"{g!r} is both {seen[g]} and {role}"
            )
    assert rolled, "the fixture has an umbrella to roll up"
    assert all(label.endswith(f"+{n}") for label, n in rolled), rolled


def test_no_command_route_or_tools_panel_remains(server) -> None:
    # nemik:W397: the Tools drop-down ran CLIs through /cmd; it is retired, and every capability it
    # offered is either native to the view or CLI-only. Neither the route nor the panel may come back.
    import urllib.error
    import urllib.request

    try:
        urllib.request.urlopen(server + "cmd/rank?repo=a", timeout=30)
        status = 200
    except urllib.error.HTTPError as e:
        status = e.code
    assert status == 404
    with sync_api.sync_playwright() as p:
        exe = os.environ.get("NEMIK_CHROMIUM")
        try:
            browser = p.chromium.launch(
                executable_path=os.path.abspath(exe) if exe else None
            )
        except sync_api.Error as e:
            pytest.skip(f"chromium unavailable: {e}")
        page = browser.new_page()
        page.goto(server)
        page.wait_for_selector("details.sec")
        tools = page.evaluate(
            "() => [document.getElementById('tool'), document.getElementById('sec-tools')]"
        )
        browser.close()
    assert tools == [None, None]


def test_one_picked_repo_restored_from_the_last_visit_is_legible_too(server) -> None:
    # nemik:W383 (W380 refuted the floor here): a single repo, picked and remembered from a previous
    # visit, is the first view on reload; its labels must still be at least 8 px.
    with sync_api.sync_playwright() as p:
        exe = os.environ.get("NEMIK_CHROMIUM")
        try:
            browser = p.chromium.launch(
                executable_path=os.path.abspath(exe) if exe else None
            )
        except sync_api.Error as e:
            pytest.skip(f"chromium unavailable: {e}")
        page = browser.new_page(viewport={"width": 900, "height": 600})
        page.goto(server)
        page.wait_for_function(
            "() => typeof cy !== 'undefined' && cy && cy.nodes('[symbol]').length > 0",
            timeout=60000,
        )
        # the repo with the most cards, so its fit is the one most likely to fall under the floor
        big = page.evaluate(
            "() => { const c = {}; data.nodes.forEach(n => c[n.repo] = (c[n.repo] || 0) + 1);"
            " return Object.entries(c).sort((a, b) => b[1] - a[1])[0][0]; }"
        )
        page.evaluate(
            f"() => localStorage.setItem('nemik.repos', JSON.stringify(['{big}']))"
        )
        page.reload()
        page.wait_for_function(
            "() => typeof cy !== 'undefined' && cy && cy.nodes('[symbol]').length > 0",
            timeout=60000,
        )
        page.wait_for_timeout(500)
        m = page.evaluate(LEGIBILITY)
        browser.close()
    assert m["label_px"] >= 8, m


def test_picked_repos_show_their_blockers_blockers_as_context(server) -> None:
    # nemik:W336: pick one repo; its cards' blockers in other repos are drawn dashed as context, and one
    # more hop (the control's 2) reaches at least as many, never fewer, and never a picked repo's card.
    with sync_api.sync_playwright() as p:
        exe = os.environ.get("NEMIK_CHROMIUM")
        try:
            browser = p.chromium.launch(
                executable_path=os.path.abspath(exe) if exe else None
            )
        except sync_api.Error as e:
            pytest.skip(f"chromium unavailable: {e}")
        page = browser.new_page(viewport={"width": 1700, "height": 1250})
        page.goto(server)
        page.wait_for_function(
            "() => typeof cy !== 'undefined' && cy && cy.nodes('[symbol]').length > 0",
            timeout=60000,
        )
        page.click("#repos button[data-repo='nemik']")
        counts = []
        for hops in ("1", "2", "3"):
            page.select_option("#depth", hops)
            page.wait_for_timeout(600)
            counts.append(page.evaluate("() => cy.nodes('[?ghost]').length"))
        stray = page.evaluate(
            "() => cy.nodes('[?ghost]').filter(n => n.data('repo') === 'nemik').length"
        )
        browser.close()
    assert counts[0] <= counts[1] <= counts[2], counts
    assert counts[1] > 0 and stray == 0, (counts, stray)


def test_rank_forest_view(server, tmp_path) -> None:
    out = Path(os.environ.get("TEST_UNDECLARED_OUTPUTS_DIR") or tmp_path)
    with sync_api.sync_playwright() as p:
        try:
            exe = os.environ.get("NEMIK_CHROMIUM")
            browser = p.chromium.launch(
                executable_path=os.path.abspath(exe) if exe else None
            )
        except Exception as e:  # noqa: BLE001 - no browser installed here
            pytest.skip(f"chromium unavailable: {e}")
        page = browser.new_page(
            viewport={"width": 1700, "height": 1250}, color_scheme="dark"
        )
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(server)
        page.wait_for_function(
            "() => typeof cy !== 'undefined' && cy && cy.nodes('[symbol]').length > 0",
            timeout=60000,
        )
        ranked = page.evaluate("() => cy.nodes('[rank_pos]').length")
        page.wait_for_timeout(500)
        m = page.evaluate(METRICS)
        overlaps = page.evaluate(NODE_OVERLAPS)
        page.screenshot(path=str(out / "forest-dark.png"))
        page.evaluate("() => cy.fit(cy.getElementById('repo:life'), 20)")
        page.wait_for_timeout(300)
        page.screenshot(path=str(out / "forest-life.png"))
        browser.close()
    (out / "forest-dark.json").write_text(json.dumps(m, indent=1))
    assert errors == []
    assert ranked > 0  # the server ships nemik-rank's composed order
    assert overlaps == []
    assert m["labels_outside"] == []
    assert m["cross_p95"] <= FOREST_BUDGET["cross_p95"], m
    assert m["fit_zoom"] >= FOREST_BUDGET["fit_zoom"], m
    assert m["intra_crossings"] <= FOREST_BUDGET["intra_crossings"], m
    assert m["cross_upward"] <= FOREST_BUDGET["cross_upward"], m


TREEMAP_INVARIANTS = """async () => {
  const g = await (await fetch("graph.json")).json();
  const t = treeOf(g.nodes, g.edges);
  const order = g.nodes.filter(n => n.rank_pos !== undefined).sort((a, b) => a.rank_pos - b.rank_pos).map(n => n.id);
  const R = orderedTreemap(t, order, { x: 0, y: 0, w: 1600, h: 1000 });
  const bad = [];
  for (const [id, p] of t.parent) {
    if (!R.has(id)) bad.push("unplaced " + id);
    const r = R.get(id), q = p && R.get(p);
    if (q && !(r.x >= q.x - 1e-6 && r.y >= q.y - 1e-6 && r.x + r.w <= q.x + q.w + 1e-6 && r.y + r.h <= q.y + q.h + 1e-6)) bad.push("outside parent " + id);
  }
  const sibs = [t.roots, ...t.kids.values()];
  const hit = (a, b) => a.x < b.x + b.w - 1e-6 && b.x < a.x + a.w - 1e-6 && a.y < b.y + b.h - 1e-6 && b.y < a.y + a.h - 1e-6;
  for (const s of sibs) for (let i = 0; i < s.length; i++) for (let j = i + 1; j < s.length; j++) if (hit(R.get(s[i]), R.get(s[j]))) bad.push("overlap " + s[i] + " " + s[j]);
  const tot = [...R.keys()].filter(k => !k.endsWith("#self")).length;
  return { bad: bad.slice(0, 5), n: t.parent.size, roots: t.roots.length, total: tot,
           repos_in_one_root: Math.max(...t.roots.map(r => { const s = new Set(), st = [r]; while (st.length) { const x = st.pop(); s.add(x.split("/").slice(-2)[0]); st.push(...t.kids.get(x)); } return s.size; })) };
}"""


def test_treemap_model(server) -> None:
    """nemik:W180 step 1: one parent each, children inside parents, siblings disjoint, across repos."""
    with sync_api.sync_playwright() as p:
        try:
            exe = os.environ.get("NEMIK_CHROMIUM")
            browser = p.chromium.launch(
                executable_path=os.path.abspath(exe) if exe else None
            )
        except Exception as e:  # noqa: BLE001 - no browser installed here
            pytest.skip(f"chromium unavailable: {e}")
        page = browser.new_page()
        page.goto(server)
        page.wait_for_function("() => typeof treeOf === 'function'", timeout=60000)
        m = page.evaluate(TREEMAP_INVARIANTS)
        browser.close()
    assert m["bad"] == [], m
    assert m["n"] > 0 and m["total"] == m["n"], (
        m
    )  # every open item is placed exactly once
    assert m["repos_in_one_root"] > 1, m  # not grouped by repo: a tree spans repos


def test_treemap_view_draws(server, tmp_path) -> None:
    """nemik:W180 step 2: the toggle draws tiles nested as the model says, with no page errors."""
    out = Path(os.environ.get("TEST_UNDECLARED_OUTPUTS_DIR") or tmp_path)
    with sync_api.sync_playwright() as p:
        try:
            exe = os.environ.get("NEMIK_CHROMIUM")
            browser = p.chromium.launch(
                executable_path=os.path.abspath(exe) if exe else None
            )
        except Exception as e:  # noqa: BLE001 - no browser installed here
            pytest.skip(f"chromium unavailable: {e}")
        page = browser.new_page(
            viewport={"width": 1700, "height": 1250}, color_scheme="dark"
        )
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(server)
        page.wait_for_function(
            "() => typeof cy !== 'undefined' && cy && cy.nodes('[symbol]').length > 0",
            timeout=60000,
        )
        page.evaluate(
            "() => { cy.zoom(4); cy.pan({x: -3000, y: -2000}); }"
        )  # the reader had zoomed in
        page.check("#treemap")
        page.wait_for_function("() => cy.nodes('.tile').length > 0", timeout=60000)
        # W185: toggling the view refits; the old zoom/pan scaled one tile off the page.
        fit = page.evaluate("""() => { const b = cy.elements(':visible').renderedBoundingBox();
          return b.x1 >= -1 && b.y1 >= -1 && b.x2 <= cy.width() + 1 && b.y2 <= cy.height() + 1; }""")
        m = page.evaluate("""() => {
          // Step 6: nested clusters. A child lies inside its parent's frame (below the header); two
          // tiles overlap only when one contains the other.
          const tiles = cy.nodes('.tile').filter(n => n.visible()), bad = [];
          const rect = n => { const p = n.position(), w = n.data('tw') / 2, h = n.data('th') / 2;
            return { x1: p.x - w, x2: p.x + w, y1: p.y - h, y2: p.y + h }; };
          const inside = (c, q) => c.x1 >= q.x1 - 0.5 && c.y1 >= q.y1 - 0.5 && c.x2 <= q.x2 + 0.5 && c.y2 <= q.y2 + 0.5;
          cy.edges('.contained').forEach(e => { if (!inside(rect(e.source()), rect(e.target()))) bad.push('outside ' + e.source().id()); });
          const bbs = tiles.map(n => [n.id(), rect(n)]);
          const hit = (a, b) => a.x1 < b.x2 - 0.5 && b.x1 < a.x2 - 0.5 && a.y1 < b.y2 - 0.5 && b.y1 < a.y2 - 0.5;
          for (let i = 0; i < bbs.length; i++) for (let j = i + 1; j < bbs.length; j++) {
            const [a, b] = [bbs[i][1], bbs[j][1]];
            if (hit(a, b) && !inside(a, b) && !inside(b, a)) bad.push(bbs[i][0] + " x " + bbs[j][0]);
          }
          // Leaf labels: repo on the first line, and the text inside its tile (canvas-measured).
          const ctx = document.createElement('canvas').getContext('2d'), clipped = [];
          let twoLine = 0;
          tiles.filter(n => !n.hasClass('cluster') && n.data('label')).forEach(n => {
            const lines = String(n.data('label')).split('\\n');
            if (lines.length === 2 && lines[0] === n.data('repo')) twoLine++;
            ctx.font = `bold ${n.data('fs')}px ${getComputedStyle(document.body).fontFamily}`;
            const w = Math.max(...lines.map(l => ctx.measureText(l).width));
            if (w > n.data('tw') + 0.5 || lines.length * n.data('fs') * 1.2 > n.data('th') + 0.5) clipped.push(n.id());
          });
          const repos = new Set(tiles.map(n => n.data('repo')));
          const bb = cy.elements(':visible').boundingBox();
          const key = document.getElementById('repokey');
          return { two_line: twoLine, clipped: clipped.slice(0, 5), groups: cy.nodes('.tile.cluster').length, key_repos: key.hidden ? 0 : key.querySelectorAll('span').length, tiles: tiles.length, contained: cy.edges('.contained').length, outside: bad.slice(0, 5),
                   repo_boxes: cy.nodes('.repo').length, repos: repos.size,
                   fit_zoom: Math.round(1000 * Math.min(cy.width() / (bb.w + 40), cy.height() / (bb.h + 40))) / 1000 };
        }""")
        page.evaluate("() => cy.fit(undefined, 20)")
        page.screenshot(path=str(out / "treemap-dark.png"))
        browser.close()
    (out / "treemap-dark.json").write_text(json.dumps(m, indent=1))
    assert errors == []
    assert fit, "the treemap is not fitted to the pane after the toggle"
    assert m["repo_boxes"] == 0 and m["repos"] > 1, m  # not grouped by repo
    assert m["key_repos"] == m["repos"], m
    assert m["groups"] > 0, m  # clusters are drawn as labelled frames
    assert m["two_line"] > 0 and m["clipped"] == [], (
        m
    )  # leaves name their repo, and every label fits  # every repo colour has a key entry
    assert m["tiles"] > 0 and m["contained"] > 0 and m["outside"] == [], (
        m
    )  # "outside" = overlapping tiles


@pytest.mark.parametrize("width", [380, 1400])
def test_side_panel_never_overflows_sideways(server, width) -> None:
    """Operator 2026-10-02: the panel cut text off on the right (a long ask, URL or ref list in the
    two-column detail grid). At phone and desktop widths, with the needs-you lane open, nothing in
    the aside is wider than the aside."""
    with sync_api.sync_playwright() as p:
        try:
            exe = os.environ.get("NEMIK_CHROMIUM")
            browser = p.chromium.launch(
                executable_path=os.path.abspath(exe) if exe else None
            )
        except Exception as e:  # noqa: BLE001 - no browser installed here
            pytest.skip(f"chromium unavailable: {e}")
        page = browser.new_page(viewport={"width": width, "height": 1200})
        page.goto(server)
        page.wait_for_function(
            "() => typeof cy !== 'undefined' && cy && cy.nodes('[symbol]').length > 0",
            timeout=60000,
        )
        # The fixture's text is stripped, so give the asks the shapes that overflowed live: a long
        # URL with no break opportunity, and a long ask.
        page.evaluate("""() => { for (const a of data.operator) {
            a.ask = 'operator: act open https://store.kde.org/p/0000000000/very-long-path-without-any-break-opportunity-at-all in your browser and approve the KubeVirt stage-1 apply after reviewing ten in-place component diffs';
            a.waiting = Array.from({length: 12}, (_, i) => 'luthen-observability:W1' + i); }
          lane('needs-you'); }""")
        page.wait_for_timeout(300)
        m = page.evaluate("""() => { const a = document.querySelector('aside');
          const r = a.getBoundingClientRect(), wide = [];
          a.querySelectorAll('*').forEach(e => { const b = e.getBoundingClientRect();
            if (b.width && b.right > r.right + 1) wide.push(e.tagName + ':' + (e.textContent || '').slice(0, 40)); });
          return { scroll: a.scrollWidth, client: a.clientWidth, wide: wide.slice(0, 5) }; }""")
        browser.close()
    assert m["wide"] == [] and m["scroll"] <= m["client"] + 1, m


def test_every_cite_in_the_panel_is_a_repo_colon_link(server) -> None:
    """Operator 2026-10-02: one cite format (repo:W<n>, never 'repo W<n>' or 'repo/W<n>'), and
    every cite shown is a link. Checked over a waypoint's detail, a lane, findings and wake."""
    with sync_api.sync_playwright() as p:
        try:
            exe = os.environ.get("NEMIK_CHROMIUM")
            browser = p.chromium.launch(
                executable_path=os.path.abspath(exe) if exe else None
            )
        except Exception as e:  # noqa: BLE001 - no browser installed here
            pytest.skip(f"chromium unavailable: {e}")
        page = browser.new_page(viewport={"width": 1400, "height": 1000})
        page.goto(server)
        page.wait_for_function(
            "() => typeof cy !== 'undefined' && cy && cy.nodes('[symbol]').length > 0",
            timeout=60000,
        )
        page.wait_for_timeout(500)
        bad = page.evaluate("""() => {
          const out = [], pat = /\\b[a-z][a-z0-9-]*(?:[:\\/]| )W\\d+\\b/;
          const scan = where => {
            const walk = document.createTreeWalker(document.querySelector('aside'), NodeFilter.SHOW_TEXT);
            for (let t; (t = walk.nextNode());) {
              if (t.parentElement.closest('a[data-cite], select, #toolout, p.stat')) continue;
              const m = t.textContent.match(pat);
              if (m) out.push(where + ': ' + m[0]);
            }
          };
          const ns = cy.nodes('[symbol]').filter(n => n.data('caused_by') && n.data('blocked_on').length);
          if (ns.length) { detail(ns[0].data()); scan('detail'); }
          lane('needs-you'); scan('lane');
          return [...new Set(out)].slice(0, 8);
        }""")
        browser.close()
    assert bad == []


def test_weather_panel_groups_one_outage(server) -> None:
    """nemik:W174 step 2: waypoints sharing a weather id list as one outage with all its waiters."""
    with sync_api.sync_playwright() as p:
        try:
            exe = os.environ.get("NEMIK_CHROMIUM")
            browser = p.chromium.launch(
                executable_path=os.path.abspath(exe) if exe else None
            )
        except Exception as e:  # noqa: BLE001 - no browser installed here
            pytest.skip(f"chromium unavailable: {e}")
        page = browser.new_page()
        page.goto(server)
        page.wait_for_function(
            "() => typeof cy !== 'undefined' && cy && cy.nodes('[symbol]').length > 0",
            timeout=60000,
        )
        m = page.evaluate("""() => {
          const open = data.nodes.filter(n => n.state === 'blocked' && n.cite).slice(0, 3);
          open.forEach(n => n.weather = 'wx:same');  // three repos' items wait on one outage
          weather();
          const once = weatherOnce(open.map(n => n.cite));
          return { rows: document.querySelectorAll('#weather dt').length,
                   waiters: document.querySelectorAll('#weather dd > a[data-cite]').length, once: once.length };
        }""")
        browser.close()
    assert m == {"rows": 1, "waiters": 3, "once": 1}, m
