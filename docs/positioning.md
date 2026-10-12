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

## From MS Project and classic project management

### Concepts

| you know | in nemik |
|---|---|
| task | a card |
| summary task | an umbrella: a card blocked on its children; the web view can roll it up over its work |
| predecessor, finish-to-start link | `blocked_on` on the dependent, or `enables` on the prerequisite; both are the same edge |
| milestone | any card you rank toward, often an umbrella |
| critical path | `nemik-critical`: every card on any longest chain of open work, per fleet, repo, view or one card's cone |
| total float (slack) | the slack `nemik-critical` gives each open card: how far it can slip before it lengthens the path |
| baseline | a revision or date; `nemik-history --baseline` compares planned with actual since it |
| status report, RAG | repo health (red, amber, green) from declared thresholds, in `nemik-metrics` and on the view's repo chips |
| resource | a workstream (a repo and its agent session), and one shared scarce resource, the operator |
| Gantt chart | none on purpose (see below); the calendar export `nemik-ics` places cards that carry dates |

What nemik does differently on purpose:

- **No durations, no dates by default.** A card's length is one step; the critical path counts cards, not
  days. Work here is done by agents whose speed varies by orders of magnitude between cards, so a
  duration estimate would be a fiction the schedule then trusts. Dates appear only where a card carries a
  real one (a due date, an event), and those go to calendars, not to a Gantt.
- **No resource levelling.** Each repo works one card at a time and pulls its own next one, so there is
  no allocation to level. The one shared resource that does saturate, the operator, is measured instead:
  asks owed per repo, and the operator's own arrival, answer and wait rates.
- **The plan is the graph, and it is allowed to move.** Re-planning is minting, re-wiring and dropping
  cards in the queue, recorded as history; `--baseline` reports how far the plan's shape drifted rather
  than treating drift as failure.

### Workflow translation

| you used to | in nemik |
|---|---|
| open the project and find the critical path | `nemik-critical`, or `nemik-critical --repo R` for one repo |
| check a task's float | the slack column of `nemik-critical --json`, or the view's detail panel |
| set a baseline and track variance | `nemik-history REPO --baseline DATE`: planned, closed, dropped, still open, added since, and how the shape moved |
| ask "what if this task finishes now?" | `nemik-critical --assume-done repo:W<n>` |
| ask "what moves this milestone?" | `nemik-rank REPO --toward repo:W<n>` |
| find what an unplanned task pushed back | `nemik-critical --fires`: interrupt cards holding up planned work, and by how much |
| write the weekly status report | `nemik-metrics` (health per repo) and `nemik-history REPO --weekly` |
| link a task to another project's task | cite it as `repo:W<n>` in `blocked_on`; `nemik-inbound` shows the other repo who waits on it |

## From Jira, Bugzilla and issue trackers

### Concepts

