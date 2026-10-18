# The Source contract (nemik:W507)

**Status: design, nothing built.** The first step of the client-path chain (W506 to W511, with
W516 for withholding). Written for whoever builds the first adapter.

## What the browser needs

A page that shows a fleet should be able to take cards and edges from anything that can yield them,
not only from the pod that renders it today. A **Source** is that anything:

    Source = { id, fetch(cursor) -> { cards, edges, cursor } }

- `id` names the source (a repo, a pod, a forge) so a card keeps the source it came from.
- `cursor` is opaque to the page and means "what I had last time": an empty cursor asks for
  everything, and a cursor returned by `fetch` asks only for what changed since.
- `cards` and `edges` are the shapes the view already reads (`graph.json` nodes and edges), so a
  source that already publishes those needs no translation beyond the cursor.

Every source answers three questions, because they differ and the page must not guess:

1. **How does it name a card?** The page's name is `repo:W<n>`; a source that uses another name
   maps it, and a card it cannot name this way is not shown rather than shown under a wrong name.
2. **How does a cross-repo `blocked_on` resolve?** To a card of another source when that source is
   loaded, and to a stub carrying only the symbol when it is not (as `withheld.py` does), never
   silently dropped.
3. **What is its cursor?** A hash, an ETag, a changelog position or an outbox page.

## Adapters, from what exists

| Adapter | Reads | Card name | Cursor | Needs published |
| --- | --- | --- | --- | --- |
| nemik pieces | `graph/<repo>.json` pieces listed in `hashes.json` | already `repo:W<n>` | the piece's sha256 in `hashes.json` | nothing new |
| OSLC TRS | the Tracked Resource Set base and change log nemik already serves (`trs.py`, `catalog.py`) | the resource IRI | the change log position | nothing new |
| raw queue file | a repo's `.claude/paths-forward.json` over HTTP from a forge's raw endpoint | `<repo>:W<n>` from the file | the ETag | nothing: the forge already serves it |
| ForgeFed / ActivityPub | an actor's outbox | not settled | the outbox page | an actor per repo (not built) |

The last row is the least known: I have not read ForgeFed's card model, so its naming and cursor
are open, and nothing below depends on it.

## The first adapter

**The raw queue file**, because it needs nothing published: the forge already serves the file, an
ETag is the cursor, and a source that proves the contract on real data costs one adapter and no
change to any repo. It also exercises the hard part, a cross-repo `blocked_on` pointing at a repo
whose source is or is not loaded. nemik pieces is the second, because it is the contract's own
native form.

What a raw queue file lacks is everything derived: rank, salience, the flow solve, the SHACL
findings. Those are W508's concern (every computation the view needs runs over plain Card data, so
it can run in the browser). Until W508, a raw-file source shows cards, states and edges, and no
rank.

## What this does not decide

- Where the contract lives in code. A pure `Source` protocol and the raw-file adapter fit one new
  module; the page's side is TypeScript emitted from Python through mtools' web-subset steps
  (mtools:W1070, W1071), whose limits (no `Fraction`, no dataclass arguments) the adapter must stay
  inside.
- Withholding. A source that is not the nemik pod serves whatever its forge serves, so withholding
  at the source (docs/withholding-at-source.md) is a condition for any public raw-file source, not an
  option.
- Authentication for a private forge's raw endpoint.
