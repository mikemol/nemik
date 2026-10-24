// nemik:W799: a part of the page's script, moved out of index.html (docs/web-modules.md).
// A classic script run before index.html's own: only definitions live here, no statement that
// touches the page when it loads. Its functions and constants stay global, as they were.

// nemik:W174: one entry per outage being waited on. Waypoints whose witnesses are the same query
// share a weather id (the query itself is not published), so N repos waiting on one registry
// outage read as one outage with N waiters, not N problems.
function weather() {
  const open = data.nodes.filter(n => n.weather && !["done", "dropped", "withheld"].includes(n.state));
  const groups = new Map();
  for (const n of open) (groups.get(n.weather) || groups.set(n.weather, []).get(n.weather)).push(n);
  const rows = [...groups.values()].filter(g => g.some(n => wants(n.repo)))
    .sort((a, b) => b.length - a.length || (a[0].cite < b[0].cite ? -1 : 1))
    .map(g => `<dt>${g.length} waiting</dt><dd>${g.map(n => citeLink(n.cite)).join(", ")}${
      g[0].title ? ` <span class="stat">${linked(g[0].title)}</span>` : ""}</dd>`);
  paint("weather", rows.length ? `<dl>${rows.join("")}</dl>` : "No outage is being waited on.");
}

function findings() {
  const rows = Object.entries(data.findings).filter(([r]) => wants(r))
    .flatMap(([r, fs]) => fs.map(([sev, sym, msg]) =>
      `<div class="finding ${esc(sev)}">${esc(sev)} · ${/^W\d+$/.test(sym) ? citeLink(`${r}:${sym}`) : esc(r)} · ${linked(msg)}</div>`));
  paint("findings", rows.join("") || '<span class="stat">none</span>');
}

// One toggle per repo. A repo that left the graph is dropped from the selection, so a stale pick
// cannot hide everything; the selection is a per-viewer preference (storage may be missing).
function chips(repos) {
  for (const r of [...picked]) if (!repos.includes(r)) picked.delete(r);
  const box = document.getElementById("repos");
  // nemik:W317: a chip carries its repo's health (nemik.health): a glyph as well as a colour, and the reasons on hover.
  const MARK = { amber: "▲ ", red: "■ " };
  paint(box, repos.map(r => {
    const h = (data.health || {})[r] || { status: "green", reasons: [] };
    const why = h.reasons.length ? `${h.status}: ${h.reasons.join("; ")}` : "green";
    // nemik:W432: the accessible name carries the health and its reasons in words (a screen reader
    // reads a title attribute inconsistently, and the glyph as a shape name); the glyph is decoration.
    const name = `${r}, health ${why}`;
    return `<button type="button" data-repo="${esc(r)}" data-health="${esc(h.status)}" title="${esc(why)}" aria-label="${esc(name)}" aria-pressed="${picked.has(r)}"><span aria-hidden="true">${MARK[h.status] || ""}</span>${esc(r)}</button>`;
  }).join(""));
  document.documentElement.style.setProperty("--hh", document.querySelector("header").offsetHeight + "px");
}

// nemik:W307: the project-manager's weekly roll-up (history.json, built host-side from git history, so
// the live pod has none and the panel stays hidden): per toggled repo, its last four weeks.
let historyDoc = undefined;
async function history() {
  const box = document.getElementById("historyBox");
  if (historyDoc === undefined) {
    try { const r = await fetch("history.json"); historyDoc = r.ok ? await r.json() : null; } catch (e) { historyDoc = null; }
  }
  if (!historyDoc) { box.hidden = true; return; }
  const rows = Object.entries(historyDoc).filter(([r]) => wants(r) && historyDoc[r].length).map(([r, weeks]) =>
    `<dt>${esc(r)}</dt><dd>${weeks.slice(-4).map(w =>
      `<div title="${esc(w.week)}: ${w.opened} opened, ${w.closed} closed, ${w.open} open, ${Math.round(100 * w.blocked_share)}% blocked${w.oldest_blocked_days == null ? "" : `, oldest block ${w.oldest_blocked_days}d`}">${esc(w.week.slice(5))} +${w.opened} −${w.closed} · ${w.open} open · ${Math.round(100 * w.blocked_share)}% blocked</div>`).join("")}</dd>`);
  box.hidden = !rows.length;
  paint("history", `<dl>${rows.join("")}</dl>`);
}

