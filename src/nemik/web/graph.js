// nemik:W799: a part of the page's script, moved out of index.html (docs/web-modules.md).
// A classic script: its functions and constants stay global, as they were, and index.html's
// script calls them when it runs.

// Only edges that point downstream (prerequisite above dependent) rank a layout. Each repo box is
// laid out on its own by forest() (below); then the boxes (and operator lanes) are themselves ranked by the edges that
// cross between them, oriented downstream: a box another box waits on sits above it. Cycles are cut
// at DFS back edges (the edge is still drawn, just not ranked). Units with no cross edges go in a
// last row, since nothing orders them.
// nemik:W180 (operator 2026-10-01: "the correct layout is probably reminiscent of a treemap"; not
// grouped by repo): the enables forest across the whole fleet, one parent each, and an ordered strip
// treemap of it. nemik:W826, W827, W828 (goal W812): both are src/nemik/core/treemap.py, compiled by
// Codon to core.wasm, the code the CLI runs natively; these are their facades (wasm.js maps the page's
// ids and Maps to the module and back). No JS copy: a browser without the module draws no treemap.
// treeOf(nodes, edges): {parent, kids, weight, own, roots}, Maps by id over the open cards.
// orderedTreemap(tree, order, rect, pad, head): a Map from id to {x, y, w, h, depth[, head]}.
// Without the module (loadCore says so in #chainsoff) the forest is empty and nothing is placed.
function treeOf(nodes, edges) {
  return coreWasm ? coreWasm.treeOf(nodes, edges)
    : { parent: new Map(), kids: new Map(), weight: new Map(), own: new Map(), roots: [] };
}
function orderedTreemap(tree, order, rect, pad = 4, head = 3 * pad) {
  return coreWasm ? coreWasm.orderedTreemap(tree, order, rect, pad, head) : new Map();
}

// nemik:W180 step 2: draw the treemap. Positions and sizes come from orderedTreemap; an enables
// edge to the tile's own parent is implied by containment and hidden; every other edge is drawn.
// Operator chips and placeholders sit in a row below the map.
// nemik:W829: the hue is core/text.py repo_hue through core.wasm; without the module, a grey.
function repoHue(r) { return coreWasm ? `hsl(${coreWasm.repoHue(String(r))}, 65%, 55%)` : "hsl(0, 0%, 55%)"; }
// The largest font (px, at most 28) at which `lines` fit a w x h box: measured with the page's own
// font on a canvas, so it holds for any string, not an average character width.
const _measure = document.createElement("canvas").getContext("2d");
function fitFont(lines, w, h) {
  _measure.font = `bold 100px ${getComputedStyle(document.body).fontFamily}`;
  const widest = Math.max(...lines.map(l => _measure.measureText(String(l)).width)) / 100;
  return Math.floor(Math.min(28, (w * 0.92) / widest, (h * 0.9) / (lines.length * 1.2)));
}
function treemap() {
  const ns = cy.nodes("[symbol]").filter(n => n.data("state") !== "unclaimed");
  const t = treeOf(ns.map(n => n.data()), cy.edges().map(e => ({ kind: e.hasClass("waits") ? "waits" : "enables",
    source: e.source().id(), target: e.target().id() })));
  const order = ns.filter(n => n.data("rank_pos") !== undefined).sort((a, b) => a.data("rank_pos") - b.data("rank_pos")).map(n => n.id());
  // Room for one label-sized leaf (about 50x50) per unit of weight, in the pane's landscape shape.
  const total = t.roots.reduce((a, r) => a + t.weight.get(r), 0), H = Math.sqrt(total * 2500 * 0.62), W = H / 0.62;
  const R = orderedTreemap(t, order, { x: 0, y: 0, w: W, h: H }, 4, 16);
  cy.batch(() => {
    // nemik:W474: a tile names its card as the graph does: its state mark, and an umbrella's roll-up
    // (+N hidden) or expanded mark, so work folded into a tile is never silently missing.
    const marked = n => stateMark(n.data()) + n.data("symbol") + warnMark(n.data())
      + (n.data("rollup") ? `${ROLLUP_MARK}${n.data("rollup")}` : expanded.has(n.id()) ? EXPANDED_MARK : "");
    ns.forEach(n => {
      const r = R.get(n.id());
      if (!r) { n.style("display", "none"); return; }
      const base = { tw: Math.max(1, r.w), th: Math.max(1, r.h), repoColor: repoHue(n.data("repo")), depth: r.depth };
      n.addClass("tile").removeClass("cluster").position({ x: r.x + r.w / 2, y: r.y + r.h / 2 });
      if (r.head !== undefined) {
        // A cluster: its label (symbol and title, cut to the width) in the header strip.
        const fs = Math.min(11, r.head * 0.75), fits = Math.floor(r.w / (fs * 0.62));
        const text = `${marked(n)} ${n.data("title") || ""}`;
        n.data({ ...base, fs, hm: (r.head - fs) / 2 + fs, label: fs >= 6 && fits > 3 ? (text.length > fits ? text.slice(0, fits - 1) + "…" : text) : "" })
         .addClass("cluster");
      } else {
        // Operator 2026-10-02: a leaf names its repo too, on its own line (vertical space is cheaper
        // than horizontal), and the text is fitted to the tile. Two lines if they fit at a readable
        // size, else the symbol alone, else nothing.
        const two = [n.data("repo"), marked(n)], f2 = fitFont(two, r.w, r.h), f1 = fitFont([marked(n)], r.w, r.h);
        const [fs, label] = f2 >= 7 ? [f2, two.join("\n")] : f1 >= 7 ? [f1, marked(n)] : [0, ""];
        n.data({ ...base, fs, label });
      }
    });
    cy.edges().forEach(e => { if (!e.hasClass("waits") && t.parent.get(e.source().id()) === e.target().id()) e.addClass("contained"); });
    // Step 4: the repo colour key, since fill is the repo here.
    const key = document.getElementById("repokey");
    key.innerHTML = [...new Set(ns.map(n => n.data("repo")))].sort().map(r =>
      `<span><i class="dot" style="background:${repoHue(r)}"></i>${esc(r)}</span>`).join(" ");
    key.hidden = false;
    let x = 0;
    cy.nodes().not(ns).not(".repo").forEach(n => { n.position({ x: x + n.outerWidth() / 2, y: H + 40 }); x += n.outerWidth() + 12; });
  });
}

