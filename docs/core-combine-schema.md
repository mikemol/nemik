# The documents the page's combine step takes (nemik:W2402, for the port W1028)

Read from `src/nemik/web/panels.js` at main 6b78506a: `combine(docs)` (line 115) joins several
answering sources' graphs into one. A port to `src/nemik/core` (nemik:W1028, W812) takes these
documents and returns this one. This note is the contract read from the code; nothing here is built.

## Input: `docs`, a list of graph documents, one per answering source

Each document is what `sourceGraph(src)` returns (lines 85-94). Every key but `nodes` and `edges`
may be absent in a document; combine reads the absent key as empty (`|| []`, `|| {}`).

| key | type | combine's use |
|---|---|---|
| `nodes` | list of node objects | joined by `id`, the last document's row wins |
| `edges` | list of `{source, target, kind}` | joined by `source target kind`, the last wins |
| `umbrellas` | list of rows with `id`, `card` | joined by `id card` (W975, from `umbrellas.json`, W973) |
| `inbound` | list | concatenated in document order, no dedupe |
| `operator` | list | concatenated in document order, no dedupe |
| `findings` | object | merged by key, a later document's key replaces an earlier one's |
| `health` | object | merged by key, a later document's key replaces an earlier one's |
| `ruler` | object | the FIRST document's, `docs[0].ruler`, the others ignored |

A node read for its blockers carries `repo`, `blocked_on` (a list of strings), and `id`; combine
reads no other node field. The stub it makes (below) fills the full node shape the page expects.

## The one rule that makes new rows: a foreign wait

For each node `n` and each text in `n.blocked_on` (trimmed), match `^([A-Za-z0-9._-]+):W(\d+)$`
(`FOREIGN_WAIT`, line 114):

- no match, or the matched repo equals `n.repo`: skipped (a same-repo wait is already wired by the
  server, `adapter.resolve_blocker`);
- else the target id is `urn:nemik:<repo>/W<n>`. When no node holds that id (checked over the ids
  seen so far, including stubs this loop added), a stub node is appended with `id`, `repo`,
  `symbol` `W<n>`, `cite` `<repo>:W<n>`, `state` `"unloaded"`, `title` `"in a source that is not
  loaded"`, `blocked_on` `[]`, `blocked_kind` `""`, `caused_by` `""`, `minted_during` `""`,
  `effort` `{}`, `last_activity` `""`, `open_blockers` `0`, `weather` `""`;
- then, when the pair `<n.id> <target id>` is not already a `waits` edge, an edge
  `{source: n.id, target, kind: "waits"}` is appended (and the pair remembered, so two texts naming
  one card add one edge).

## Output

`{nodes, edges, umbrellas, inbound, operator, findings, health, ruler}`:

- `nodes`: sorted by `id` (string `<`), stubs included. `edges`: in the order built (the joined
  rows in document order, then the added `waits` edges), NOT sorted.
- The other keys as the table says.

## What a port must keep, and what is not pinned

- `once(rows, key)` is a Map: a duplicate key keeps its FIRST position and takes the LAST row's
  value. So "last wins" is about the row, and the order of `edges` and `umbrellas` is by first
  appearance.
- Order: nodes sorted by id; edges unsorted; both outputs depend on the documents' order only
  through "last wins" and the concatenations, so the port takes the list in the page's order.
- The stub's field set and its `urn:nemik:` id are an interface to the page and to the layout.
- Not pinned by any test I found: the first-document-wins `ruler`, the `inbound`/`operator`
  concatenation without dedupe, and the "last document wins" on a duplicate node or edge.
  nemik:W1028's tests should pin them before the port, so the port cannot change them silently.
- Plain data only: no tuples as keys (the page joins an edge's key with a space; a Codon port
  must do the same with a string).
