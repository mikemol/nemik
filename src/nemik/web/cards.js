// nemik:W799: a part of the page's script, moved out of index.html (docs/web-modules.md).
// A classic script run before index.html's own: only definitions live here, no statement that
// touches the page when it loads. Its functions and constants stay global, as they were.

// nemik:W435: what the canvas offers only to a pointer (select a card and read it, expand an umbrella)
// as a keyboard-reachable list of the cards drawn, in salience order. A row's button selects through
// the same path as a tap; an umbrella's second button toggles the same roll-up as a double-click and
// says its state in aria-expanded.
function selectCard(id) {
  const el = cy.getElementById(id);
  if (!el.length) return;
  cy.nodes(":selected").unselect();
  el.select();
  selectedId = id; detail(el.data()); refreshRings();
  // in place, not a rebuild: rebuilding would drop the keyboard focus on the row just pressed
  for (const b of document.querySelectorAll("#cardlist button[data-card]"))
    b.setAttribute("aria-current", String(b.dataset.card === id));
  // nemik:W473: one select path (tap, list row, cite link) and one announcement of it
  const d = el.data();
  document.getElementById("announce").textContent =
    `selected ${d.cite || d.symbol}, ${d.state || ""}: ${d.title || ""}`;
}
// nemik:W473: a cite anywhere on the page (Selected panel, lanes, wake, goals) selects its card
// through selectCard and brings it into view; one not drawn still shows in the Selected panel.
function focusCite(cite) {
  const n = data.nodes.find(x => x.cite === cite);
  if (!n) return;
  const el = cy && cy.getElementById(n.id);
  if (el && el.length) {
    selectCard(n.id);
    cy.animate({ center: { eles: el }, zoom: Math.max(cy.zoom(), 1.2) });
  } else detail(n);
}
function toggleUmbrella(id) {
  const el = cy.getElementById(id);
  if (el.data("rollup")) expanded.add(id); else if (expanded.has(id)) expanded.delete(id); else return;
  draw();
}
function cardList() {
  const list = document.getElementById("cardlist");
  // nemik:W480/W497: what holds keyboard focus in the list, so a rebuild puts it back on the same control
  const at = document.activeElement;
  const held = at && list.contains(at)
    ? (at.dataset.card ? `button[data-card="${CSS.escape(at.dataset.card)}"]`
      : at.dataset.toggle ? `button[data-toggle="${CSS.escape(at.dataset.toggle)}"]` : null) : null;
  if (listMode === "critical") computeChains();
  // an unclaimed placeholder is another repo's ask, labelled with its cite, not a card of its own
  const rows = cy.nodes("[symbol]").filter(n => n.visible() && n.data("state") !== "unclaimed").toArray()
    .sort((a, b) => LIST_ORDER[listMode](a, b) || (a.id() < b.id() ? -1 : 1));
  // nemik:W481, W725: the list is a tree. Each visible card sits under the heaviest visible thing it enables
  // (treeOf, the forest the treemap uses), in the list's own order; a card with nothing under it is a leaf.
  const byId = new Map(rows.map(n => [n.id(), n]));
  const rank = new Map(rows.map((n, i) => [n.id(), i]));
  const tree = treeOf(rows.map(n => n.data()), cy.edges().toArray()
    .filter(e => byId.has(e.source().id()) && byId.has(e.target().id()))
    .map(e => ({ kind: e.hasClass("waits") ? "waits" : "enables", source: e.source().id(), target: e.target().id() })));
  const under = id => (tree.kids.get(id) || []).filter(k => byId.has(k)).sort((a, b) => rank.get(a) - rank.get(b));
  const item = (id, level) => {
    const n = byId.get(id), d = n.data(), kids = under(id), open = !closedTree.has(id), esId = esc(id);
    // nemik:W688: the badge's count is visible text (WCAG 2.5.3), so the name carries it, in words
    const warned = (d.warnings || []).length;
    const name = `${d.state || ""} ${d.symbol}${warned ? ` ${warned} warning${warned > 1 ? "s" : ""}` : ""}: ${d.title || ""}`;
    const umbrella = d.rollup || expanded.has(id);
    const toggle = umbrella
      ? ` <button type="button" tabindex="-1" data-toggle="${esId}" aria-expanded="${expanded.has(id)}">${expanded.has(id) ? "collapse" : `expand ${d.rollup}`}</button>`
      : "";
    const folds = kids.length ? ` aria-expanded="${open}"` : "";
    const group = kids.length
      ? `<ul role="group"${open ? "" : " hidden"}>${kids.map(k => item(k, level + 1)).join("")}</ul>` : "";
    return `<li role="none"><button type="button" role="treeitem" tabindex="-1" data-card="${esId}" aria-level="${level}"${folds}`
      + ` aria-label="${esc(name)}" aria-current="${id === selectedId}">${esc(d.label || d.symbol)}</button>${toggle}${group}</li>`;
  };
  const roots = rows.map(n => n.id()).filter(id => !byId.has(tree.parent.get(id)));
  const html = roots.map(id => item(id, 1)).join("");
  if (!paint(list, html)) return;  // nothing the list shows moved: leave it, and the focus in it, alone
  // nemik:W478: one tab stop for the whole list (a roving tabindex): the focused control if it survived,
  // else the selected card's row, else the first
  const buttons = [...list.querySelectorAll("button[data-card]")];
  const back = held && list.querySelector(held);
  const stop = back || buttons.find(b => b.dataset.card === selectedId) || buttons[0];
  if (stop) stop.tabIndex = 0;
  if (back) back.focus({ preventScroll: true });
}