// nemik:W135 (operator 2026-09-28: "a multi-headed overlapping dag/forest view ordered by
// nemik-rank"). Inside one repo box: the HEADS are its goals (nothing open in the box follows
// them); each hangs its prerequisites below it. Heads run left to right by the best nemik-rank
// position (rank_pos, from the server's composed order) among the work beneath them. A waypoint
// several heads share is drawn once, under the highest-ranked of them; its edges to the others
// cross over (the overlap). Within a layer, ready work sits in rank order.
function forest(box) {
  // Operator chips are not prerequisites: they are placed after, below the askers (see end).
  const chips = box.filter(".actor"), kids = box.not(".actor");
  const ids = new Set(kids.map(n => n.id()));
  const feeds = new Map(kids.map(n => [n.id(), new Set()]));   // dependent -> its prerequisites
  const follows = new Map(kids.map(n => [n.id(), new Set()])); // prerequisite -> its dependents
  kids.edgesWith(kids).forEach(e => {
    let [pre, dep] = [e.source().id(), e.target().id()];     // enables: prerequisite -> dependent
    if (e.hasClass("waits")) [pre, dep] = [dep, pre];         // waits: waiter -> what it waits for
    if (!ids.has(pre) || !ids.has(dep) || pre === dep) return;
    feeds.get(dep).add(pre); follows.get(pre).add(dep);
  });
  const rp = id => { const v = cy.getElementById(id).data("rank_pos"); return v === undefined ? Infinity : v; };
  const sym = id => cy.getElementById(id).data("label") || id;
  const bySal = document.getElementById("bySalience").checked;
  const sal = id => cy.getElementById(id).data("salience") || 0;
  const bySym = (a, b) => (sym(a) < sym(b) ? -1 : sym(a) > sym(b) ? 1 : 0);
  // nemik:W261: "salience order" ranks by the flow model alone (highest absorbed salience first);
  // otherwise by nemik-rank's composed position, where the band outranks the weight.
  const byRank = bySal ? (a, b) => sal(b) - sal(a) || rp(a) - rp(b) || bySym(a, b)
                       : (a, b) => rp(a) - rp(b) || bySym(a, b);
  const below = h => {  // everything under a head, following prerequisites
    const seen = new Set([h]), stack = [h];
    while (stack.length) for (const p of feeds.get(stack.pop())) if (!seen.has(p)) { seen.add(p); stack.push(p); }
    return seen;
  };
  let heads = [...ids].filter(id => follows.get(id).size === 0);
  if (!heads.length) heads = [...ids];  // a cycle with no exit: every member is its own head
  const trees = new Map(heads.map(h => [h, below(h)]));
  const best = h => Math.min(...[...trees.get(h)].map(rp));
  // A head's salience is the demand its whole cone carries: the sum over the ready cards beneath it.
  const carried = h => [...trees.get(h)].reduce((t, n) => t + sal(n), 0);
  heads.sort(bySal ? (a, b) => carried(b) - carried(a) || best(a) - best(b) || byRank(a, b)
                   : (a, b) => best(a) - best(b) || byRank(a, b));
  const owner = new Map();
  for (const h of heads) for (const n of trees.get(h)) if (!owner.has(n)) owner.set(n, h);
  for (const n of ids) if (!owner.has(n)) owner.set(n, heads[0]);
  // Layer = longest path down from a head, over the DAG left after a DFS drops back edges (a
  // cycle is cut at one edge, still drawn; without the cut, depth ran around it to its bound).
  const dag = new Map([...ids].map(n => [n, []])), mark = new Map();
  const cut = n => {
    mark.set(n, 1);
    for (const p of [...feeds.get(n)].sort()) {
      if (mark.get(p) === 1) continue;  // back edge
      dag.get(n).push(p);
      if (!mark.has(p)) cut(p);
    }
    mark.set(n, 2);
  };
  for (const h of heads) if (!mark.has(h)) cut(h);
  for (const n of [...ids].sort()) if (!mark.has(n)) cut(n);
  const topo = [], seen = new Set();
  const visit = n => { if (seen.has(n)) return; seen.add(n); for (const p of dag.get(n)) visit(p); topo.push(n); };
  for (const n of [...ids].sort()) visit(n);
  const depth = new Map([...ids].map(n => [n, 0]));
  for (const n of topo.reverse()) for (const p of dag.get(n)) depth.set(p, Math.max(depth.get(p), depth.get(n) + 1));
  const SEP = 8, ROW = 20;
  const h = kids.length ? Math.max(...kids.map(n => n.outerHeight())) : 20;
  // Each head's column, laid out at the origin: layers down, rank order across.
  const cols = [];
  for (const head of heads) {
    const layers = [];
    for (const n of ids) if (owner.get(n) === head) (layers[depth.get(n)] ||= []).push(n);
    const place = [];
    let w = 0;
    layers.forEach((layer, d) => {
      if (!layer) return;
      layer.sort(byRank);
      let x = 0;
      for (const id of layer) { const nw = cy.getElementById(id).outerWidth(); place.push([id, x + nw / 2, d * (h + ROW)]); x += nw + SEP; }
      w = Math.max(w, x - SEP);
    });
    if (place.length) cols.push({ place, w, h: layers.length * (h + ROW) - ROW });
  }
  // Shelves: columns keep rank order, left to right then top to bottom, wrapping near sqrt(area)
  // so one repo with many lone goals does not become a single very wide row.
  const limit = Math.max(...cols.map(c => c.w), 1.6 * Math.sqrt(cols.reduce((t, c) => t + (c.w + 3 * SEP) * (c.h + ROW), 0)));
  let x0 = 0, y0 = 0, shelfH = 0;
  for (const c of cols) {
    if (x0 > 0 && x0 + c.w > limit) { x0 = 0; y0 += shelfH + 2 * ROW; shelfH = 0; }
    for (const [id, x, y] of c.place) cy.getElementById(id).position({ x: x0 + x, y: y0 + y });
    x0 += c.w + 3 * SEP; shelfH = Math.max(shelfH, c.h);
  }
  // A chip goes below everything, under the mean x of the waypoints that ask it.
  let cx = 0;
  const floor = y0 + shelfH + h + 2 * ROW;
  chips.forEach(c => {
    const xs = c.connectedEdges().map(e => e.source().position().x).filter(Number.isFinite);
    const w = c.outerWidth();
    const want = xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : cx + w / 2;
    const x = Math.max(cx + w / 2, want);
    c.position({ x, y: floor });
    cx = x + w / 2 + SEP;
  });
}

