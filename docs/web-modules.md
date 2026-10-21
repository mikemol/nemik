# The page, by concern (nemik:W800, for the decomposition W799)

`src/nemik/web/index.html` is 1879 lines: a style block (lines 10 to 91), the markup (93 to 166)
and one script (167 to 1877). The operator ruled it too large to read in chunks (2026-10-20).
This is the map the split works from. Line numbers are as of that day; the order of the script is
the order below.

## The script, by concern

| Concern | Lines | What is in it |
|---|---|---|
| Constants and state | 169-202 | `LANE`, `STATES`, the mutable `data`, `cy`, `selectedId`; the glyph tables `STATE_MARK`, `ROLLUP_MARK`, `BEHIND_MARK` |
| Small helpers | 203-238 | `esc`, `paint` (the redraw-only-what-moved writer), `openSecs` (which side-panel sections are open) |
| Layout constants and scopes | 239-271 | `PAD`, `RULER_DOT`, `SCOPES`, `viewChain` |
| Critical chains | 272-350 | `criticalSet`, `computeChains`, `LIST_ORDER` (the card list's orders) |
| Rings and ink | 351-473 | `ringMap`, `ringSvg`, `fitReadable`, `luminance`, `labelInk`, `refreshRings`, `markChainEdges` |
| Selection | 474-503 | `selectCard`, `focusCite`, `toggleUmbrella` |
| Card list | 504-613 | `cardList` and its focus, keyboard and click handlers |
| Render and patch | 614-999 | `render`, `light`, `markCross`, `syncData`, `patchDraw`, `placeNew`, `afterDraw` (the in-place poll follow, nemik:W494) |
| Treemap and forest | 1000-1390 | `treeOf`, `orderedTreemap`, `treemap`, `forest`, `tile` |
| Lanes, detail, popover | 1391-1430 | `lane`, `detail`, `popSoon`, `popShow`, `popHide` |
| Help, keys, list order | 1431-1502 | `openHelp`, `closeHelp`, `ACTIONS`, `showCards`, `pickListMode`, `KEYMAP` |
| Detail HTML, panels | 1503-1585 | `detailHTML`, `weather`, `findings`, `chips` |
| Data load | 1586-1735 | `history`, `sourceGraph`, `graphText`, `combine`, `load` |
| Boards and links | 1736-1844 | `seriesBoard`, `wake`, `goals`, `linked`, `weatherOnce`, `citeLink` |
| Sources | 1845-1877 | `DEFAULT_SOURCES`, `saveSources`, `drawSources` |

## Who reads the page as text

These tests and publishers open `index.html` and match on its text, so a move has to keep what they
look for, or move the look with it:

- tests: `test_static.py`, `test_publish.py`, `test_wcagfacts.py`, `test_wcag_marks.py`,
  `test_lanes.py`, `test_staticserve.py`, `test_wcag_focus.py`, `test_wcagjudge.py`,
  `test_file_url.py`, `test_layout.py` (and `test_test_inputs.py`, which lists the files tests open);
- publishers: the static build (`serve.build_static`) checks the page for its markers and copies it,
  and the live server answers `/` with it.

## The order of the split (W799's children)

1. W801: the live server, the static build and the OpenAPI list carry extra page files first; nothing
   moves until a moved file would be served.
2. W802: the style block to `style.css`.
3. W803: constants, helpers, critical chains, rings, render and patch, treemap, forest to `graph.js`.
4. W804: selection, the card list, lanes, popover, help and keys to `cards.js`. Only definitions move:
   the statements that wire the page when it loads (`addEventListener` on the card list, the popover,
   the key handler, the list-order radios) stay in `index.html`, because they need the DOM and the
   helpers the inline script defines (`esc`, `paint`), and a classic script in the head runs before
   both.
5. W805: detail HTML, the panels, data load, boards, links and sources to `panels.js`.
6. W806: a line ceiling per file that only falls (`tests/test_web_size.py`).
7. W808, W809, W810: the rings and ink, the scopes, critical chains and list orders to `graph.js`;
   render, the in-place poll follow and the draw helpers to `render.js` (graph.js would have passed
   900 lines). `index.html` is then the markup and the statements that wire the page at load.

The script is global `function`s and `let`s today, so the first split keeps them global by loading
the modules as classic scripts in order; turning them into ES modules is a later, separate step.
