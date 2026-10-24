# Where each control and section would go: the page's four views and a help drawer (nemik:W936, under W934)

`docs/page-structure.md` (W935) inventoried the page and proposed a principle: navigation follows
the questions the page is for, every control sits with what it acts on, and the interface is
self-similar across scales (fleet, repo, umbrella, card). This is the mapping that proposal asked for,
for the operator to react to **before** anything is built (W938). It is a proposal about a taste
question, not a decision. Marked **(read)** for what the inventory records of the page as of
2026-10-23 and **(mine)** for a placement or a reading.

## The places

| Place | The question it answers | Holds |
|---|---|---|
| **Queue** | What do I work next? | a repo's ordered ready cards (W932), its goals, every card in an order |
| **Orders** | What needs me? | the operator's asks, heaviest first |
| **Graph** | What waits on what? | the graph, treemap and their filters |
| **Health** | How is it going? | history, weather, wake, findings |
| **Help** | What does this mean, and how do I set it? | legend, keys, sources, settings |

Two things belong to no view because they apply to all: the **scope bar** (the repo chips, the trail
fleet, repo, umbrella, card that is also the way back up, and the jump-to-card form) and the
**selected card**, a detail pane any view can open, in one fixed place.

## Every header control (read), where it goes (mine)

| Control | Goes to | Why | At the level below (repo, umbrella, card) |
|---|---|---|---|
| show done/dropped | Graph | it changes which cards the graph includes | same: the closed cards under this scope |
| show operator blocks that don't need you | Orders | it is about asks that are not the operator's | same: the asks under this scope |
| show all cross-repo edges | Graph | it adds edges to the graph | same: edges leaving this scope |
| salience order | Graph | it orders the forest by the flow model | same: orders what is inside |
| hops of blockers | Graph | how far the graph follows waits out of a pick | same: hops from this scope |
| roll up umbrellas | Graph | it collapses containers; the page's one zoom gesture already | same, and it is the seed of the rule |
| treemap | Graph | another drawing of the same scope | same |
| card list order (six radios) | Queue | the list it orders lives in Queue; today it is at the top of the page and the list is the ninth section | same: orders the cards under this scope |
| clock for the recent order | Queue | it only means something beside the order it qualifies | same |
| relayout | Graph | it acts on the graph | same |
| status line, WebAssembly notice, live region | a footer, global | status of the page, not of a view; the live region stays global for assistive technology | not scoped |
| legend note and action | Help | reference, not a control of a view | not scoped |
| repo chips (17 toggles) | scope bar | they pick what every view shows | the first step of the trail |

## Every side section (read), where it goes (mine)

| Section (today's place) | Goes to | Why | At the level below |
|---|---|---|---|
| Legend (1, open) | Help, with a one-line key in Graph | reference; the graph needs a key beside it, the full table does not | not scoped |
| Weather (2, closed) | Health | outages the cards wait on: how things are going | outages the cards under this scope wait on |
| History (3, open) | Health | time series | this scope's weeks; for a card, its own ledger lines |
| Goals (4, open) | Queue | a repo's frontier and its on-deck leaf: what to work next | an umbrella's children are its goals |
| Wake (5, open) | Health, with its "N need you" line also in Orders | which repos are awake and what waits on them; the need-you line is an ask | for a card: who waits on it |
| Sources (6, closed) | Help | configuration | not scoped |
| Settings (7, closed) | Help | the viewer's preferences | not scoped |
| Selected (8, open) | the detail pane | one card, any view can open it | a card is the lowest scale |
| Cards (9, **closed**) | Queue | the closest thing to the queue, now ninth and shut | the cards under this scope |
| Findings (10, closed) | Health | the shape checks' output: how things are going | findings for this scope's cards |
| Queue (W932, new) | Queue, first | the ordered ready cards with their wait | an umbrella's children in rank order |
| keyboard-help dialog | Help | reference, not reachable from the header today | not scoped |
| jump-to-card form | scope bar | it works from any view and any scale | not scoped |

## What this changes

- The inventory counts sixteen header controls that act on something: seven on the graph and nine
  radios on the card list (the card list lives in the side panel, away from its radios). In the map
  each sits in the view it acts on.
- The side panel stops being ordered by when each section was added: reference and configuration
  leave the content area for Help; the queue, which was ninth and closed, is the first thing in Queue.
- "What needs me" gets a place of its own instead of being a combination of checkboxes.

## What I did not check, and what the operator has to judge

- **Whether the header controls keep their meaning inside an opened umbrella.** The self-similarity
  column is my reading of what each would mean, not something I tried on the page (as the inventory
  said). W938 builds each view with the WCAG chain test as its oracle, and this column becomes a
  test for it: at the level below, does the control still mean the same thing?
- **Is Orders its own view or a section of Health?** I made it a view because it is a question the
  operator asks on its own and because the asks must not hide in a status panel. If the operator would
  rather have four places, Orders folds into Health and the need-you line stays where Wake puts it.
- **Is the selected card a pane or a drawer?** It needs a fixed place; which one is a layout taste.
- **Wake splits across two places.** Its sleeping repos are health and its need-you line is an ask.
  If one section must stay whole it goes to Health and Orders links to it.
- **The count in "what this changes"** is from the inventory's list, not a fresh count of the page.
  The six card-list radios plus the three clock radios are the nine, so "orders" is one control to a
  reader and nine inputs to a counter.

## What follows

W937 holds a scale path and a view in the address so a view is linkable and the PDF command can pick
one; W938 builds the views one at a time, Queue first, each with the WCAG chain test as its oracle,
and the page files stay under their line ceilings, so the new code goes in new files.