function lane(cat) {
  const help = {
    "needs-you": "A decision or an act only you can make. Asks listed together are the same ask from several repos.",
    "no-command": "An act on a machine with nothing to run yet: the owning repo still owes the command (or the tool). Not yours until it has one. Ticks show how long each has stood.",
    answered: "The block records your answer already. The agent should lift it or re-file it against the condition it now waits on.",
    condition: "Filed against you, but it waits on an event or condition, not on you.",
    unstated: "Blocked on you with no stated ask, so you can't tell a decision from a check-in. The agent should state what it needs.",
  }[cat];
  const rows = (data.operator || []).filter(a => a.category === cat).map(a =>
    `<dt>${citeLink(a.ref)}${a.salience ? ` <span class="stat" title="demand waiting behind this ask, in nemik-rank units">${a.salience}</span>` : ""}${a.ticks_blocked ? ` <span class="stat" title="loop ticks this ask has stood">${a.ticks_blocked} ticks</span>` : ""}</dt><dd>${linked(a.ask, a.ref.split(":")[0])}${a.same_ask.length ? `<br><span class="stat">same ask: ${a.same_ask.map(citeLink).join(", ")}</span>` : ""}${(a.waiting || []).length ? `<br><span class="stat">waiting behind this: ${a.waiting.map(citeLink).join(", ")}</span>` : ""}</dd>`);
  paint("detail", `<p class="stat">${esc(help)}</p><dl>${rows.join("")}</dl>`);
}

function detail(n) { paint("detail", detailHTML(n)); }
const POP_OPEN_MS = 500, POP_CLOSE_MS = 300;
let popOpen = null, popClose = null;
function popSoon(el) {
  clearTimeout(popClose); clearTimeout(popOpen);
  popOpen = setTimeout(() => popShow(el), POP_OPEN_MS);
}
function popShow(el) {
  const pop = document.getElementById("pop"), box = document.getElementById("cy").getBoundingClientRect();
  const bb = el.renderedBoundingBox();
  pop.innerHTML = detailHTML(el.data());
  pop.hidden = false;
  // beside the card, kept inside the window
  const x = Math.min(box.left + bb.x2 + 8, window.innerWidth - pop.offsetWidth - 8);
  const y = Math.min(box.top + bb.y1, window.innerHeight - pop.offsetHeight - 8);
  pop.style.left = Math.max(8, x) + "px"; pop.style.top = Math.max(8, y) + "px";
}
function popLater() { clearTimeout(popOpen); clearTimeout(popClose); popClose = setTimeout(popHide, POP_CLOSE_MS); }
function popHide() { clearTimeout(popOpen); clearTimeout(popClose); document.getElementById("pop").hidden = true; }

let beforeHelp = null;
function openHelp(jump) {
  beforeHelp = document.activeElement;
  keyhelp.hidden = false;
  jumpform.hidden = !jump;
  (jump ? document.getElementById("jump") : keyhelp).focus();
}
function closeHelp() {
  keyhelp.hidden = true;
  document.getElementById("jump").value = "";
  if (beforeHelp && beforeHelp.focus) beforeHelp.focus();
}
const ACTIONS = {
  help: () => (keyhelp.hidden || !jumpform.hidden ? openHelp(false) : closeHelp()),
  jump: () => openHelp(true),
  close: () => (keyhelp.hidden ? popHide() : closeHelp()),
  orderRank: () => pickListMode("rank"),
  orderNewest: () => pickListMode("newest"),
  orderCritical: () => pickListMode("critical"),
  orderRepo: () => pickListMode("repo"),
  orderAsks: () => pickListMode("asks"),
  orderRecent: () => pickListMode("recent"),
};
// nemik:W798: the order radios act on the Cards section, which is closed by default; choosing an order
// opens it, so the choice shows. Before this a viewer picked an order and saw nothing change.
function showCards() {
  document.getElementById("sec-cards").open = true;
}
function pickListMode(mode) {
  listMode = mode;
  document.querySelector(`input[name="listmode"][value="${mode}"]`).checked = true;
  // nemik:W470: the clock is a choice only in the recent mode
  document.getElementById("clockgroup").hidden = mode !== "recent";
  showCards();
  cardList();
}