const dist = (p, q) => Math.hypot(p.x - q.x, p.y - q.y);
const p95 = L => { if (!L.length) return 0; const s = [...L].sort((a, b) => a - b); return s[Math.min(s.length - 1, Math.floor(0.95 * s.length))]; };
const lexLess = (a, b) => { for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return a[i] < b[i]; return false; };

function tile() {
  const GAP = 60;
  const units = new Map();  // unit id -> { el: collection to shift, bb }
  // Inside each box, the rank forest (operator 2026-10-09: the only per-repo view; the dagre
  // alignment search it replaced is gone).
  cy.nodes(".repo").forEach(r => {
    const kids = r.children();
    forest(kids);
    units.set(r.id(), { el: kids, bb: kids.boundingBox() });
  });
  cy.nodes(".actor").orphans().forEach(a => units.set(a.id(), { el: a, bb: a.boundingBox() }));
  const unitOf = n => (n.isChild() ? n.parent().id() : n.id());
  const down = new Map([...units.keys()].map(k => [k, new Set()]));
  const linked = new Set();
  cy.edges().forEach(e => {
    let [u, v] = [unitOf(e.source()), unitOf(e.target())];
    if (u === v || !down.has(u) || !down.has(v)) return;
    if (e.hasClass("waits")) [u, v] = [v, u];  // waiter -> blocker points upstream
    down.get(u).add(v); linked.add(u); linked.add(v);
  });
  // Longest-path ranks over the DAG left after dropping DFS back edges.
  const state = new Map(), order = [];
  const visit = u => {
    state.set(u, 1);
    for (const v of down.get(u)) {
      if (state.get(v) === 1) down.get(u).delete(v);  // back edge: cut the cycle here
      else if (!state.has(v)) visit(v);
    }
    state.set(u, 2); order.push(u);
  };
  [...linked].sort().forEach(u => state.has(u) || visit(u));
  const rank = new Map();
  for (const u of order.reverse()) {
    rank.set(u, rank.get(u) || 0);
    for (const v of down.get(u)) rank.set(v, Math.max(rank.get(v) || 0, rank.get(u) + 1));
  }
  const last = Math.max(-1, ...rank.values()) + 1;
  for (const u of units.keys()) if (!rank.has(u)) rank.set(u, last);
  // Placement (operator 2026-09-28: shorten cross-box edges, minimize p95, and minimize the drawing's
  // area). Rows by rank left a wide box's row mostly empty beside narrow ones, so boxes are packed
  // skyline-style instead: in rank order, each goes as high as it can while staying below every box
  // it depends on and clear of every box already placed, as near as it can to the mean x of its
  // placed neighbours. Packing is tried at several target widths; the result kept minimizes
  // area/area0 + p95/p95_0 (each relative to the first packing, so neither unit dominates).
  const w = new Map([...units.keys()].map(k => [k, new Map()]));
  cy.edges().forEach(e => {
    const [u, v] = [unitOf(e.source()), unitOf(e.target())];
    if (u === v || !w.has(u) || !w.has(v)) return;
    w.get(u).set(v, (w.get(u).get(v) || 0) + 1);
    w.get(v).set(u, (w.get(v).get(u) || 0) + 1);
  });
  const up = new Map([...units.keys()].map(k => [k, []]));
  for (const [u, vs] of down) for (const v of vs) up.get(v).push(u);
  const size = u => units.get(u).bb;
  const crossEdges = [];
  cy.edges().forEach(e => {
    const [a, b] = [e.source(), e.target()], [u, v] = [unitOf(a), unitOf(b)];
    if (u === v || !w.has(u) || !w.has(v)) return;
    const rel = (n, k) => { const bb = size(k), p = n.position(); return { x: p.x - bb.x1, y: p.y - bb.y1 }; };
    crossEdges.push([u, rel(a, u), v, rel(b, v)]);
  });
  // A box may be mirrored left-right when that brings its cross-linked nodes nearer their partners
  // (a dagre layout is as valid mirrored); `flip` holds the boxes that are.
  let pos = new Map(), flip = new Set();
  const at = (u, r) => ({ x: pos.get(u).x + (flip.has(u) ? size(u).w - r.x : r.x), y: pos.get(u).y + r.y });
  const cross = () => crossEdges.map(([u, ru, v, rv]) => dist(at(u, ru), at(v, rv)));
  // nemik:W127: the area that counts is the viewport-shaped rectangle the drawing is fitted into,
  // not the drawing's own box: minimizing it maximizes the fit-to-screen scale. A portrait packing
  // on a landscape screen is width-poor and scale-limited by its height, whatever its own area.
  const VW = cy.width() || 1, VH = cy.height() || 1;
  const area = () => {
    let x1 = Infinity, y1 = Infinity, x2 = -Infinity, y2 = -Infinity;
    for (const [u, p] of pos) { x1 = Math.min(x1, p.x); y1 = Math.min(y1, p.y);
      x2 = Math.max(x2, p.x + size(u).w); y2 = Math.max(y2, p.y + size(u).h); }
    const s = Math.max((x2 - x1) / VW, (y2 - y1) / VH);
    return s * s * VW * VH;
  };
  const seq = [...units.keys()].sort((a, b) => rank.get(a) - rank.get(b) || size(b).w * size(b).h - size(a).w * size(a).h || (a < b ? -1 : 1));
  // k: how far a box will drop to stay near its neighbours (score = y + k * |x - target|).
  // prev: the previous packing, so a second pass also aims at neighbours not yet placed.
  // loose (nemik:W127): a box need only start no higher than the boxes it depends on, so it may sit
  // beside them rather than below. The strict rule stacks a long cross-repo chain into a column
  // whatever width is allowed (the rank forest's narrow boxes came out 2038x5352 on a 1360x1200
  // view); both are tried, and the score below picks.
  const pack = (W, k, prev, loose) => {
    pos = new Map();
    const placed = [];
    for (const u of seq) {
      const { w: uw, h: uh } = size(u);
      let minY = 0;
      for (const v of up.get(u)) if (pos.has(v)) minY = Math.max(minY, pos.get(v).y + (loose ? GAP : size(v).h + GAP));
      let s = 0, n = 0;
      for (const [v, c] of w.get(u)) {
        const p = pos.get(v) || (prev && prev.get(v));
        if (p) { s += c * (p.x + size(v).w / 2); n += c; }
      }
      const maxX = Math.max(0, W - uw);
      const target = n ? Math.min(maxX, Math.max(0, s / n - uw / 2)) : 0;
      const xs = new Set([target, 0, maxX]);
      for (const r of placed) { xs.add(r.x2 + GAP); xs.add(r.x1 - uw - GAP); }
      let best = null;
      for (const x of xs) {
        if (x < 0 || x > maxX) continue;
        let y = minY, moved = true;
        while (moved) {
          moved = false;
          for (const r of placed)
            if (x < r.x2 + GAP && r.x1 < x + uw + GAP && y < r.y2 + GAP && r.y1 < y + uh + GAP) { y = r.y2 + GAP; moved = true; }
        }
        const score = y + k * Math.abs(x - target);
        if (!best || score < best.score) best = { score, x, y };
      }
      pos.set(u, { x: best.x, y: best.y });
      placed.push({ x1: best.x, y1: best.y, x2: best.x + uw, y2: best.y + uh });
    }
  };
  const widest = Math.max(...seq.map(u => size(u).w));
  const side = Math.sqrt(seq.reduce((t, u) => t + (size(u).w + GAP) * (size(u).h + GAP), 0));
  let best = null, base = null;
  // Target widths around the side of a square of the same area, scaled toward the viewport's aspect.
  const aspect = Math.sqrt(VW / VH);
  for (const loose of [false, true]) for (const f of [1, 1.25, 1.5, 1.75, 2, 2.5, 3].map(f => f * aspect)) for (const k of [0.25, 1, 4]) for (const again of [false, true]) {
    pack(Math.max(widest, side * f), k, null, loose);
    if (again) pack(Math.max(widest, side * f), k, new Map(pos), loose);
    flip = new Set();
    // Mirror pass: flip any box whose mirror image lowers the cross-edge p95 (then total).
    const c = () => { const L = cross(); return [p95(L), L.reduce((a, b) => a + b, 0)]; };
    for (let round = 0, better = true; better && round < 4; round++) {
      better = false;
      for (const u of seq) { const before = c(); flip.add(u); if (lexLess(c(), before)) better = true; else flip.delete(u); }
    }
    const m = { p95: p95(cross()) || 1, area: area() };
    base ||= m;
    const score = m.area / base.area + m.p95 / base.p95;
    if (!best || score < best.score) best = { score, pos: new Map(pos), flip: new Set(flip) };
  }
  for (const u of best.flip) {
    const { el, bb } = units.get(u);
    el.forEach(n => n.position({ x: bb.x1 + bb.x2 - n.position().x, y: n.position().y }));
  }
  for (const [u, p] of best.pos) {
    const { el, bb } = units.get(u);
    el.shift({ x: p.x - bb.x1, y: p.y - bb.y1 });
  }
  cy.fit(undefined, 20);
}

