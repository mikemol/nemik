# What the web page's navigation says about its structure (nemik:W935, under W934)

The operator said (2026-10-23) that navigation on the page is a mess: every pane, top and side, "is
just a grab-bag", with no clear semantic relation to the page's structure or content, no organizing
principle, no intuitiveness, and no natural idiom to align to. This is the first part: an inventory
of what the page offers now and a diagnosis from it. It is built from `src/nemik/web/index.html` as
of 2026-10-23. Marked **(read)** for what I read in the file and **(mine)** for a reading.

## The inventory (read)

**The header** holds, in one row, in this order:

| Control | What it does | What it acts on |
|---|---|---|
| show done/dropped (checkbox) | adds closed cards | the graph |
| show operator blocks that don't need you (checkbox) | adds operator asks that are not yours | the graph |
| show all cross-repo edges (checkbox) | adds edges | the graph |
| salience order (checkbox) | orders the forest by the flow model | the graph layout |
| hops of blockers (select, 1 to 3) | how far to follow waits out of a picked repo | the graph |
| roll up umbrellas (checkbox) | collapses umbrellas | the graph |
| treemap (checkbox) | replaces the graph with one treemap | the graph |
| Card list order (six radios: rank, newest, critical, repo, asks, recent) | orders the **Cards** list | the **side panel** |
| Clock for the recent order (three radios, hidden until `recent`) | which stamp `recent` reads | the side panel |
| a status line, a notice about WebAssembly, `relayout`, a legend note and action, a live region | text and two buttons | various |
| repo chips (17, each a toggle) | picks the repos shown | the graph and, through Goals, the side panel |

**The side panel** is ten collapsible sections, in this order, with their default:

| # | Section | Default | Kind of thing it is |
|---|---|---|---|
| 1 | Legend | open | reference: what the marks mean |
| 2 | Weather | closed | status: outages the cards wait on |
| 3 | History | open (hidden until data) | status: time series |
| 4 | Goals | open | content: a repo's frontier, when a repo is picked |
| 5 | Wake | open | status: which repos are awake and what waits on them |
| 6 | Sources | closed | configuration: where the data comes from |
| 7 | Settings | closed | configuration: the viewer's preferences |
| 8 | Selected | open | detail: the card the graph or list has selected |
| 9 | Cards | **closed** | content: every card, in an order |
| 10 | Findings | closed | content: the shape checks' output |

Plus a keyboard-help dialog and a jump-to-card form, neither reachable from the header.

## What the inventory shows (mine)

1. **The header mixes four jobs in one row.** Seven controls change the graph (what to include, how
   to lay it out), nine change the order of a list that lives in the side panel, the chips pick which
   repos everything shows, and the rest is status text. A control does not sit next to the thing it
   acts on: the list order is at the top of the page and the list is the ninth section down.
2. **The side panel is ordered by when each section was added, not by what a reader does.** Reference
   (Legend) is first and open; the two configuration sections (Sources, Settings) sit between status
   (Wake) and detail (Selected); the card list, which is the closest thing to the queue the
   operator is trying to read, is ninth and closed by default.
3. **There is no top-level answer to "what am I looking at".** The page is one graph with panels
   around it. It does not say that it can show the whole fleet, one repo's queue, what needs the
   operator, or how things are going, though it contains all four; each is a combination of toggles.
4. **The same noun wears several names.** "Cards", "Goals", "Selected" and "Findings" are lists of
   cards at different scopes; "Wake" and "Weather" are status of different things; none says so.
5. **Nothing says what is on the page's own axis.** The three things the data is about are a
   workstream (a repo), a card, and an edge between cards, and the page's structure does not follow
   them: there is no place that is "a repo", no place that is "a card" except Selected, and edges
   are a layer on the graph and a checkbox.

## The principle proposed (mine, for the operator's judgement)

Let the navigation follow the questions the page is for, and place every control with what it acts
on. The questions, from what the operator has asked of it:

1. **What do I work next?** A repo's queue, in order (W929).
2. **What needs me?** The operator's asks, heaviest first (already `nemik-operator`).
3. **What waits on what?** The graph: cards, edges, repos.
4. **How is it going?** History, weather, wake, findings, and the forecast.

Four top-level views, as the one level of navigation (a `tablist`, so a screen reader and the keys
know it is a set of views), each holding its own controls: the graph's filters in the graph view, the
list order in the queue view. Reference and configuration (Legend, Sources, Settings, keys) leave the
content area for one help-and-settings drawer. A **selected card** is a detail pane any view can
open, as it is now, but with a fixed place. The repo chips are a scope that applies to every view.

**Self-similar across scales** (the operator, 2026-10-23: "the interface should be clearly
self-similar; the intuition that carries at a higher level perspective should continue to serve at
lower perspectives"). The data is already nested: a fleet holds workstreams, a workstream holds cards,
an umbrella card holds the cards beneath it, and a card holds its own steps. The four questions make
sense at every one of those scales: what is the order of the work *in this*, what in it needs the
operator, what in it waits on what, how is it going. So the rule is that a scale is not a different
page. One idiom serves all of them: the four views, the same controls in the same places, the scope
named at the top (fleet, then repo, then umbrella, then card, as a trail that is also the way back
up), and choosing a part of the view *zooms to that part* and shows the same four views for it. The
page has the seed of it already **(read)**: repo boxes are compound nodes holding their cards, and an
umbrella card is a node that collapses and, on a double click, expands to what it holds (W350, in the
Roll up umbrellas label), so a container opening to its contents is one gesture at two scales. It stops
there as far as I read: Goals follows the picked repos and Selected follows the picked card, but the
rest of the side panel does not change with the scale; whether the header's controls keep their
meaning inside an opened umbrella was not checked. The address (W937) then holds a scale path and a view,
and every control is judged by one test: at the level below, does it still mean the same thing?

This is a proposal, not a decision: it is one reading of a taste question the operator has to judge.
W936 turns it into a mapping of every control and section to a place, with the reason, for the
operator to react to before anything is built (W938).

## What this does not do

It does not look at the page in a browser, and it does not measure how readers use it; the
inventory is of the file. It does not say how a view switch should look or how it keeps its state
(the page has no URL state today, which W892 had to work around), and that is W937.
