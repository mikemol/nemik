# nemik web view: navigability and keyboard research (read-only)

## 1. Inventory: what exists now (src/nemik/web/index.html)

Keyboard / ARIA today:
- No `keydown` handler anywhere in the file. No `tabindex`. The only `.focus()` call is restoring focus to an umbrella toggle after a redraw (index.html:362-363).
- The canvas `#cy` (index.html:83) is not focusable; nodes are reachable by pointer only: tap selects (593), lane tap opens operator lane (594), dbltap toggles umbrella (596), hover lights cross edges (589-590).
- Keyboard fallback is the Cards list (W435, index.html:321-365): `<button data-card>` per visible card, salience-desc order (343), `aria-current` on the selected one (333, 352), umbrella toggle with `aria-expanded` (349). It sits in a section closed by default (111).
- Side panels are `<details>/<summary>` (W387, 85-115), so they are keyboard-operable.
- Repo chips are `aria-pressed` toggles (1084, 1093).
- One live region: `#legnote role="status"` (79). The Selected panel `#detail` (109) is NOT live, so selection changes are silent to a screen reader.
- Cite links (`<a href="#" data-cite>`, 1229-1231) route to `focusCite` (1232-1238) only for clicks inside `#wake` and `#goals` (1239-1242). Links rendered inside `#detail` (cite as, blocked on, waits on, is the block for: 1033, 1040, 1045-1047) and inside operator lanes (1014) have no handler: they are `href="#"` that do nothing (gap; also the obvious traversal edges).
- `focusCite` selects and centres the node but does not move DOM focus or update Cards `aria-current` (it calls `detail`, not `selectCard`) — two select paths that diverge (593 vs 325 vs 1232).
- The 60 s poll rebuilds the graph from scratch (597-602, 1262) and re-selects by id; any DOM-focus model must survive this the same way (keep a `focusedId`, restore after `draw()`).

Topologies/orderings the data already carries:
| Topology | Source | Order available |
|---|---|---|
| Dependency DAG (waitsFor / enables) | edges; `blocked_on` (1040); inbound blocks (1031, blocks.py:46 `inbound`) | upstream / downstream adjacency; topological rank used in layout (609-613) |
| Critical path(s) | critical.py:81 `critical`, :96 `critical_cards`, `cone` :58, `fires` :243; client `criticalSet` (189); `path_count` (1037); halo rings (223-262) | a linear chain per scope (head to tail), several scopes stacked |
| Salience / rank | flow.py:146 `solve`, salience.py:357, rank.py:397 `rank`, :421 `rank_fleet`; node `salience`, `band`, `rank_pos` (1036) | total order (Cards list already uses it, 343) |
| Enables forest / treemap | `treeOf` (619), `orderedTreemap` (660), `forest` (759) | single-parent tree: parent = heaviest thing it enables; children in rank order |
| Umbrella hierarchy | rank.py:286 `children`, :292 `is_umbrella`; rollup/expand (335-339) | tree, collapsible (tree pattern fits exactly) |
| Repo grouping | compound nodes; chips (1073-1093) with health status | repos list; cards within repo |
| Health per repo | health.py:40/45 | repo order by status (MARK at 1084) |
| Operator asks | blocks.py:295 `operator_asks`, categories :237; lanes (1006-1016) with `salience`, `same_ask`, `waiting` | per category, by salience |
| Goals / milestones | rank.py:249 `goals`, :206 `frontier`; Goals panel (1193) | goal -> frontier cards |
| Wake / liveness roster | `wake()` (1178) | repo list |
| Weather (shared outages) | `weather()` (1053) | outage -> waiters |
| Time | `last_activity` (1044), dtstart/due, History (1101) | chronological; not currently a navigable order |
| Cycles | critical.py:174 `cycles` | ring order |
| Spatial | Cytoscape positions | geometric nearest-neighbour |

## 2. Workflows -> topology and order