// Each card's rings, as scope ids. The view chain is over what is drawn; the selected chain over the
// selected card's cone (everything it transitively waits on or enables), whatever is drawn.
function ringMap() {
  const rings = new Map();
  const put = (id, s) => rings.set(id, [...(rings.get(id) || []), s]);
  data.nodes.filter(isOpen).forEach(n => { if (n.on_path) put(n.id, "fleet"); if (n.on_path_repo) put(n.id, "repo"); });
  const deps = depEdges();
  viewChain = criticalSet(keepOpen, deps);
  viewChain.forEach(id => put(id, "view"));
  chainLen.view = viewChain.longest;
  delete chainLen.sel;
  if (selectedId && data.nodes.some(n => n.id === selectedId && isOpen(n))) {
    const open = new Set(data.nodes.filter(isOpen).map(n => n.id));
    const reach = (from, forward) => {
      const seen = new Set([from]), todo = [from];
      while (todo.length) {
        const cur = todo.pop();
        deps.forEach(([a, b]) => {
          const [x, y] = forward ? [a, b] : [b, a];
          if (x === cur && open.has(y) && !seen.has(y)) { seen.add(y); todo.push(y); }
        });
      }
      return seen;
    };
    const cone = new Set([...reach(selectedId, true), ...reach(selectedId, false)]);
    const selChain = criticalSet(cone, deps);
    selChain.forEach(id => put(id, "sel"));
    chainLen.sel = selChain.longest;
  }
  if (document.getElementById("pathkey").innerHTML) pathKey();  // after the first graph (W419)
  return rings;
}

