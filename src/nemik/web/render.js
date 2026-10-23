// nemik:W799: a part of the page's script, moved out of index.html (docs/web-modules.md).
// A classic script run before index.html's own: only definitions live here, no statement that
// touches the page when it loads. Its functions and constants stay global, as they were.

// nemik:W496/W498: a view change you made (a toggle, a roll-up, a repo) lays the graph out afresh; the 60 s
// poll (render(true)) follows what changed in place when it can, and leaves the layout alone.
function draw() { render(false); }
function render(poll) {
  const showDone = document.getElementById("showDone").checked;
  const showNoise = document.getElementById("showNoise").checked;
  const keep = new Set(data.nodes.filter(n =>
    wants(n.repo) && (showDone || !["done", "dropped"].includes(n.state))).map(n => n.id));
  // waits-for edges (resolved from blocked_on) may point at another repo, a waypoint there, or the operator:
  // pull the target repo in so a cross-repo dependency is visible even under a repo filter.
  // A repo target is drawn as its own "ws:" node, not the repo's compound box: dagre cannot lay
  // out edges into compound parents.
  const byId = new Map(data.nodes.map(n => [n.id, n]));
  // nemik:W336: with repos picked, the open cards they transitively wait on in OTHER repos, `depth` hops out,
  // are drawn too as context ("ghosts"): not just what a repo is blocked on, but what that is blocked on.
  const ghosts = new Set();
  if (picked.size) {
    const hops = +document.getElementById("depth").value, deps = depEdges();
    let frontier = new Set(keep);
    for (let d = 0; d < hops && frontier.size; d++) {
      const next = new Set();
      deps.forEach(([blocker, waiter]) => {
        const b = byId.get(blocker);
        if (frontier.has(waiter) && b && isOpen(b) && !keep.has(blocker)) { next.add(blocker); }
      });
      next.forEach(id => { keep.add(id); ghosts.add(id); });
      frontier = next;
    }
  }
  // nemik:W350: milestone roll-up. With "roll up umbrellas" on, an umbrella (an open card with two or
  // more open prerequisites in its own repo) hides the work beneath it that nothing else needs, and its
  // label counts what it hides; double-click it to expand or collapse it again.
  const hidden = new Set(), rolled = new Map();
  if (document.getElementById("rollup").checked) {
    const deps = depEdges();
    const preds = new Map(), dependents = new Map();
    deps.forEach(([p, d]) => {
      if (!preds.has(d)) preds.set(d, []);
      preds.get(d).push(p);
      if (!dependents.has(p)) dependents.set(p, []);
      dependents.get(p).push(d);
    });
    const open = id => byId.has(id) && isOpen(byId.get(id));
    const umbrellas = [...keep].filter(id => open(id)
      && (preds.get(id) || []).filter(p => open(p) && byId.get(p).repo === byId.get(id).repo).length >= 2);
    for (const u of umbrellas) {
      if (expanded.has(u) || hidden.has(u)) continue;
      const cone = new Set(), todo = [u];
      while (todo.length) for (const p of preds.get(todo.pop()) || []) if (open(p) && !cone.has(p) && p !== u) { cone.add(p); todo.push(p); }
      // keep only what nothing outside the umbrella's cone needs, to a fixed point
      let changed = true;
      while (changed) {
        changed = false;
        for (const c of [...cone]) if ((dependents.get(c) || []).some(d => d !== u && !cone.has(d) && open(d))) { cone.delete(c); changed = true; }
      }
      if (!cone.size) continue;
      cone.forEach(c => { hidden.add(c); keep.delete(c); });
      rolled.set(u, cone.size);
    }
  }
  // A block ends at the blocker's claiming waypoint, or at an "unclaimed" placeholder in the
  // blocker's box; pull that end in even when its repo is filtered out, so the block stays visible.
  const waits = data.edges.filter(e => e.kind === "waits" && keep.has(e.source) && !hidden.has(e.target)
      // nemik:W467: the no-command lane shows by default too: it is the owners' debt, kept in sight.
      && (e.target.startsWith("operator:") ? (showNoise || e.target === "operator:needs-you" || e.target === "operator:no-command")
        : ghosts.has(e.source) ? keep.has(e.target) : byId.has(e.target)));
  waits.forEach(e => { if (byId.has(e.target) && !ghosts.has(e.source)) keep.add(e.target); });
  // nemik:W120: one operator lane per repo box, not one for the fleet. A single lane was a hub
  // every ask converged on, so its edges were the longest on the page whatever the layout did
  // (the top 5% of edge lengths, measured). A chip inside each box keeps those edges short; clicking
  // any chip still opens the whole fleet's lane in the side panel.
  const chip = e => `${e.target}@${byId.get(e.source).repo}`;
  waits.forEach(e => { if (e.target.startsWith("operator:")) e.chip = chip(e); });
  const actors = [...new Set(waits.filter(e => e.chip).map(e => e.chip))].sort();
  const treemapOn = document.getElementById("treemap").checked;
  const bySal = document.getElementById("bySalience").checked;  // nemik:W261: salience on the label
  // nemik:W464: a waiting card absorbs no salience (only the frontier does), so its label read blank
  // though demand runs through it. What it carries is the demand leaving it toward the frontier (its
  // own plus what passes through), summed once per dependency (one can be drawn as both a waits and
  // an enables edge). Along a chain it ends equal to what the frontier card absorbs.
  const through = new Map(), seenDep = new Set();
  for (const e of data.edges) {
    if (!e.current || (e.kind !== "waits" && e.kind !== "enables")) continue;
    const [needs, pre] = e.kind === "waits" ? [e.source, e.target] : [e.target, e.source];
    if (seenDep.has(needs + " " + pre)) continue;
    seenDep.add(needs + " " + pre);
    through.set(needs, (through.get(needs) || 0) + e.current);
  }
  const demandLabel = n => !bySal ? "" : n.salience ? ` · ${+n.salience.toFixed(1)}`
    : through.get(n.id) ? ` · (${+through.get(n.id).toFixed(1)})` : "";
  const repos =treemapOn ? [] : [...new Set(data.nodes.filter(n => keep.has(n.id)).map(n => n.repo))];
  keepOpen = new Set(data.nodes.filter(n => keep.has(n.id) && isOpen(n)).map(n => n.id));
  const ringsOf = ringMap();
  // nemik:W388: each wait line's natural is its source's place (1..m, by id) among the lines into the same
  // drawn blocker, so the pattern is generated from the (source, target) pair and stays short.
  const fanOf = new Map(), fans = new Map();
  waits.forEach(e => { const t = e.chip || e.target; if (!fans.has(t)) fans.set(t, []); fans.get(t).push(e); });
  fans.forEach(list => list.sort((a, b) => (a.source < b.source ? -1 : 1)).forEach((e, i) => fanOf.set(e, i + 1)));
  const els = [
    // A repo box counts the unclaimed blocks inside it: each one is that repo's move.
    // Its border reads liveness (asleep/idle/awake), from the same roster the Wake panel
    // shows -- a repo nothing is waiting on has no roster row and stays "unknown".
    ...repos.map(r => {
      const k = data.nodes.filter(n => keep.has(n.id) && n.repo === r && n.state === "unclaimed").length;
      const name = wants(r) ? r : `${r} (context)`;
      return { data: { id: "repo:" + r, label: k ? `${name} · ${k} unclaimed` : name, live: liveness[r] || "unknown" }, classes: "repo" };
    }),
    ...data.nodes.filter(n => keep.has(n.id)).map(n => {
      const e = n.effort || {}, total = (e.forecast || 0) + (e.interrupt || 0) + (e.unclassified || 0);
      return { data: { ...n, parent: treemapOn ? undefined : "repo:" + n.repo, label: n.state === "unclaimed" ? `? ${n.for}` : stateMark(n) + n.symbol + warnMark(n) + demandLabel(n)
          + (rolled.has(n.id) ? `${ROLLUP_MARK}${rolled.get(n.id)}` : expanded.has(n.id) ? EXPANDED_MARK : ""),
        rollup: rolled.get(n.id) || 0,
        fill: color(n.state), border: total ? 1 + 6 * (e.interrupt || 0) / total : 1,
        rings: ringsOf.get(n.id) || [], nrings: (ringsOf.get(n.id) || []).length,
        ghost: !wants(n.repo) } };
    }),
    ...actors.map(a => {
      const [cat, r] = a.slice(9).split("@");
      const n = (data.operator || []).filter(x => x.category === cat && x.ref.split(":")[0] === r).length;
      return { data: { id: a, parent: treemapOn ? undefined : "repo:" + r, label: `${LANE[cat]} (${n})`, lane: cat }, classes: "actor operator " + cat };
    }),
    ...data.edges.filter(e => e.kind === "enables" && keep.has(e.source) && keep.has(e.target))
      // nemik:W496: an edge's id is its ends, not its place in the list, so the poll can be diffed against
      // what is drawn (an index id shifted every later edge when one appeared)
      .map(e => ({ data: { id: `e|${e.source}|${e.target}`, source: e.source, target: e.target, current: bySal ? e.current : undefined }, classes: e.satisfied ? "satisfied" : "" })),
    ...waits.map(e => ({ data: { id: `w|${e.source}|${e.chip || e.target}`, source: e.source, target: e.chip || e.target, current: bySal ? e.current : undefined,
      fan: fanOf.get(e), dash: rulerDash(rulerF(fanOf.get(e))).split(" ").map(Number) },
      classes: "waits" + (e.satisfied ? " satisfied" : "") })),
  ];
  // Keep the reader's viewport across a redraw; only the first draw fits the graph (nemik:W119).
  // The viewport is kept only across a redraw of the SAME view: a changed layout mode or repo
  // filter puts every node somewhere else, and the old zoom/pan then showed one tile scaled off the
  // page (operator 2026-10-02, treemap toggle).
  const mode = [treemapOn, document.getElementById("bySalience").checked, [...picked].sort().join(","), document.getElementById("depth").value,
    document.getElementById("rollup").checked].join("|");
  if (poll && cy && mode === lastMode && !treemapOn && patchDraw(els)) {
    afterDraw(keep, repos);
    return;
  }
  const view = cy && mode === lastMode ? { zoom: cy.zoom(), pan: { ...cy.pan() } } : null;
  lastMode = mode;
  layoutStale = 0;
  document.getElementById("relayout").hidden = true;
  if (cy) cy.destroy();
  cy = cytoscape({
    container: document.getElementById("cy"), elements: els,
    layout: { name: "preset" },    style: [
      // nemik:W125: the label sits INSIDE its shape (operator 2026-09-28), sized to fit it, so no
      // space below each node is reserved and nothing else can cover the text. Its colour is set after
      // styling by labelInk() (W384): the page background was 2.6:1 on some fills, not 4.5:1.
      { selector: "node", style: { "background-color": "data(fill)", label: "data(label)", color: css("--bg"),
        "font-size": 10, "font-weight": "bold", "text-valign": "center", "text-halign": "center",
        width: "label", height: "label", padding: 4, shape: "round-rectangle",
        "border-width": "data(border)", "border-color": css("--interrupt") } },
      { selector: 'node[state = "dropped"]', style: { color: css("--ink") } },
      { selector: 'node[state = "unclaimed"]', style: { "font-size": 11, "border-style": "dashed", "border-width": 3,
        "border-color": css("--unclaimed"), "background-opacity": 0.15, color: css("--ink") } },  // W903
      // A diamond's text box is its middle half, so it needs more padding to hold the same label.
      { selector: 'node[minted_during = "interrupt"]', style: { shape: "diamond", padding: 11 } },
      { selector: ".repo", style: { "background-opacity": 0.04, "background-color": css("--ink"), "border-width": 1,
        "border-color": css("--line"), label: "data(label)", "text-valign": "top", "text-halign": "center",
        "font-size": 12, color: css("--muted") } },
      { selector: '.repo[live = "asleep"]', style: { "border-width": 2, "border-color": css("--blocked") } },
      { selector: '.repo[live = "idle"]', style: { "border-width": 2, "border-color": css("--interrupt") } },
      { selector: '.repo[live = "awake"]', style: { "border-width": 2, "border-color": css("--ready") } },
      { selector: "edge", style: { width: 1, "line-color": css("--edge"), "target-arrow-color": css("--edge"),
        "target-arrow-shape": "triangle", "curve-style": "bezier", "arrow-scale": 0.7 } },
      // nemik:W388: a wait line's dash is its identity, the ruler-sequence encoding (emitF) of its source's
      // place among the lines into the same blocker, so lines crowding one card never share a pattern and
      // each decodes back to its source. "This is a wait" is carried by colour AND the blocking-bar (tee)
      // arrowhead, not the dash.
      { selector: "edge.waits", style: { "line-style": "dashed", "line-dash-pattern": "data(dash)",
        "line-color": css("--blocked"), "target-arrow-color": css("--blocked"), "target-arrow-shape": "tee", width: 1.5 } },
      // nemik:W56/W57: the upstream end is done, so this edge no longer holds anything back.
      { selector: "edge.satisfied", style: { opacity: 0.25, "line-style": "solid" } },
      // nemik:W264: with "salience order" on, an edge is as wide as the flow that crossed it.
      { selector: "edge[current > 0]", style: { width: "mapData(current, 0, 12, 1.5, 7)" } },
      // nemik:W336: a card shown only as context (its repo is not picked) is dashed and dim.
      // nemik:W385 (W380 refuted the old cue): a DOUBLE border, a shape no other card uses (unclaimed is
      // dashed), at full opacity so its label keeps W384's 4.5:1 contrast; the repo box says "(context)".
      { selector: "node[?ghost]", style: { "border-style": "double", "border-width": 4, "border-color": css("--muted") } },
      // nemik:W322, W335: the cards on a longest open chain (nemik-critical) carry one ring per scope.
      { selector: "node[nrings > 0]", style: { "background-image": ringSvg, "background-fit": "none", "background-clip": "none",
        "background-width": ringW, "background-height": ringH, "background-position-x": "50%", "background-position-y": "50%",
        "bounds-expansion": PAD * 4 + 4 } },
      { selector: ".actor", style: { shape: "round-rectangle", "background-color": css("--other"),
        label: "data(label)", width: "label", height: 20, padding: 6, "text-halign": "center",
        "text-valign": "center", "text-margin-x": 0, color: css("--bg"), "font-size": 11, "border-width": 0 } },
      { selector: ".operator", style: { "background-color": css("--blocked") } },
      { selector: ".operator.answered, .operator.condition", style: { "background-color": css("--done") } },
      { selector: ".operator.unstated", style: { "background-color": css("--interrupt") } },
      // nemik:W467: the owner's debt, not the operator's: the "other" fill and a dashed edge, so it
      // differs from needs-you without relying on colour alone.
      { selector: ".operator.no-command", style: { "background-color": css("--other"), "border-width": 2,
        "border-style": "dashed", "border-color": css("--ink") } },
      { selector: "edge.rank", style: { display: "none" } },
      // nemik:W180: a tile is a rectangle of its computed size, label top-left, repo as border colour.
      // Step 3: fill = repo hue, tiles abut with a thin page-coloured separator, text scaled to fit;
      // state reads as opacity (blocked dim) and a working tile's thicker separator.
      { selector: "node.tile", style: { shape: "rectangle", width: "data(tw)", height: "data(th)", padding: 0,
        "text-wrap": "wrap", "line-height": 1.2,
        "text-valign": "center", "text-halign": "center", "font-size": "data(fs)", "border-width": 1,
        "border-color": css("--bg"), "background-color": "data(repoColor)", "background-opacity": 1, color: "#fff",
        "text-outline-width": 1, "text-outline-color": "#0008" } },
      // Step 6: a cluster is a frame tinted with its repo, label in its header (graphviz-style); it
      // draws under its children (z by depth).
      { selector: "node.tile", style: { "z-index-compare": "manual", "z-index": "data(depth)" } },
      { selector: "node.tile.cluster", style: { "background-opacity": 0.12, "border-width": 1.5,
        "border-color": "data(repoColor)", "text-valign": "top", "text-margin-y": "data(hm)", color: css("--ink"),
        "text-outline-width": 0 } },
      // nemik:W390: a tile whose label would draw under MIN_LABEL_PX shows none rather than an unreadable one
      { selector: "node.tile.tinylabel", style: { label: "" } },
      { selector: 'node.tile[state = "blocked"]', style: { "background-opacity": 0.45 } },
      { selector: 'node.tile[state = "working"]', style: { "border-width": 3, "border-color": css("--ink") } },
      { selector: "edge.contained", style: { display: "none" } },
      { selector: "edge.cross", style: { opacity: 0.08 } },
      { selector: "edge.cross.lit", style: { opacity: 1, "z-index": 10 } },
      // nemik:W482: a longest-chain edge, in the view ring's colour, drawn even between repo boxes
      { selector: "edge.onchain", style: { opacity: 1, "z-index": 9, width: 3,
        "line-color": css("--ring-view"), "target-arrow-color": css("--ring-view") } },
      { selector: ":selected", style: { "overlay-opacity": 0.15 } },
      // nemik:W479: the card the Cards list's keyboard focus is on, a ring apart from selection (and from
      // the chain rings): a wide, dotted outline in the ink colour, drawn outside the node
      { selector: "node.listfocus", style: { "outline-width": 4, "outline-style": "dotted",
        "outline-color": css("--ink"), "outline-offset": 3 } },
    ],
  });
  document.getElementById("repokey").hidden = true;
  if (treemapOn) treemap(); else tile();
  labelInk();
  // The layout runs after cytoscape's own initial fit, so a fresh view is fitted here, to what the
  // layout actually placed.
  if (view) { cy.zoom(view.zoom); cy.pan(view.pan); } else fitReadable(treemapOn, repos);
  // nemik:W390: treemap tiles size their own text to fit (data(fs)), so a small tile's label shrinks with it.
  // At every zoom, a label that would draw under the floor is hidden instead, and the status line says how
  // many and where they are read: the Cards list (W435) names every card drawn.
  if (treemapOn) {
    const tileLabels = () => {
      let hidden = 0;
      cy.nodes(".tile").forEach(n => {
        const tiny = (n.data("fs") || LABEL_FONT_PX) * cy.zoom() < MIN_LABEL_PX;
        n.toggleClass("tinylabel", tiny);
        if (tiny) hidden++;
      });
      document.getElementById("legnote").textContent = hidden
        ? `${hidden} tiles too small to label at this zoom; zoom in, or read them in Cards.` : "";
    };
    tileLabels();
    cy.on("zoom", tileLabels);
  }
  // nemik:W88: an edge between two boxes is faint until one of its ends is hovered or selected,
  // or "show all cross-repo edges" is on. Inside a box, edges stay as they are.
  markCross();
  cy.on("mouseover", "node", ev => ev.target.connectedEdges(".cross").addClass("lit"));
  cy.on("mouseout", "node", light);
  // nemik:W462: the card popover, the hovercard convention: it opens after a 500 ms rest, stays while
  // the pointer is on the card or on the popover, closes 300 ms after it leaves both, and Esc
  // dismisses it (WCAG 1.4.13: dismissible, hoverable, persistent).
  cy.on("mouseover", "node[symbol]", ev => popSoon(ev.target));
  cy.on("mouseout", "node[symbol]", () => popLater());
  cy.on("pan zoom", () => popHide());
  cy.on("select unselect", "node", light);
  cy.on("tap", "node[symbol]", ev => selectCard(ev.target.id()));
  cy.on("tap", "node[lane]", ev => lane(ev.target.data("lane")));
  // nemik:W350: double-click an umbrella to expand or collapse what it rolls up.
  cy.on("dbltap", "node[symbol]", ev => toggleUmbrella(ev.target.id()));
  afterDraw(keep, repos);
}

