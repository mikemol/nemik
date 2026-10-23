# The views worth printing to PDF (nemik:W891, W890)

The operator asked (2026-10-23) to have an agent render standard views to PDF, since the web
interface is not always within reach from a phone. This lists what the page can show and picks the
set `nemik-pdf` (W892) will print.

## What the page offers

The page has one graph and one card list, and every view is a setting of its header controls. There
is no URL state (no query string, no fragment): a view is reached only by setting the controls, so
the PDF command has to set them itself. The controls, by element id or name in `src/nemik/web/index.html`:

| Control | Id or name | Values |
|---|---|---|
| Show done and dropped cards | `showDone` | checkbox |
| Show operator blocks that do not need the operator | `showNoise` | checkbox |
| Show all cross-repo edges | `showCross` | checkbox |
| Order the forest by salience | `bySalience` | checkbox |
| Hops of blockers drawn around picked repos | `depth` | 1, 2 (default), 3 |
| Roll up umbrellas | `rollup` | checkbox |
| Treemap across the fleet | `treemap` | checkbox |
| Card list order | radios named `listmode` | rank (default), newest, critical, repo, asks, recent |
| Clock for the recent order | radios named `listclock` | last_worked (default), issued, last_activity |
| Repos picked | buttons inside `repos` | none lit shows every repo |

## The set to print

| Name | Settings | For |
|---|---|---|
| `fleet` | defaults, `rollup` on | the whole picture in one page |
| `treemap` | `treemap` on | where the load is, by repo and card |
| `repo REPO` | that repo picked, `depth` 2 | one workstream and what it waits on elsewhere |
| `asks` | `listmode` asks | the cards waiting on the operator, first |
| `rank` | `listmode` rank | what the fleet should work next |

Not in the set: `showDone` (a long history that no phone page needs), and `listclock` (it only
changes the order of the recent list).

## What W892 has to do with this

Because no URL carries a view, `nemik-pdf VIEW` sets the controls above through playwright after the
page's own ready event and then prints. The page also keeps some settings per viewer in browser
storage, so a print run uses a fresh browser context, which starts from the defaults in the table.
