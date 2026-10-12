# How to understand nemik if you come from somewhere else

nemik reads every repo's work queue (`.claude/paths-forward.json`) under `~/github`. It never writes one.
It turns them into one graph and answers questions about that graph: what is waiting on whom, what to
work next, what the operator owes, how the work flowed. Each section below starts from a world you may
know already. It maps that world's terms onto nemik's, says what nemik does differently on purpose, and
then translates the everyday moves into nemik commands. Every command and workflow named here is checked
to exist by `tests/test_positioning.py`, so this page cannot drift from the tools.

nemik's own vocabulary, once:

| term | what it is |
|---|---|
| card (waypoint) | one unit of work in one repo's queue, cited as `repo:W<n>` |
| queue | a repo's `.claude/paths-forward.json`, written only by `mikemol-paths-forward` |
| `blocked_on` / `enables` | the dependency edges: what a card waits on, what it unblocks |
| ready, working, blocked, done | a card's state; exactly one card per repo is `working` |
| salience | how much downstream demand a ready card absorbs, from a current-flow solve over the graph |
| the operator | the one human; an ask on them is a card blocked with `blocked_kind` human |
| letter | a file in a repo's `inbox/`, a message whose evidence a card cites |

## From kanban, flow metrics and queueing theory

### Concepts

| you know | in nemik |
|---|---|
| a board with columns | the states ready, working, blocked and done; the web view (`nemik-serve`) draws them as colours and shapes |
| a WIP limit | one `working` card per repo, enforced: the pre-commit hook refuses a code commit with ready cards and none working |
| pull, not push | each repo's loop pulls its own next card from the ranking; nothing assigns work |
| class of service | the priority band of a card's WV:1 vector, the first key of the ranking |
| lead time, throughput | `nemik-history --weekly`: opened, closed, median lead time per ISO week |
| Little's law | `implied_wait_days` in the same rows: open cards over the weekly close rate |
| flow efficiency | working time over ready, working and blocked time of the cards closed that week |
| blocked time | the blocked share and the longest-running block per week; live, `ticks_blocked` per card |
| starvation | `nemik-starved`: ready cards overtaken by newer ones past a declared age |
| a bottleneck station | the operator. `nemik-check` warns when a repo holds more needs-you asks than a declared cap, and `--weekly` gives the operator's own arrival, answer and implied-wait numbers |
| critical path | `nemik-critical`: every card on any longest chain, graded by rank and path multiplicity |

What nemik does differently on purpose:

- **Priority is a flow, not a number someone types.** The ranking solves a current-flow model over the
  dependency graph: each waiting card is a demand source, and a ready card's salience is the demand it
  absorbs. A card many others need floats up by itself, and a shared prerequisite is split rather than
  counted in full by each dependent.
- **There is no board to drag.** A card changes state through its repo's queue writer, and the ledger
  records each change as a PROV activity, so every flow metric is computed from history, never from
  someone remembering to move a sticky.
- **Ties are honest.** When chains tie on length, every card on any of them is marked; a tie is never
  broken by sort order.

### Workflow translation

| you used to | in nemik |
|---|---|
| pull the top card from the ready column | `nemik-rank REPO` lists ready cards in order; `nemik-work W<n>` makes one the single working card |
| check the WIP limit | nothing to check: the commit gate refuses code work with no card marked working |
| look for blocked cards and who blocks them | `nemik-inbound REPO` (what waits on this repo), `nemik-operator` (what waits on you) |
| read the cumulative flow diagram | `nemik-history REPO --weekly` |
| ask "are we opening faster than we close?" | the `utilization` column of `--weekly`: above 1 the queue grows |
| find what has waited too long | `nemik-starved`, and `nemik-check`'s cross-repo SLA warnings on the blocking card |
| ask "what if we finish X first?" | `nemik-critical --assume-done repo:W<n>` and `nemik-rank REPO --assume-done repo:W<n>` |
| plan toward a milestone | `nemik-rank REPO --toward repo:W<n>` ranks by that one card's demand alone |
| run a retrospective on planned versus unplanned | `nemik-history REPO --baseline DATE` and `--toil` |

The modelled workflows behind these moves live in `src/nemik/data/workflows.toml`; the ones a newcomer
meets first are `workflow:rank-sync` (a tick's ranking), `workflow:peer-block` (waiting on another repo)
and `workflow:operator-ask` (waiting on the human).