| you know | in nemik |
|---|---|
| issue, ticket, bug | a card |
| project | a workstream: one repo and its queue |
| issue key (`PROJ-123`) | the cite `repo:W<n>`; a symbol is never reused, and a dropped card keeps its number in the residue |
| blocks / is blocked by | `enables` / `blocked_on`; a block on another repo names that repo's card |
| depends on an external team | `blocked_kind` agent (another repo's session) or human (the operator) |
| priority field | the band of the card's WV:1 vector, then the flow salience the ranking computes |
| triage queue | `nemik-operator`: every ask on the human, sorted needs-you, answered, condition, unstated, heaviest first |
| comment thread | the card's evidence, and letters in the repo's `inbox/` that a card cites |
| status workflow | ready, working, blocked, done, dropped; the transitions and who may make them are modelled in `src/nemik/data/workflows.toml` |
| JQL, saved filters | the RDF graph: `nemik-check`, `nemik-rank`, `nemik-critical` and the rest are queries over it |
| SLA | `nemik-check` warns on a blocking card when another repo has waited on it past the declared number of loop ticks |

What nemik does differently on purpose:

- **No central server, no write path.** Each repo's queue lives in that repo, written only by its own
  agent through `mikemol-paths-forward`. nemik reads all of them and writes none, so there is no shared
  database to lock, migrate or lose, and no second source of truth to drift.
- **Unanswered is a state the system sees.** An ask on another repo shows up in that repo's
  `nemik-inbound` as UNCLAIMED until a card there claims it, and a letter no card cites shows up the same
  way. Nothing waits silently in a queue nobody reads.
- **Priority answers to the graph.** A ticket's priority is not a field someone sets and forgets; the ranking
  re-derives it each tick from what is waiting on what.

### Workflow translation

| you used to | in nemik |
|---|---|
| file a ticket against another team | add a card that is `blocked_on` their `repo:W<n>`, or write a letter to their `inbox/` |
| see the tickets assigned to you | `nemik-inbound REPO`: what waits on this repo, claimed or UNCLAIMED, and uncited letters |
| accept a ticket from another team | run the `--add` line `nemik-inbound` prints: it mints a card that claims theirs |
| triage the incoming queue | `nemik-operator` for the human; `nemik-rank REPO` for an agent |
| run a saved filter for "stale and blocked" | `nemik-check` (stale blocks, SLA, saturation) and `nemik-starved` |
| close a ticket with a resolution | mark the card done with evidence; `nemik-witnesses --apply` closes cards whose declared witness holds |
| export to a spreadsheet | `nemik-serve`'s `graph.json`, or `nemik-metrics` for numbers |

The interplay of these moves is modelled as `workflow:peer-block` and `workflow:inbox-fold`.

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

## From multi-agent and swarm frameworks

### Concepts

| you know | in nemik |
|---|---|
| agent | a workstream: one repo, one Claude session on it, one queue |
| orchestrator, planner | none. Each repo's loop ranks its own queue against the fleet graph each tick |
| task handoff | a card `blocked_on` another repo's card, and that repo minting a card that claims it |
| message bus, mailbox | letters in a repo's `inbox/`, and peer messages between live sessions; a card cites the letter it answers |
| shared memory, blackboard | the queues themselves, read fleet-wide as one RDF graph by nemik |
| supervisor, human in the loop | the operator: a scarce resource with its own queue (`nemik-operator`), salience and load measures |
| agent liveness, heartbeat | `nemik-wake`: which repos are awake, idle or asleep, and what waits on the sleeping ones |
| tool permissions, guardrails | per-repo hooks (one writer per queue, the commit gate, the working-card rule), not a central policy |
| retries and dead letters | a block past the declared SLA warns on the blocker; an uncited letter shows UNCLAIMED until claimed |
| emergent coordination | the current-flow ranking: demand from every waiting card flows to whoever can do the prerequisite |

What nemik does differently on purpose:

- **No orchestrator.** Nothing assigns work or holds the plan. Every repo pulls from the same graph, so
  coordination survives any one session dying, and a dormant repo is a visible state, not a hang.
- **Durable state, not conversation.** An agent's working state lives in its queue file and ledger, not
  in its context window, so a session can be restarted, compacted or replaced and pick up where the
  queue says it was.
- **The human is modelled, not assumed.** The operator's attention is the scarcest resource, so asks on
  it carry the demand they hold back, duplicate asks are grouped, and a repo that piles up asks is warned.
  Most things that look like they need the human turn out not to, and the ask categories say which.
- **Read-only observer, many writers.** nemik never writes a queue; each repo writes its own through one
  writer. Integration with anything else follows the same rule: exports are files, imports are printed
  writer commands.

### Workflow translation

| you used to | in nemik |
|---|---|
| dispatch a task to another agent | add a card here `blocked_on` its `repo:W<n>`, or write a letter to its `inbox/` |
| poll for messages addressed to you | `nemik-inbound REPO` every tick: waiting cards and uncited letters, each with its claim command |
| check which agents are alive | `nemik-wake` |
| escalate to a human | file the card `blocked_on` an `operator: decide ...` or `operator: act ...` ask; it appears in `nemik-operator` |
| find who the whole system is waiting on | `nemik-critical` and `nemik-operator`, heaviest first |
| detect a deadlock between agents | `nemik-critical` lists dependency cycles; `nemik-check` warns on each card in one the operator cannot break |
| replay what the agents did | the ledger, and `nemik-history REPO` between any two revisions |

These moves are modelled as `workflow:peer-block`, `workflow:operator-ask` and `workflow:letter-as-evidence`.

## From schedulers and traffic control (Linux tc, I/O schedulers, ERP and MRP)

### Concepts

| you know | in nemik |
|---|---|
| a queueing discipline (qdisc) | the ranking's declared composition (`[order]` in `rank-weights.toml`): band first, then flow salience |
| strict priority | the priority band; an operator ask is deliberately NOT a strict tier but demand inside the flow, with a declared weight |
| weighted fair queueing | flow salience: a shared prerequisite's demand is split among the cards that need it, not counted in full by each |
| starvation, aging | `nemik-starved` reports ready cards overtaken past a declared age; there is no aging term in the order, by choice |
| a token bucket, admission control | arrival pacing, carded as W327 and not built: a declared limit on new cards per repo per day, reported against actual |
| backpressure | the operator-saturation warning, and the cross-repo SLA warning on a blocker's card |
| one runnable task per CPU | one `working` card per repo |
| MRP explosion | the `enables` cone of a card: everything it unblocks, transitively |
| MRP netting, what is already on hand | done cards drop out of the open graph; their edges show as satisfied |
| lead-time offsetting | none: nemik does not schedule in time (see the MS Project section) |

Where the analogy breaks, on purpose:

- **Cards are not packets.** Working a card changes the graph: it closes edges, mints new cards, re-wires
  others. A scheduler that assumed a fixed job set would be scheduling a graph that no longer exists, so
  the ranking is re-derived from the current graph every tick rather than held as a schedule.
- **The scarce resource is attention, not cycles.** The operator is the one shared server, and its
  service time is a human decision. nemik measures its queue and warns on its saturation, but does not
  try to schedule it.
- **Fairness is reported, not enforced.** Starvation, saturation and SLA breaches are findings someone acts
  on, not preemption. A deliberate ruling (dormancy is the operator's choice) is never overridden by a
  fairness rule.

### Workflow translation

| you used to | in nemik |
|---|---|
| read `tc -s qdisc` for drops and backlog | `nemik-history REPO --weekly`: opened versus closed, blocked share, implied wait |
| inspect the run queue | `nemik-rank REPO` (one repo) or `nemik-rank --all` (the fleet) |
| find the starved flows | `nemik-starved` |
| find the saturated link | `nemik-check`'s operator-saturation and cross-repo SLA warnings, and `nemik-metrics`' repo health |
| explode a bill of materials | `nemik-critical --card repo:W<n>`: that card's cone and its longest chain |
| check net requirements after a receipt | `nemik-critical --assume-done repo:W<n>`, `nemik-rank REPO --assume-done repo:W<n>` |

The tick that runs this pull loop in every repo is `workflow:rank-sync`.
