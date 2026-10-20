# Which page code is pure enough to share (nemik:W815, for the goal W812)

The plan (docs/wasm-pipeline.md): one Codon-compatible Python core of pure functions over plain
data; the CLI is a native facade over it and the page is a wasm facade over it. This is the
inventory of the page's JS against that: per top-level function, its size and whether its body
touches the graph object (`cy`), the DOM, the network or shared page state. Measured by a script
that matches those names in each function's text, so a "pure" row is a candidate to confirm, not a
proof; the 55 functions are `graph.js` (7, the treemap and forest moved there by W807) and the
rest of `index.html`.

## Pure over plain data (the candidates)

| Function | Lines | What it does | Python twin today |
|---|---|---|---|
| `treeOf` | 41 | each open card's parent is the heaviest open card it enables; weights | none |
| `orderedTreemap` | 44 | the ordered treemap of that forest, as rectangles | none |
| `criticalSet` | 43 | the cards on the view's longest chains, with heights | `critical.critical_cards(by_cite, scope)` (plain data in, `Critical` out) |
| `combine` | 33 | merges the fetched graph documents into one | `serve.to_json` builds the documents; the merge is the page's |
| `detailHTML` | 36 | the selected card's detail as HTML text | none (the CLI prints `--show` as JSON) |
| `findings`, `weather`, `weatherOnce`, `linked`, `lane`, `seriesBoard` | 9-16 each | text and small tables from the documents | `nemik-check` words the same findings; `luthenseries.board` is the series twin |
| `repoHue`, `luminance`, `esc` | 4-8 each | a colour from a name, a luminance, HTML escaping | none |

## Touch the graph, the DOM or the network (stay JS, the facade)

`treemap`, `forest`, `tile` (they place cytoscape nodes), `render` (268 lines), `cardList`,
`patchDraw`, `placeNew`, `afterDraw`, `selectCard`, `ringMap`, `fitReadable`, `labelInk`, the
popover and help functions, `load`, `history`, `sourceGraph`, `graphText`, `wake`, `goals`,
`citeLink`, `drawSources`. These stay JavaScript. Their pure cores are the candidates above: `forest`
and `treemap` call `treeOf` and `orderedTreemap`; `render` and `cardList` call `criticalSet` and the
list orders.

## The order to port

1. **Critical chains.** The Python exists (`critical.critical_cards`), so the first move is not a
   rewrite but a check: do `criticalSet` and `critical_cards` agree on the fixture fleet? If so the
   JS is deleted and the page calls the Python through wasm; if not, the disagreement is itself a
   finding. It is also the one with a CLI user (`nemik-critical`), so it proves the sharing.
2. **`treeOf` and `orderedTreemap`.** Pure, self-contained, 85 lines, no twin. Tested today only
   through the browser (`test_layout.py`), so the port starts with a plain-data test of the model
   that both the old JS (as the oracle, under node) and the new Python must pass.
3. **The HTML and text builders** (`detailHTML` and the small ones), which the CLI can print too.
4. **`combine`**, once the documents' shape is fixed by a schema both sides read.

## What a core function takes and returns

Plain data only: lists, dicts, strings and numbers, the JSON documents the page already fetches.
Not an rdflib `Graph`, not a path, not a process. The CLI builds that data from the queues and git
and prints the core's answer; the page fetches the same documents. `critical.critical_cards` already
has this shape (`by_cite: dict[str, Card]`), which is why it goes first.