| Workflow | Topology | Natural order / step |
|---|---|---|
| W-a "What should I do next" | salience rank (fleet or repo) | linear, descending; Home = top |
| W-b "Why is X blocked / trace upstream" | DAG, waitsFor direction | depth-first up the blockers; branch choice among several blockers |
| W-c "What does landing X unblock" | DAG, enables direction (cone) | breadth-first down; or `fires` (critical.py:243) |
| W-d Walk the critical path | critical chain per scope | linear head->tail; switch scope = switch chain |
| W-e Triage operator asks | operator lanes | category, then salience; per ask: same_ask siblings, waiting-behind list |
| W-f Review a repo's health | repo grouping + health | repo list by status; inside, cards by rank or state |
| W-g Goal progress | goals -> frontier | goal list, then frontier cards |
| W-h Scan by recency | time (last_activity / ledger) | chronological desc |
| W-i Drill the umbrella / treemap structure | umbrella tree / enables forest | tree: parent/children/siblings, expand/collapse |
| W-j Cross-repo coordination ("who waits on me") | inbound blocks, cross edges | per repo, inbound then outbound |
| W-k Spatial "what's near this on screen" | layout geometry | arrow = nearest node in that direction |
| W-l Outage impact | weather | outage -> waiters |

Observation: W-b/W-c/W-i are *relational* (a cursor moves along edges from the current card); W-a/W-d/W-e/W-h are *sequential* (a cursor moves along a list). Common structure: every mode is a pair (ordering of a card set, adjacency relation for the current card). Lists are the degenerate case with adjacency = prev/next. That invariant is what lets one key map serve all modes.

## 3. Modal navigation model

### Invariant
A *mode* = (scope set S, primary order `next/prev` over S, optional relation `up/down` = parent/child, `left/right` = sibling in the current parent). The cursor ("focused card") is shared across modes: switching mode keeps the same card if it is in the new S, else jumps to the new mode's first item.

### Modes (proposed)
| Key | Mode | next/prev (Up/Down in list modes) | up/down/left/right |
|---|---|---|---|
| `1` / `m r` | Rank (default) | salience desc | — (left/right = previous/next repo boundary) |
| `2` / `m d` | Dependency | — | Up = a card it waits on, Down = a card it enables, Left/Right = cycle among the alternatives at that step (other blockers / other dependents) |
| `3` / `m c` | Critical path | chain order; Left/Right = other scope's chain | |
| `4` / `m a` | Asks | category then salience | Right = same_ask siblings / waiting list |
| `5` / `m t` | Tree (umbrella / treemap forest) | tree order | APG tree: Left = collapse/parent, Right = expand/first child, Up/Down = visible-row order |
| `6` / `m h` | Recency | last_activity desc | |
| `7` / `m g` | Repo | repo order (health), then cards | Left/Right = repo |
| (opt.) | Spatial | — | arrows = nearest node by geometry |

Dependency mode needs a breadcrumb (the path walked) so `Backspace`/`Alt+Left` retraces; without it a DAG walk is non-reversible (multiple parents).

### Choosing and showing the mode
- A radiogroup / segmented control in the header ("Navigate by: Rank | Dependency | Critical | Asks | Tree | Recent | Repo"), plus number keys. Current mode shown in it and announced.
- Mode is per-viewer state in localStorage (wrapped like 1248-1256).
- Mode may also be set implicitly: entering from an operator lane sets Asks; Enter on a goal sets Dependency/frontier. Keep implicit switches announced.

### Keys inside the graph widget
- Tab / Shift-Tab: move between page regions (header controls, graph, panels). Graph = ONE tab stop (roving model). Never step card-by-card with Tab.
- Arrows: per mode table above. Home/End: first/last in the mode's order (chain head/tail, top-ranked/last). PageUp/PageDown: jump 10 or to the next group (repo/category).
- Enter: commit selection (same path as tap: `selectCard`), opens Selected panel content; Shift+Enter or `o`: move DOM focus into the Selected panel (so the cite links there are reachable).
- Space: toggle umbrella (= dbltap, 596) where applicable; else select.
- Esc: layered — close popover (W462) -> clear breadcrumb / return to the card where the walk started -> leave graph to the mode switcher. Never clear selection on first Esc.
- Focus vs selection: focus = cursor (ring + popover), selection = pinned Selected panel. Separate like APG listbox with "selection follows focus" OFF by default, because detail() re-renders a big panel and screen readers would chatter. Offer a toggle.