function ringSvg(ele) {
  const on = ele.data("rings") || [], rs = SCOPES.filter(s => on.includes(s.id)), k = rs.length;
  const w = ele.outerWidth() + 2 * PAD * k, h = ele.outerHeight() + 2 * PAD * k;
  const rects = rs.map((s, i) => {
    const x = PAD * (k - i - 1) + 1.5;
    return `<rect x="${x}" y="${x}" width="${w - 2 * x}" height="${h - 2 * x}" rx="${6 + PAD * (i + 1)}" fill="none" stroke="${scopeColor(s.color)}" stroke-width="${s.width}" stroke-dasharray="${scopeDash(s)}"/>`;
  }).join("");
  return "data:image/svg+xml;utf8," + encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}">${rects}</svg>`);
}
const ringW = ele => ele.outerWidth() + 2 * PAD * (ele.data("nrings") || 0) + "px";
const ringH = ele => ele.outerHeight() + 2 * PAD * (ele.data("nrings") || 0) + "px";

// nemik:W340: a view whose labels are smaller than MIN_LABEL_PX on screen is not legible (the all-repos fit
// shrinks the 10px label to about 4). The first fit never goes below that floor: when fitting everything
// would, it shows the repo box carrying the most salience at the floor, and says how to see the rest.
const MIN_LABEL_PX = 8, LABEL_FONT_PX = 10;
function fitReadable(treemapOn, repos) {
  // nemik:W433: the live region holds the message only; its "fit all" button sits beside it, so a
  // screen reader announces the note once instead of re-reading the injected button with it.
  const note = document.getElementById("legnote"), act = document.getElementById("legact");
  note.textContent = "";
  act.textContent = "";
  cy.fit(cy.elements(":visible"), 20);
  const floor = MIN_LABEL_PX / LABEL_FONT_PX;
  if (treemapOn || cy.zoom() >= floor) return;
  // nemik:W383 (W380 refuted the old early return on one repo): with one repo drawn, including a pick
  // restored from the last visit, show its top-left corner at the floor, not the whole box too small.
  let bb, what;
  if (repos.length < 2) {
    bb = cy.elements(":visible").boundingBox();
    what = `${repos[0] || "this view"} at readable size; pan to see the rest.`;
  } else {
    const load = r => data.nodes.filter(n => n.repo === r).reduce((s, n) => s + (n.salience || 0), 0);
    const focus = [...repos].sort((a, b) => load(b) - load(a) || (a < b ? -1 : 1))[0];
    const box = cy.getElementById("repo:" + focus);
    if (!box.length) return;
    bb = box.boundingBox();
    what = `${focus} at readable size; ${repos.length - 1} more repos off-screen.`;
  }
  cy.viewport({ zoom: floor, pan: { x: 20 - bb.x1 * floor, y: 20 - bb.y1 * floor } });
  note.textContent = what;  // text, not markup: the repo name needs no escaping here
  act.innerHTML = `<button id="fitall" type="button">fit all (too small to read)</button>`;
  document.getElementById("fitall").onclick = () => {
    cy.fit(cy.elements(":visible"), 20); note.textContent = ""; act.textContent = "";
  };
}

