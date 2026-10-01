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
BUDGET = {"cross_p95": 2450, "intra_p95": 365, "area": 11_900_000, "fit_zoom": 0.33,
          "intra_crossings": 120, "cross_upward": 18}
# The rank forest (W135), same rules. History (cross p95, fit zoom):
#   W135 forest, strict packing:            3654, 0.223 (2038x5352: a column on a landscape pane)
#   W127 packing may set a box beside the boxes it depends on: 2009, 0.458 (2319x2583)
#   W139 measured (in-box crossings, upward cross-box edges): strict 214, 16; loose (W127) 214, 17
FOREST_BUDGET = {"cross_p95": 2210, "fit_zoom": 0.41, "intra_crossings": 235, "cross_upward": 19}

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