### Implementation pattern
- `#cy` gets `tabindex="0"`, `role="application"` is tempting but avoid it (it disables SR browse keys globally). Prefer: a visually-hidden DOM mirror of the current mode (`role="listbox"`/`role="tree"`/`role="grid"`) with `aria-activedescendant` pointing at the focused card's mirror option, and draw the canvas focus ring from the same state. The Cards list (340-353) is already that mirror for Rank mode; generalise it to render the current mode's order instead of only salience.
- Roving tabindex on real buttons is the alternative; aria-activedescendant is better here because the poll rebuild (597) would destroy roving targets; activedescendant only needs the id to persist.
- Patterns: Rank/Recency/Asks/Critical = listbox (or grid if columns: state, salience, repo); Tree = tree (APG treeview, maps 1:1 to rollup/expanded); Repo = treegrid (repo rows expand to cards, columns health/counts); Dependency = no APG pattern fits a DAG — use a listbox of "neighbours of current card" grouped Waits-on / Enables, plus announced breadcrumb. That is honest about DAG shape.
- Announcements: one polite live region (reuse/extend `#legnote`, 79, or a dedicated hidden one) saying on cursor move: "<state> <cite>: <title>. Waits on 2, enables 3. Critical: yes. Salience 4.1, rank 7 of 52." Mode switch: "Dependency mode. Up: waits on, Down: enables." Rate-limit; do not make `#detail` live.
- Popover-on-focus (W462): show the same card popover on keyboard focus as on hover; it must be `role="tooltip"`-like non-modal, dismissible by Esc without moving focus (WCAG 1.4.13: dismissible, hoverable, persistent), and its text must equal the announced summary (one renderer, two sinks).
- Camera: on cursor move, `cy.animate` centre only if the node is off-viewport (avoid motion; respect prefers-reduced-motion).

## 4. Keyboard shortcut scheme

Conventions: GitHub/Gmail/Linear/Jira use single-key letter shortcuts, `?` help, `/` search, `g`-prefix goto chords, `j/k` next/prev; VS Code uses Ctrl/Cmd+K and command palette (Ctrl+Shift+P / Cmd+K in Linear); yEd/graph tools use arrows on selection and +/- zoom, `f`/fit.