// nemik:W416: a static build publishes hashes.json and graph.json's pieces (graph/<repo>.json and
// graph/_fleet.json, W414/W415). The page refetches only the pieces whose hash moved and assembles
// them as nemik.pieces.assemble does; without hashes.json (nemik-serve) it reads graph.json whole.
const pieceCache = {};  // path -> {hash, doc}
window.__pieceFetches = [];  // the paths fetched, in order: what a browser test counts
// nemik:W655 (W509): one source's graph, fetched on its own cursor (the hash of each piece it last
// returned, kept per source and path). An empty URL is this server's own pieces. A source that cannot be
// reached, refuses (CORS), or answers something unreadable throws, and graphText shows it as unavailable
// while the others draw.
async function sourceGraph(src) {
  const base = src.url ? src.url.replace(/\/*$/, "/") : "";
  const res = await fetch(base + "hashes.json");
  if (!res.ok) {
    const whole = await fetch(base + "graph.json");
    if (!whole.ok) throw new Error("HTTP " + whole.status);
    return whole.json();
  }
  const hashes = await res.json();
  const piece = async path => {
    const key = base + path;
    if (!pieceCache[key] || pieceCache[key].hash !== hashes[path]) {
      window.__pieceFetches.push(key);
      pieceCache[key] = {hash: hashes[path], doc: await (await fetch(base + path)).json()};
    }
    return pieceCache[key].doc;
  };
  const fleet = await piece("graph/_fleet.json");
  const parts = [...await Promise.all(fleet.repos.map(r => piece(`graph/${r}.json`))), fleet];
  const byId = (a, b) => a.id < b.id ? -1 : a.id > b.id ? 1 : 0;
  const edgeKey = e => [e.source, e.target, e.kind];
  const byEdge = (a, b) => {
    const [x, y] = [edgeKey(a), edgeKey(b)];
    for (let i = 0; i < 3; i++) if (x[i] !== y[i]) return x[i] < y[i] ? -1 : 1;
    return 0;
  };
  const merged = section => Object.fromEntries(
    parts.flatMap(p => Object.entries(p[section])).sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0));
  return {
    nodes: parts.flatMap(p => p.nodes).sort(byId),
    edges: parts.flatMap(p => p.edges).sort(byEdge),
    inbound: fleet.inbound,
    operator: fleet.operator,
    findings: merged("findings"),
    health: merged("health"),
    ruler: fleet.ruler,
  };
}

// Every source is asked; the ones that answer are combined (cards and edges by identity, the rest
// joined), and each one's outcome is kept in sourceStatus for the Sources section. Only when none
// answers is the refresh a failure. One answering source is returned untouched.
let sourceStatus = [];
async function graphText() {
  const got = await Promise.allSettled(sources.map(sourceGraph));
  sourceStatus = got.map(g => g.status === "fulfilled" ? "ok" : "unavailable: " + ((g.reason && g.reason.message) || "failed"));
  const docs = got.filter(g => g.status === "fulfilled").map(g => g.value);
  if (!docs.length) throw new Error("no source answered");
  return JSON.stringify(docs.length === 1 ? docs[0] : combine(docs));
}

// nemik:W656 (W509): several answering sources as one graph. Cards and edges join by identity. A card
// waiting on "<repo>:W<n>" in another source is wired to that card, by the one rule adapter.resolve_blocker
// applies to the cross-workstream form; the server could only do that for repos it knew. A reference whose
// repo no loaded source holds becomes a stub carrying the symbol (state "unloaded"), as withheld.py leaves
// a stub where a withheld card is pointed at, so the wait is drawn and says what it waits for.
const FOREIGN_WAIT = /^([A-Za-z0-9._-]+):W(\d+)$/;
function combine(docs) {
  const once = (rows, key) => [...new Map(rows.map(r => [key(r), r])).values()];
  const byId = (a, b) => a.id < b.id ? -1 : a.id > b.id ? 1 : 0;
  const nodes = once(docs.flatMap(d => d.nodes), n => n.id);
  const edges = once(docs.flatMap(d => d.edges), e => [e.source, e.target, e.kind].join(" "));
  const ids = new Set(nodes.map(n => n.id));
  const waits = new Set(edges.filter(e => e.kind === "waits").map(e => e.source + " " + e.target));
  for (const n of [...nodes]) {
    for (const text of n.blocked_on || []) {
      const m = FOREIGN_WAIT.exec(text.trim());
      if (!m || m[1] === n.repo) continue;
      const id = `urn:nemik:${m[1]}/W${m[2]}`;
      if (!ids.has(id)) {
        ids.add(id);
        nodes.push({ id, repo: m[1], symbol: `W${m[2]}`, cite: `${m[1]}:W${m[2]}`, state: "unloaded",
          title: "in a source that is not loaded", blocked_on: [], blocked_kind: "", caused_by: "",
          minted_during: "", effort: {}, last_activity: "", open_blockers: 0, weather: "" });
      }
      if (!waits.has(n.id + " " + id)) { waits.add(n.id + " " + id); edges.push({ source: n.id, target: id, kind: "waits" }); }
    }
  }
  return {
    nodes: nodes.sort(byId),
    edges,
    inbound: docs.flatMap(d => d.inbound || []),
    operator: docs.flatMap(d => d.operator || []),
    findings: Object.assign({}, ...docs.map(d => d.findings || {})),
    health: Object.assign({}, ...docs.map(d => d.health || {})),
    ruler: docs[0].ruler,
  };
}

let lastGraph = null;
async function load() {
  try {
    const text = await graphText();
    // nemik:W119: the 60s poll redrew and re-fit even when nothing changed, so the view jumped
    // and lost the reader's pan/zoom every minute. An unchanged graph is not redrawn.
    if (text === lastGraph && data) {
      drawSources();
      await wake();  // liveness still refreshes: recolour the boxes in place, no relayout
      cy.nodes(".repo").forEach(n => n.data("live", liveness[n.id().slice(5)] || "unknown"));
      return;
    }
    lastGraph = text;
    data = JSON.parse(text);
  } catch (e) {
    // A blank page looks the same as "still loading" -- say what actually happened, and keep
    // whatever was last rendered rather than tearing the graph down over a transient miss.
    // nemik:W657: a page opened from a file: URL cannot read its sibling data files (the browser refuses
    // fetch there), which looks like a dead page; say what to do. From a bucket or any http(s) host the
    // same files load as they do from a server.
    const fromFile = location.protocol === "file:";
    document.getElementById("stat").textContent = fromFile
      ? "opened from a file: the browser will not let a page read its data files here; serve this folder over http (for example python3 -m http.server) or put it in a bucket"
      : data ? "graph refresh failed, showing last-known data" : "graph unavailable";
    drawSources();
    return;
  }
  drawSources(); applyAddress();
  chips([...new Set(data.nodes.map(n => n.repo))].sort());
  await wake();  // draw() reads `liveness`, populated by wake() -- fetch it first, not alongside.
  await loadCore();  // render() marks the longest chains through it
  pathKey(); render(true); selectAddressCard(); findings(); goals(); queuePanel(); weather(); history();
}

// Also feeds `liveness` (repo -> asleep/idle/awake) that draw() uses to color repo boxes, so the
// graph doesn't fetch this a second time.
// nemik:W669: luthen's series (wake.json's series, a board only when the server has a fresh snapshot) as the
// repos that hold workable cards but are not awake, each with its state in words and the share of its
// history spent awake, idle and asleep. No file, or board false, draws nothing.
function seriesBoard(s) {
  const share = h => {
    const t = { awake: 0, idle: 0, asleep: 0 };
    for (let i = 0; i < h.length; i++) {
      const end = i + 1 < h.length ? h[i + 1].at : s.as_of;
      t[h[i].state] = (t[h[i].state] || 0) + Math.max(0, end - h[i].at);
    }
    const sum = t.awake + t.idle + t.asleep, pct = n => Math.round(100 * n / sum);
    return sum ? `awake ${pct(t.awake)}%, idle ${pct(t.idle)}%, asleep ${pct(t.asleep)}% of its history` : "no history";
  };
  const spent = t => t && (t.input || t.output) ? `; ${Math.round((t.input + t.output) / 1000)}k tokens in and out` : "";
  const rows = s.stranded.map(r => `<dt>${esc(r)}</dt><dd>${esc(s.repos[r].state)}, ${s.repos[r].ready} workable; ${esc(share(s.repos[r].history))}${spent(s.repos[r].tokens)}</dd>`);
  return rows.length
    ? `<p><b>${rows.length} with work, not awake</b> (luthen's series):</p><dl>${rows.join("")}</dl>`
    : `<p class="stat">Every repo with work is awake (luthen's series).</p>`;
}
// nemik:W751: each repo's commit gate times from mikemol-commit's landing records (landings.json, a
// board only when the host left a file): how many landed, the median and last gate in minutes, and
// the recent ones as a sparkline against the repo's own slowest. No file, or host false, draws nothing.
const SPARK = "▁▂▃▄▅▆▇█";
function landingsBoard(l) {
  const minutes = s => `${Math.round(s / 60)} min`;
  const rows = Object.keys(l.series).sort().map(repo => {
    const g = l.series[repo], sorted = [...g].sort((a, b) => a - b), top = sorted[sorted.length - 1] || 1;
    const spark = g.slice(-12).map(s => SPARK[Math.min(SPARK.length - 1, Math.floor(s / top * SPARK.length))]).join("");
    return `<dt>${esc(repo)}</dt><dd>${g.length} landed; gate median ${minutes(sorted[Math.floor(sorted.length / 2)])}, last ${minutes(g[g.length - 1])} <span class="stat">${spark}</span></dd>`;
  });
  return rows.length
    ? `<p><b>Commit gate times</b> (mikemol-commit, read ${esc(l.as_of)}${l.stale ? ", stale" : ""}):</p><dl>${rows.join("")}</dl>`
    : "";
}
async function wake() {
  const el = document.getElementById("wake");
  let w, board = "";
  try { w = await (await fetch("wake.json")).json(); } catch (e) { el.textContent = "unavailable"; return; }
  if (w.series && w.series.board) board = seriesBoard(w.series);
  try {
    const l = await (await fetch("landings.json")).json();
    if (l.host) board += landingsBoard(l);
  } catch (e) { /* static view or no host file: no landings board */ }
  liveness = Object.fromEntries(w.roster.map(r => [r.repo, r.state]));
  const sleepers = w.roster.filter(r => r.state !== "awake");
  const rows = sleepers.map(r => `<dt><b>${esc(r.repo)}</b> <span class="stat">${esc(r.state)}</span></dt>
    <dd>${r.waiting.map(x => `${citeLink(x.blocked)}${x.claimed_by.length ? "" : ` (waiting on ${esc(r.repo)}: claim with <code>--enables</code> ${citeLink(x.blocked)})`}`).join(", ")}</dd>`);
  paint(el, (rows.length ? `<dl>${rows.join("")}</dl>` : "Everything waited on is awake.")
    + `<p><b>${w.operator.waiting.length} need you:</b> ${w.operator.waiting.map(x => citeLink(x.blocked)).join(", ") || "none"}</p>`
    + board
    + `<p class="stat">Liveness: ${esc(w.liveness)}.</p>`);
}

