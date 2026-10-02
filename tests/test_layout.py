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

import pytest

import installed

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
BUDGET = {"cross_p95": 2450, "intra_p95": 365, "area": 13_600_000, "fit_zoom": 0.30,
          "intra_crossings": 215, "cross_upward": 18}
# The rank forest (W135), same rules. History (cross p95, fit zoom):
#   W135 forest, strict packing:            3654, 0.223 (2038x5352: a column on a landscape pane)
#   W127 packing may set a box beside the boxes it depends on: 2009, 0.458 (2319x2583)
#   W139 measured (in-box crossings, upward cross-box edges): strict 214, 16; loose (W127) 214, 17
#   W179 fruit class ranked as one row (W178): 2010, 0.458; in-box crossings 214 -> 310. The rise is
#        the price of a new constraint (rank order honours the fruit class), not a layout regression
#        (operator 2026-10-01); the budget is re-based on it, same ~10% headroom as before.
#   W141 regenerated fixture (501 open nodes): 2357, 0.45; crossings 190, upward 20. Re-based.
FOREST_BUDGET = {"cross_p95": 2600, "fit_zoom": 0.41, "intra_crossings": 340, "cross_upward": 22}

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
    proc = subprocess.Popen([*installed.script("nemik-serve"), "--root", str(FLEET), "--port", str(port)],
                            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
  const out = [];
  ns.forEach(a => ns.forEach(b => { if (a.id() < b.id() && hit(a.boundingBox(), b.boundingBox())) out.push(a.id() + " x " + b.id()); }));
  return out;
}"""

@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_layout_meets_budgets_with_labels_inside(server, scheme, tmp_path) -> None:
    out = Path(os.environ.get("TEST_UNDECLARED_OUTPUTS_DIR") or tmp_path)
    with sync_api.sync_playwright() as p:
        try:
            exe = os.environ.get("NEMIK_CHROMIUM")
            browser = p.chromium.launch(executable_path=os.path.abspath(exe) if exe else None)
        except Exception as e:  # noqa: BLE001 - no browser installed here
            pytest.skip(f"chromium unavailable: {e}")
        page = browser.new_page(viewport={"width": 1700, "height": 1250}, color_scheme=scheme)
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(server)
        page.wait_for_function("() => typeof cy !== 'undefined' && cy && cy.nodes('[symbol]').length > 0", timeout=60000)
        m = page.evaluate(METRICS)
        overlaps = page.evaluate(NODE_OVERLAPS)
        page.screenshot(path=str(out / f"layout-{scheme}.png"))
        browser.close()
    (out / f"layout-{scheme}.json").write_text(json.dumps(m, indent=1))
    assert errors == []
    assert overlaps == []  # nemik:W118 reorders rows after the layout
    assert m["labels_outside"] == []
    assert m["cross_p95"] <= BUDGET["cross_p95"], m
    assert m["intra_p95"] <= BUDGET["intra_p95"], m
    assert m["width"] * m["height"] <= BUDGET["area"], m
    assert m["fit_zoom"] >= BUDGET["fit_zoom"], m
    assert m["intra_crossings"] <= BUDGET["intra_crossings"], m
    assert m["cross_upward"] <= BUDGET["cross_upward"], m


def test_rank_forest_view(server, tmp_path) -> None:
    out = Path(os.environ.get("TEST_UNDECLARED_OUTPUTS_DIR") or tmp_path)
    with sync_api.sync_playwright() as p:
        try:
            exe = os.environ.get("NEMIK_CHROMIUM")
            browser = p.chromium.launch(executable_path=os.path.abspath(exe) if exe else None)
        except Exception as e:  # noqa: BLE001 - no browser installed here
            pytest.skip(f"chromium unavailable: {e}")
        page = browser.new_page(viewport={"width": 1700, "height": 1250}, color_scheme="dark")
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(server)
        page.wait_for_function("() => typeof cy !== 'undefined' && cy && cy.nodes('[symbol]').length > 0", timeout=60000)
        ranked = page.evaluate("() => cy.nodes('[rank_pos]').length")
        page.check("#forest")
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
            browser = p.chromium.launch(executable_path=os.path.abspath(exe) if exe else None)
        except Exception as e:  # noqa: BLE001 - no browser installed here
            pytest.skip(f"chromium unavailable: {e}")
        page = browser.new_page()
        page.goto(server)
        page.wait_for_function("() => typeof treeOf === 'function'", timeout=60000)
        m = page.evaluate(TREEMAP_INVARIANTS)
        browser.close()
    assert m["bad"] == [], m
    assert m["n"] > 0 and m["total"] == m["n"], m  # every open item is placed exactly once
    assert m["repos_in_one_root"] > 1, m  # not grouped by repo: a tree spans repos


def test_treemap_view_draws(server, tmp_path) -> None:
    """nemik:W180 step 2: the toggle draws tiles nested as the model says, with no page errors."""
    out = Path(os.environ.get("TEST_UNDECLARED_OUTPUTS_DIR") or tmp_path)
    with sync_api.sync_playwright() as p:
        try:
            exe = os.environ.get("NEMIK_CHROMIUM")
            browser = p.chromium.launch(executable_path=os.path.abspath(exe) if exe else None)
        except Exception as e:  # noqa: BLE001 - no browser installed here
            pytest.skip(f"chromium unavailable: {e}")
        page = browser.new_page(viewport={"width": 1700, "height": 1250}, color_scheme="dark")
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(server)
        page.wait_for_function("() => typeof cy !== 'undefined' && cy && cy.nodes('[symbol]').length > 0", timeout=60000)
        page.evaluate("() => { cy.zoom(4); cy.pan({x: -3000, y: -2000}); }")  # the reader had zoomed in
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
    assert m["two_line"] > 0 and m["clipped"] == [], m  # leaves name their repo, and every label fits  # every repo colour has a key entry
    assert m["tiles"] > 0 and m["contained"] > 0 and m["outside"] == [], m  # "outside" = overlapping tiles


@pytest.mark.parametrize("width", [380, 1400])
def test_side_panel_never_overflows_sideways(server, width) -> None:
    """Operator 2026-10-02: the panel cut text off on the right (a long ask, URL or ref list in the
    two-column detail grid). At phone and desktop widths, with the needs-you lane open, nothing in
    the aside is wider than the aside."""
    with sync_api.sync_playwright() as p:
        try:
            exe = os.environ.get("NEMIK_CHROMIUM")
            browser = p.chromium.launch(executable_path=os.path.abspath(exe) if exe else None)
        except Exception as e:  # noqa: BLE001 - no browser installed here
            pytest.skip(f"chromium unavailable: {e}")
        page = browser.new_page(viewport={"width": width, "height": 1200})
        page.goto(server)
        page.wait_for_function("() => typeof cy !== 'undefined' && cy && cy.nodes('[symbol]').length > 0", timeout=60000)
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
            browser = p.chromium.launch(executable_path=os.path.abspath(exe) if exe else None)
        except Exception as e:  # noqa: BLE001 - no browser installed here
            pytest.skip(f"chromium unavailable: {e}")
        page = browser.new_page(viewport={"width": 1400, "height": 1000})
        page.goto(server)
        page.wait_for_function("() => typeof cy !== 'undefined' && cy && cy.nodes('[symbol]').length > 0", timeout=60000)
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
            browser = p.chromium.launch(executable_path=os.path.abspath(exe) if exe else None)
        except Exception as e:  # noqa: BLE001 - no browser installed here
            pytest.skip(f"chromium unavailable: {e}")
        page = browser.new_page()
        page.goto(server)
        page.wait_for_function("() => typeof cy !== 'undefined' && cy && cy.nodes('[symbol]').length > 0", timeout=60000)
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
