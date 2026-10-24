// nemik:W932 (W931): the picked repo's queue as a queue. A classic script run before index.html's own:
// only definitions live here. Working cards come first, then the ready cards in the order they will be
// worked (queue.json, from nemik.queuerows), each with its place and the reason it sits there in words.
// A view that publishes no queue.json (the static build) says so rather than drawing a guessed order.

function queueReason(r) {
  const waited = r.waited_days < 0 ? "age unknown" : `waited ${r.waited_days} days`;
  const passed = r.overtaken_by
    ? `${r.overtaken_by} newer ${r.overtaken_by === 1 ? "card" : "cards"} ranked ahead of it`
    : "no newer card ahead of it";
  return `${r.band} band, weight ${r.weight}; ${waited}; ${passed}`;
}

function queueRepo(repo, doc) {
  const working = data.nodes.filter(n => n.repo === repo && n.state === "working");
  const rows = (doc.queues[repo] || []);
  const now = working.map(n => `<li>${citeLink(n.cite)} ${linked(n.title || "", repo)}</li>`);
  const next = rows.map(r =>
    `<li value="${r.place}">${citeLink(r.cite)} ${linked(r.title, repo)} <span class="stat">${esc(queueReason(r))}</span></li>`);
  return `<h2>${esc(repo)}</h2>`
    + (now.length ? `<p><b>Working now</b></p><ol class="queue">${now.join("")}</ol>` : "")
    + (next.length ? `<p><b>Next, in order</b> (1 is next)</p><ol class="queue">${next.join("")}</ol>` : "<p>No ready card.</p>");
}

async function queuePanel() {
  const el = document.getElementById("queue"), repos = [...picked].sort();
  if (!repos.length) { el.textContent = "Toggle a repo."; return; }
  let doc = null;
  try { const res = await fetch("queue.json"); doc = res.ok ? await res.json() : null; } catch (e) { doc = null; }
  paint(el, doc ? repos.map(r => queueRepo(r, doc)).join("")
    : "This view publishes no queue order; nemik-serve does (/queue.json).");
}