const KEYMAP = [
  { key: "?", mode: "any", action: "help", description: "show or hide this list of shortcuts" },
  { key: "/", mode: "any", action: "jump", description: "jump to a card by cite or title" },
  { key: "Escape", mode: "any", action: "close", description: "close this panel, or the card popover" },
  { key: "1", mode: "any", action: "orderRank", description: "order the card list by rank" },
  { key: "2", mode: "any", action: "orderNewest", description: "order the card list newest first" },
  { key: "3", mode: "any", action: "orderCritical", description: "order the card list by longest chain beneath it" },
  { key: "4", mode: "any", action: "orderRepo", description: "group the card list by repo" },
  { key: "5", mode: "any", action: "orderAsks", description: "put the cards waiting on the operator first" },
  { key: "6", mode: "any", action: "orderRecent", description: "put the card worked on most recently first" },
];

// nemik:W462: the Selected panel's rows, also shown by the hover popover, from one source
function detailHTML(n) {
  const e = n.effort || {};
  if (n.state === "unclaimed") {
    return `<dl>
      <dt>waiting</dt><dd>${citeLink(n.for)} is blocked on <b>${esc(n.repo)}</b></dd>
      <dt>blocked on</dt><dd>${linked(n.blocked_on.join(", "), n.for.split(":")[0])}</dd>
      <dt>claimed by</dt><dd>nothing yet</dd></dl>
      <p class="stat">To make it citable: ${esc(n.repo)} adds a waypoint with
      <code>--enables</code> ${citeLink(n.for)}, or the blocked side writes that waypoint as
      <code>${esc(n.repo)}:W&lt;n&gt;</code> in blocked_on. ${esc(n.repo)}'s agent can list these with
      <code>nemik-inbound ${esc(n.repo)}</code> or <code>/inbound/${esc(n.repo)}</code>.</p>`;
  }
  const inb = (data.inbound || []).filter(b => b.claimed_by.includes(n.cite) || b.blocked === n.cite);
  return `<dl>
    <dt>cite as</dt><dd>${citeLink(n.cite)}</dd>
    <dt>title</dt><dd>${linked(n.title)}</dd>
    <dt>state</dt><dd>${esc(n.state)}${n.stage === "gating" ? " (in a commit stack: being worked)" : ""}${needsManifest(n) ? " (needs a manifest: without one it cannot be stacked)" : ""}</dd>
    ${n.warnings && n.warnings.length ? `<dt>warnings</dt><dd>${n.warnings.map(w => `${esc(w.severity)}: ${esc(w.message)}`).join("<br>")}</dd>` : ""}
    ${n.salience !== undefined ? `<dt>salience</dt><dd>${n.salience} (flow model; band ${esc(n.band || "")}, rank ${n.rank_pos})</dd>` : ""}
    ${n.path_count ? `<dt>longest chains through it</dt><dd>${n.path_count}${n.path_count > 1 ? " (tied alternatives)" : ""}</dd>` : ""}
    ${n.minted_during ? `<dt>minted during</dt><dd>${esc(n.minted_during)}</dd>` : ""}
    ${n.caused_by ? `<dt>caused by</dt><dd>${linked(n.caused_by.replace(/^urn:nemik:([^/]+)\//, "$1:"), n.repo)}</dd>` : ""}
    ${n.blocked_on.length ? `<dt>blocked on</dt><dd>${linked(n.blocked_on.join(", "), n.repo)} (${esc(n.blocked_kind)})</dd>` : ""}
    ${(n.suppliers && n.suppliers.length) || n.want ? `<dt>or any owner</dt><dd>${n.want ? esc(n.want) : "of what it waits on"}${n.suppliers && n.suppliers.length ? ` (also fine: ${linked(n.suppliers.join(", "), n.repo)})` : ""}</dd>` : ""}
    <dt>forecast</dt><dd>${e.forecast || 0}</dd>
    <dt>interrupt</dt><dd>${e.interrupt || 0}</dd>
    <dt>unclassified</dt><dd>${e.unclassified || 0}</dd>
    <dt>last activity</dt><dd>${esc(n.last_activity || "none")}</dd>
    ${inb.filter(b => b.blocked !== n.cite).map(b => `<dt>is the block for</dt><dd>${citeLink(b.blocked)}</dd>`).join("")}
    ${inb.filter(b => b.blocked === n.cite).map(b => `<dt>waits on</dt><dd>${b.claimed_by.length
      ? b.claimed_by.map(citeLink).join(", ") : `${esc(b.blocker)} (waiting on ${esc(b.blocker)}: claim with <code>--enables</code> ${citeLink(b.blocked)})`}</dd>`).join("")}</dl>`;
}