Proposed (active only when focus is not in a text input; disabled by a "single-key shortcuts" toggle per WCAG 2.1.4):
- `?` help overlay (generated from the same keymap table, so it can't drift; test it like tests/test_skill.py does for the skill).
- `/` search/jump by cite or title (combobox, APG); Enter focuses that card (= focusCite, fixed to move focus).
- `j`/`k` next/prev in current mode (aliases of Down/Up for list modes); `h`/`l` left/right.
- `[` / `]` up/down the dependency relation from any mode (waits-on / enables) without switching mode — quick peek.
- `1`-`7` mode switch (or `m` then letter).
- `g` chords: `g n` next action (top of rank), `g c` critical head, `g a` asks, `g s` selected panel, `g r` repo picker, `g g` / `G` first/last.
- `x` or Space: expand/collapse umbrella. `Enter` select. `o` open Selected panel focus. `Esc` layered back.
- `f` fit, `+`/`-` zoom, `0` reset (graph only). `t` toggle treemap, `u` roll up (existing checkboxes, 76-77).
- `.` or `c` copy cite of focused card.
- Avoid: Ctrl/Alt chords that browsers or screen readers own (Ctrl+L, Alt+Left back, NVDA/JAWS Insert/CapsLock combos, VoiceOver Ctrl+Opt). Single letters are swallowed by SR browse mode anyway unless focus is in the application-ish widget; that is fine: document "press Enter/forms mode on the graph" in help. `h` collides with NVDA browse "next heading" only in browse mode — acceptable.
- Discoverability: `?` hint in the header stat line; `aria-keyshortcuts` on mode buttons; title tooltips naming the key; the help overlay lists per-mode arrow meanings.

## 5. Evaluating the earlier recommendation
(graph = one tab stop; up = waits-on, down = enables, left/right = siblings; Enter selects; Esc returns)

Fits:
- One tab stop: correct (roving / activedescendant), keep in every mode.
- Up/down = waits-on/enables is exactly Dependency mode, and matches the layout (prerequisite above dependent, 609-613), so spatial and logical agree there.
- Enter selects (= tap path), Esc returns: kept, Esc made layered.

Breaks:
- It is a single mode. For W-a (what next), W-d, W-e, W-h the user wants a list, and DAG arrows make "next by rank" unreachable without wandering.
- "Siblings" is undefined on a DAG: siblings w.r.t. which parent? A card with 2 blockers has two sibling sets. Needs the breadcrumb (the parent you came from defines siblings), and a rule at a root (fall back to rank-neighbours or repo-neighbours).
- Up/Down with multiple waits-on: which one? Needs a pick rule (critical one first, then highest salience) plus Left/Right to rotate among them — i.e. left/right means "alternatives at this step", not "siblings".
- In Tree/treemap mode the forest is drawn by enables-parent (617-618), where "parent" is downstream, so "up" visually = enables there — opposite of Dependency mode. That is the strongest argument that topology must be a mode: the same arrow can't mean both.
- Cross-repo edges and unclaimed placeholders (1020-1029) need explicit treatment (step into the "?" node, Enter shows the claim hint).
- Says nothing about announcements, poll survival, or popover.

## 6. Open questions for the operator
- Q1 Default mode: Rank (what next) or Dependency?
- Q2 Selection follows focus, or explicit Enter? (Recommend explicit.)
- Q3 Should mode be global or per-panel (e.g. Asks panel always asks order)?
- Q4 Single-letter shortcuts on by default (WCAG 2.1.4 needs an off switch)?
- Q5 Does Dependency mode cross repo boundaries freely, or stop and announce?
- Q6 Is spatial mode wanted at all, or only logical modes?
- Q7 Recency: last_activity, dtstart, or due — which clock?
- Q8 Should moving the cursor pan the canvas, or only when off-screen?

## 7. Atomization (smallest first)
- N1 Wire cite links everywhere: delegate `[data-cite]` clicks on `#detail` and lanes (fix gap at 1239). Next: extend the listener id list; browser test clicks a "blocked on" link.
- N2 Unify select paths: `focusCite` and tap call `selectCard` (325). Next: refactor + test aria-current updates from canvas tap.
- N3 Announce selection: polite live region with one summary renderer. Next: add hidden `role=status`, test text on select.
- N4 Keymap table + `?` overlay generated from it. Next: data structure + overlay, test every key listed.
- N5 Graph tab stop: `#cy` tabindex=0 + hidden mirror listbox with aria-activedescendant; Rank mode only, j/k/arrows/Home/End/Enter/Esc; focus ring drawn on canvas; survives poll (597). Next: reuse cardList order.
- N6 `/` jump-to-cite combobox. Next: APG combobox over cites/titles.
- N7 Mode switcher (radiogroup + number keys, localStorage). Next: framework with Rank only, then add modes.
- N8 Dependency mode with breadcrumb and alternative rotation. Next: pick-rule (critical, then salience) pure function + headless test.
- N9 Critical mode (chain per scope; Left/Right scope). Next: expose chains from criticalSet (189).
- N10 Tree mode = APG tree over umbrella/forest, Space toggles rollup. Next: map treeOf (619) to tree rows.
- N11 Asks mode over lanes (1006) incl. same_ask / waiting.
- N12 Recency and Repo (treegrid) modes.
- N13 W462 popover shares the summary renderer; shows on focus; Esc dismisses (WCAG 1.4.13).
- N14 g-chords, `[`/`]` peek, single-key off switch.
- N15 a11y-adversary review pass on N5-N13.