// nemik:W384: WCAG contrast. Each filled card and lane chip gets whichever of near-black or white text
// has the higher contrast ratio against its rendered fill, so every state colour in either theme clears
// 4.5:1 without a hand-picked pairing per token. (Tiles and unclaimed placeholders style their own text.)
const INKS = ["#111111", "#ffffff"];
// nemik:W829: the luminance is core/text.py through core.wasm (0 without the module).
function luminance(css) { return coreWasm ? coreWasm.luminance(css) : 0; }
const contrast = (a, b) => { const [x, y] = [luminance(a), luminance(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
const hexRgb = h => `rgb(${parseInt(h.slice(1, 3), 16)},${parseInt(h.slice(3, 5), 16)},${parseInt(h.slice(5, 7), 16)})`;
function labelInk() {
  cy.nodes("[symbol], .actor").filter(n => !n.hasClass("tile") && n.data("state") !== "unclaimed").forEach(n => {
    const fill = n.style("background-color");
    const best = INKS.reduce((a, b) => (contrast(hexRgb(b), fill) > contrast(hexRgb(a), fill) ? b : a));
    n.style("color", best);
  });
}

function refreshRings() {
  const rings = ringMap();
  cy.nodes("[symbol]").forEach(n => { const r = rings.get(n.id()) || []; n.data({ rings: r, nrings: r.length }); });
  markChainEdges();
  cy.style().update();
}
// nemik:W482: draw the dependencies that make up the view's longest chains, so a chain can be followed
// from one repo box into the next (each box shows only its piece). An edge is on a chain when both
// ends are and they are consecutive on it: one step down from the prerequisite, one step up to it.
function markChainEdges() {
  cy.edges().removeClass("onchain");
  const chain = viewChain;
  if (!chain) return;
  const on = new Set(chain);
  cy.edges().forEach(e => {
    const [pre, dep] = e.hasClass("waits") ? [e.target().id(), e.source().id()] : [e.source().id(), e.target().id()];
    if (on.has(pre) && on.has(dep) && chain.down.get(pre) === chain.down.get(dep) + 1
        && chain.up.get(dep) === chain.up.get(pre) + 1) e.addClass("onchain");
  });
}


// nemik:W335: one halo ring per path scope, drawn together (innermost first), each with its own colour AND
// dash so the scope never rests on hue alone: the fleet's longest chain, this repo's, the visible set's,
// and the selected card's cone. Colours are Okabe-Ito; "ink" follows the theme.
const PAD = 4;
// nemik:W419: the ruler-sequence patterns come from the server (graph.json `ruler`, W418), generated by
// mtools' mikemol.rulerseq (mtools:W1048, paperkit's emit_f hosted): `ruler.f[n]` is F(n), injective and of
// length n, so it encodes any natural; `ruler.motif[k]` is the order-k motif. The page only renders them.
// tests/test_layout.py pins the drawn motifs to paperkit's published family.
const RULER_DOT = "·";
const rulerF = n => (data && data.ruler && data.ruler.f[n]) || "";
const rulerMotif = k => (data && data.ruler && data.ruler.motif[k]) || "";
// A motif as an SVG stroke-dasharray: a dot is a short stroke, a dash a long one, each then a gap.
const rulerDash = motif => [...motif].map(c => (c === RULER_DOT ? "1.5 2.5" : "6 2.5")).join(" ");
// Each scope's ring carries its own motif order (broadest scope, longest motif), so no two scopes share a
// pattern, whatever their colours (WCAG 1.4.1; W380 refuted the old fleet/sel pair, both solid).
const SCOPES = [
  { id: "fleet", color: "--ring-fleet", order: 3, width: 2, label: "longest chain, fleet" },
  { id: "repo", color: "--ring-repo", order: 2, width: 2, label: "longest chain, its repo" },
  { id: "view", color: "--ring-view", order: 1, width: 2.5, label: "longest chain, this view" },
  { id: "sel", color: "ink", order: 0, width: 3, label: "longest chain, selected card's cone" },
];
// nemik:W437: a scope colour is a theme token (light and dark each reach 3:1 against --bg)
const scopeColor = c => (c === "ink" ? css("--ink") : c.startsWith("--") ? css(c) : c);
const scopeDash = s => rulerDash(rulerMotif(s.order));
// The legend waits for the first graph, since its patterns arrive with it (W419).
// nemik:W482 (operator 2026-10-13: chains of 2 and 3 both ringed "longest, this view"): the view and
// selection chains carry their length, and say that a chain runs on between repo boxes, where each
// box shows only its piece of it.
const chainLen = {};
let viewChain = null;  // the cards on the view's longest chains, with their heights (criticalSet)
const pathKey = () => { document.getElementById("pathkey").innerHTML = SCOPES.map(s =>
  `<span><svg width="26" height="8" aria-hidden="true"><line x1="1" y1="4" x2="25" y2="4" stroke="${scopeColor(s.color)}" stroke-width="${s.width}" stroke-dasharray="${scopeDash(s)}"/></svg>${s.label}${chainLen[s.id] ? ` (${chainLen[s.id]} cards, across repo boxes)` : ""}</span>`).join(""); };

// nemik:W344: the dependency order is a poset, so tied longest chains are alternatives, not a ranking. This is
// every card among `ids` that lies on SOME longest chain (zero slack); `deps` are [prerequisite, dependent]
// pairs. A cycle is cut where the walk meets itself. Nothing depends on iteration order.
// nemik:W822 (goal W812): the computation is src/nemik/core/chains.py, compiled by Codon to
// core.wasm, the same code nemik-critical runs natively. This is its facade: it maps the page's
// ids and pairs to the module and back to the shape the callers read. wasm64 (memory64) only, no JS
// copy (nemik:W814): a browser without it draws no chain marks and says so (loadCore).
let coreWasm = null, coreFailed = false;
async function loadCore() {
  if (coreWasm || coreFailed) return;
  try {
    coreWasm = NemikWasm.instantiate(await (await fetch("core.wasm")).arrayBuffer());
  } catch (e) {
    coreFailed = true;
    document.getElementById("chainsoff").hidden = false;
  }
}
function criticalSet(ids, deps) {
  const found = coreWasm
    ? coreWasm.chains([...ids], deps)
    : { length: 0, up: new Map(), down: new Map(), paths: new Map() };
  const on = [...ids].filter(id => found.paths.has(id));
  on.longest = found.length;  // nemik:W482: the legend says how long "longest" is
  on.up = found.up; on.down = found.down;  // and its edges can be found (markChainEdges)
  return on;
}

const isOpen = n => n.symbol && !["done", "dropped"].includes(n.state);
const depEdges = () => data.edges.filter(e => e.kind === "enables" || e.kind === "waits")
  .map(e => (e.kind === "enables" ? [e.source, e.target] : [e.target, e.source]));
let keepOpen = new Set();
const expanded = new Set();  // nemik:W350: umbrellas the reader opened with a double-click
// nemik:W727: how the card list orders its cards: by salience ("rank") or highest symbol number first ("newest")
let listMode = "rank";
// nemik:W470: which clock the recent order reads: last_worked, issued or last_activity (a card with
// none of it sorts last)
let listClock = "last_worked";
const symbolNumber = n => Number((n.data("symbol") || "").replace(/\D/g, "")) || 0;
// nemik:W734: "critical" puts first the card with the longest chain of cards beneath it (what it enables,
// transitively), computed over the drawn graph each time the list is built in that mode.
let chainOf = new Map();
function computeChains() {
  const next = new Map();
  for (const e of cy.edges().toArray()) {
    if (e.hasClass("waits")) continue;
    const from = e.source().id();
    if (!next.has(from)) next.set(from, []);
    next.get(from).push(e.target().id());
  }
  const memo = new Map();
  const len = (id, path) => {
    if (memo.has(id)) return memo.get(id);
    if (path.has(id)) return 0;  // a cycle adds nothing
    path.add(id);
    let d = 0;
    for (const t of next.get(id) || []) d = Math.max(d, 1 + len(t, path));
    path.delete(id);
    memo.set(id, d);
    return d;
  };
  chainOf = new Map(cy.nodes("[symbol]").toArray().map(n => [n.id(), len(n.id(), new Set())]));
}
const LIST_ORDER = {
  rank: (a, b) => (b.data("salience") || 0) - (a.data("salience") || 0),
  newest: (a, b) => symbolNumber(b) - symbolNumber(a),
  critical: (a, b) => (chainOf.get(b.id()) || 0) - (chainOf.get(a.id()) || 0),
  // nemik:W736: each repo's cards together (repos by name), heaviest first inside a repo
  repo: (a, b) => String(a.data("repo")).localeCompare(String(b.data("repo"))) || LIST_ORDER.rank(a, b),
  // nemik:W740: the card worked on most recently first; a card with no last_worked sorts last
  recent: (a, b) => String(b.data(listClock) || "").localeCompare(String(a.data(listClock) || "")),
  // nemik:W738: the cards waiting on the operator first, then by rank
  asks: (a, b) => Number(b.data("blocked_kind") === "human") - Number(a.data("blocked_kind") === "human") || LIST_ORDER.rank(a, b),
};
const closedTree = new Set();  // nemik:W725: card-list rows the reader folded (open unless listed)


const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const LANE = { "needs-you": "needs you", "no-command": "no command yet", answered: "already answered", condition: "waiting on a condition", unstated: "no ask stated" };
const STATES = ["ready", "working", "blocked", "done", "dropped", "unclaimed"];
const color = s => css("--" + (STATES.includes(s) ? s : "other"));
let data = null, cy = null, selectedId = null, liveness = {}, lastMode = null;

// nemik:W381 (W380 refuted 'state not by colour alone'): each state but ready also carries a glyph at the
// front of the card's label, so state reads without its fill colour, in the graph and the treemap alike.
// The glyphs are ones every base font carries (U+25B8, U+2016, U+221A, U+00D7): a glyph a font lacks draws
// as a wide placeholder box, which widened labels only under the gate's headless Chrome.
// nemik:W661: a state outside these six (colour --other) carries "* ", ASCII and this role only ("? " is the
// unclaimed label's), so the only state with no mark is ready (WCAG 1.4.1, judged by data/wcag.rego).
const STATE_MARK = { ready: "", working: "▸ ", blocked: "‖ ", done: "√ ", dropped: "× ", other: "* " };
// nemik:W456: what an umbrella's label carries after its symbol, each glyph used in this role only (the
// roll-up count once reused the working mark: "‖ W503 ▸ 3" read as working). ASCII "+" needs no font.
const ROLLUP_MARK = " +", EXPANDED_MARK = " ▾";
// nemik:W477: stored ready, but an open card enables it, so it waits (nemik:W465). ASCII, this role only.
const BEHIND_MARK = "~ ";
// nemik:W684: a ready leaf with no manifest cannot be stacked; the Selected panel says so. Its drawn
// indicator is the warning badge (nemik:W688), not a state of its own: a ready card drawn with another
// state's fill and mark broke the one-mark-per-state and second-channel rules (the gate's browser tests).
const needsManifest = d => d.state === "ready" && d.needs_manifest === true;
// nemik:W688 (operator 2026-10-18, 695f3e0a line 79877: a card that throws warnings on the CLI carries a
// visual indicator in the UI): "!" and the count after a card's symbol, "!!" when one is a Violation.
// ASCII, this role only; the count is the text and the messages are in the Selected panel, so colour
// carries nothing here. The payload's rows are the CLI's (nemik:W687), so a new shape shows up unaided.
const warnMark = d => { const w = d.warnings || []; return w.length ? `${w.some(x => x.severity === "Violation") ? "!!" : "!"}${w.length}` : ""; };
// nemik:W767: a card a queued or gating commit stack names is being worked, whatever its status says
const stateMark = d => (d.stage === "gating" ? STATE_MARK.working : d.state === "ready" && d.behind_open ? BEHIND_MARK : STATE_MARK[STATES.includes(d.state) ? d.state : "other"] || "");

function esc(s) { return String(s).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c])); }

// nemik:W497: a panel is rewritten only when its markup changed, so an unrelated change elsewhere never
// rebuilds it under the reader's focus, scroll or text selection. Every write to a panel goes through
// here; an element something else has touched since (its serialization moved) is repainted regardless.
const painted = new Map();  // element -> {html, dom}: the markup last written and how the DOM then read it
function paint(target, html) {
  const el = typeof target === "string" ? document.getElementById(target) : target;
  const last = painted.get(el);
  if (last && last.html === html && el.innerHTML === last.dom) return false;
  el.innerHTML = html;
  painted.set(el, { html, dom: el.innerHTML });
  return true;
}

