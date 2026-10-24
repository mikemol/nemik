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

// nemik:W953 (W937): the address is applied once, on the first load. The repo is picked before the chips
// draw and the card is selected after the first render; a name the graph does not hold is ignored.
let addressState = null, addressSelected = false;
function applyAddress() {
  if (addressState) return;
  addressState = parseAddress(location.hash);
  const repo = addressState.scope[0];
  if (repo && data.nodes.some(n => n.repo === repo)) { picked.clear(); picked.add(repo); }
}
function selectAddressCard() {
  if (addressSelected || !addressState) return;
  addressSelected = true;
  const [repo, ...symbols] = addressState.scope;
  if (symbols.length) focusCite(`${repo}:${symbols[symbols.length - 1]}`);  // a card not drawn still shows in Selected
}

function formatAddress(state) {
  const path = state.scope.map(encodeURIComponent).join("/");
  return "#/" + path + (state.view ? "?view=" + encodeURIComponent(state.view) : "");
}