// nemik:W80: the selected repo's goals, each with its on-deck leaf and whether its path is clear
// (nothing outside the repo left to wait on).
async function goals() {
  const el = document.getElementById("goals"), repos = [...picked].sort();
  if (!repos.length) { el.textContent = "Toggle a repo."; return; }
  const parts = [];
  for (const repo of repos) {
    let gs;
    try { gs = await (await fetch("goals/" + encodeURIComponent(repo) + ".json")).json(); } catch (e) { parts.push(`<p>${esc(repo)}: unavailable</p>`); continue; }
    parts.push((repos.length > 1 ? `<h2>${esc(repo)}</h2>` : "") + (gs.length ? "<dl>" + gs.map(g => `<dt>${citeLink(repo + ":" + g.goal)} ${esc(g.title.slice(0, 60))}</dt>
    <dd>on deck ${g.on_deck ? citeLink(g.on_deck) : "none"}; path ${g.clear
      ? '<span style="color:var(--ready)">clear</span>'
      : '<span style="color:var(--blocked)">waits on</span> ' + weatherOnce(g.outside).map(o => linked(o)).join(", ")}</dd>`).join("") + "</dl>"
      : "No open goals."));
  }
  paint(el, parts.join(""));
}


// A cite in the Wake panel is a link: it selects that waypoint in the graph and shows its detail.
// Operator 2026-10-02: one cite format everywhere, `repo:W<n>`, and every cite is a link. linked()
// escapes free text and turns each cite in it into one; a bare W<n> is that repo's when `repo` is
// given (a waypoint's own blocked_on names its local items that way).
const CITE = /\b([a-z][a-z0-9-]*):(W\d+)\b/g;
function linked(text, repo) {
  // The older spellings "repo W<n>" and "repo/W<n>" of a known repo are the same cite.
  const repos = new Set((data && data.nodes || []).map(n => n.repo));
  let out = esc(text).replace(/\b([a-z][a-z0-9-]*)[ \/](W\d+)\b/g, (m, r, w) => repos.has(r) ? `${r}:${w}` : m)
    .replace(CITE, (m) => citeLink(m));
  if (repo) out = out.replace(/(^|[\s,(\[])(W\d+)\b(?![^<]*<\/code>)/g, (m, pre, w) => pre + citeLink(`${repo}:${w}`));
  return out;
}
// A goal's outside list, with refs that wait on the same outage (same weather id) shown once.
function weatherOnce(refs) {
  const seen = new Set();
  return refs.filter(r => { const w = (data.nodes.find(n => n.cite === r) || {}).weather;
    if (!w) return true; if (seen.has(w)) return false; seen.add(w); return true; });
}
function citeLink(cite) {
  return `<a href="#" data-cite="${esc(cite)}"><code>${esc(cite)}</code></a>`;
}

// nemik:W654 (W509): the sources this viewer assembles its graph from, an id and a URL each, kept in this
// browser only. The default is one entry, nemik's own published pieces (an empty URL means "here"). A
// reading that is missing, throws or is not a list of {id, url} strings leaves the default.
const DEFAULT_SOURCES = [{ id: "nemik", url: "" }];
let sources = DEFAULT_SOURCES.map(s => ({ ...s }));
try {
  const kept = JSON.parse(localStorage.getItem("nemik.sources") || "null");
  if (Array.isArray(kept) && kept.length && kept.every(s => s && typeof s.id === "string" && typeof s.url === "string"))
    sources = kept.map(s => ({ id: s.id, url: s.url }));
} catch (e) { /* not remembered */ }
function saveSources() {
  try { localStorage.setItem("nemik.sources", JSON.stringify(sources)); } catch (e) { /* not remembered */ }
}
function drawSources() {
  const rows = sources.map((s, i) => `<div class="srcrow">
    <input data-src="${i}" data-field="id" value="${esc(s.id)}" aria-label="source ${i + 1} id" size="8">
    <input data-src="${i}" data-field="url" value="${esc(s.url)}" aria-label="source ${i + 1} URL, empty for this server" size="22">
    <button type="button" data-remove="${i}" aria-label="remove source ${i + 1}">remove</button>
    <span class="stat" data-status="${i}">${esc(sourceStatus[i] || "")}</span></div>`);
  paint(document.getElementById("sources"), rows.join("")
    + `<button type="button" id="addsource">add source</button>`
    + `<p class="stat">Kept in this browser. An empty URL is this server's own published pieces.</p>`);
}

