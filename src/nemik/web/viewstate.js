// nemik:W952 (W937): the page's address as state. A classic script run before index.html's own: only
// definitions live here. The address is "#/<repo>/<symbol>.../?view=<token>": the scope path from the
// fleet (nothing) down to a repo, an umbrella and a card, and the view as a token the page does not
// interpret here (docs/page-structure-map.md leaves the view names to the operator). A malformed
// address is no state at all, never a half-read one.

const ADDRESS_REPO = /^[A-Za-z0-9._-]+$/, ADDRESS_SYMBOL = /^W\d+$/, ADDRESS_VIEW = /^[a-z][a-z-]*$/;

function parseAddress(hash) {
  const none = { scope: [], view: "" };
  const [path, query = ""] = String(hash).replace(/^#/, "").split("?");
  let parts;
  try { parts = path.split("/").filter(Boolean).map(decodeURIComponent); } catch (e) { return none; }
  const view = new URLSearchParams(query).get("view") || "";
  const [repo, ...symbols] = parts;
  const scoped = parts.length === 0 || (ADDRESS_REPO.test(repo) && symbols.every(s => ADDRESS_SYMBOL.test(s)));
  return scoped && (!view || ADDRESS_VIEW.test(view)) ? { scope: parts, view } : none;
}

function formatAddress(state) {
  const path = state.scope.map(encodeURIComponent).join("/");
  return "#/" + path + (state.view ? "?view=" + encodeURIComponent(state.view) : "");
}