// nemik:W88: an edge between two boxes is faint until one of its ends is hovered or selected, or "show all
// cross-repo edges" is on. Inside a box, edges stay as they are.
function light() {
  cy.edges(".cross").removeClass("lit");
  if (document.getElementById("showCross").checked) { cy.edges(".cross").addClass("lit"); return; }
  cy.nodes(":selected").connectedEdges(".cross").addClass("lit");
}
function markCross() {
  const unit = n => (n.isChild() ? n.parent().id() : n.id());
  cy.edges().forEach(e => e.toggleClass("cross", unit(e.source()) !== unit(e.target())));
  light();
}
// nemik:W496/W498: follow a poll in place. The fleet's history says what changes (nemik-history --churn:
// 76% of commits mint, close or rewire cards, 20% touch a card's fields, 2% flip a status), so a poll's
// elements are diffed against the drawn ones by id: fields are written onto the cards that stay, cards
// and edges that went are removed, new ones are added beside their neighbours, and nothing already
// placed moves. The layout is then out of date by however many cards came or went, and says so; the
// button runs the full layout. A box or an operator lane appearing or going, or a card changing box, is
// the layout's business, so those return false and the caller draws afresh.
let layoutStale = 0;
const sameValue = (a, b) => a === b || JSON.stringify(a) === JSON.stringify(b);
function syncData(el, want) {
  const have = el.data(), fixed = new Set(["id", "source", "target", "parent"]);
  const changed = {};
  for (const k of Object.keys(want)) if (!fixed.has(k) && !sameValue(have[k], want[k])) changed[k] = want[k];
  for (const k of Object.keys(have)) if (!fixed.has(k) && !(k in want)) el.removeData(k);
  if (Object.keys(changed).length) el.data(changed);
}
function patchDraw(els) {
  const next = new Map(els.map(e => [e.data.id, e]));
  const isBox = e => /(^|\s)(repo|actor)(\s|$)/.test(e.classes || "");
  const drawnIds = new Set(cy.elements().map(e => e.id()));
  const added = els.filter(e => !drawnIds.has(e.data.id));
  const went = cy.elements().filter(e => !next.has(e.id()));
  if (added.some(isBox) || went.some(e => e.hasClass("repo") || e.hasClass("actor"))) return false;
  if (added.some(e => e.data.parent && !drawnIds.has(e.data.parent))) return false;
  for (const e of els) {
    const el = cy.getElementById(e.data.id);
    if (el.length && el.isNode() && (el.data("parent") || null) !== (e.data.parent || null)) return false;
  }
  cy.remove(went);
  for (const e of els) {
    const el = cy.getElementById(e.data.id);
    if (!el.length) continue;
    syncData(el, e.data);
    if (el.isEdge()) el.toggleClass("satisfied", /(^|\s)satisfied(\s|$)/.test(e.classes || ""));
  }
  const fresh = cy.add(added.filter(e => !e.data.source));
  placeNew(fresh);
  cy.add(added.filter(e => e.data.source));
  layoutStale += fresh.length + went.nodes().length;
  labelInk();
  markCross();
  const button = document.getElementById("relayout");
  button.hidden = !layoutStale;
  button.textContent = `layout out of date: ${layoutStale} cards moved in or out · re-layout`;
  return true;
}
// A new card goes beside what it is wired to in its own repo box: above a prerequisite it waits on, below
// a dependent that waits on it (the forest draws heads at the top and prerequisites beneath), else at the
// foot of the box; then along the row, and down a row, until it overlaps nothing.
function placeNew(fresh) {
  const SEP = 8, ROW = 20, ids = new Set(fresh.map(n => n.id())), done = new Set();
  const placed = n => !ids.has(n.id()) || done.has(n.id());
  fresh.forEach(n => {
    const box = n.parent(), mates = box.length ? box.children().filter(placed) : cy.nodes().filter(placed);
    const w = n.outerWidth(), h = n.outerHeight();
    const anchor = { above: null, below: null };
    n.connectedEdges().forEach(e => {
      const [pre, dep] = e.hasClass("waits") ? [e.target(), e.source()] : [e.source(), e.target()];
      const other = pre.id() === n.id() ? dep : pre;
      if (other.id() === n.id() || !mates.contains(other)) return;
      if (dep.id() === n.id()) anchor.above ||= other; else anchor.below ||= other;
    });
    let base;
    if (anchor.above) base = { x: anchor.above.position().x, y: anchor.above.position().y - (h + ROW) };
    else if (anchor.below) base = { x: anchor.below.position().x, y: anchor.below.position().y + (h + ROW) };
    else {
      const bb = mates.length ? mates.boundingBox() : { x1: 0, y2: 0 };
      base = { x: bb.x1 + w / 2, y: bb.y2 + ROW + h / 2 };
    }
    const clear = (x, y) => !mates.some(m => {
      const p = m.position();
      return Math.abs(p.x - x) < (m.outerWidth() + w) / 2 + 2 && Math.abs(p.y - y) < (m.outerHeight() + h) / 2 + 2;
    });
    let spot = base;
    search: for (let row = 0; row < 12; row++)
      for (let k = 0; k < 40; k++) {
        const x = base.x + (k % 2 ? 1 : -1) * Math.ceil(k / 2) * (w + SEP), y = base.y + row * (h + ROW);
        if (clear(x, y)) { spot = { x, y }; break search; }
      }
    n.position(spot);
    done.add(n.id());
  });
}
// What follows any draw, whole or patched: the selection (a rebuilt graph drops it, so the same node is
// selected again if it still exists), the chain edges, the Cards list and the status line.
function afterDraw(keep, repos) {
  if (selectedId) {
    const el = cy.getElementById(selectedId);
    if (el.length) { el.select(); detail(el.data()); } else { selectedId = null; }
  }
  markChainEdges();
  cardList();
  const shown = data.nodes.filter(n => keep.has(n.id));
  const blocked = shown.filter(n => n.state === "blocked").length;
  document.getElementById("stat").textContent = `${shown.length} waypoints · ${blocked} blocked · ${repos.length} repos`;
}

