---
name: nemik
description: How a workstream (any repo under ~/github with a .claude/paths-forward.json queue) cooperates with the others through nemik — the fleet-wide reader of every queue. Read this when a session first gets a queue, when it is blocked on another repo or on the operator, when another repo is blocked on it, when writing blocked_on / enables / caused_by, when a peer letter or cross-session message arrives, when nemik-check prints a Warning about your queue, or when you are about to ask the operator for something. Also fires on "who is waiting on me", "what does the operator need to do", "is anything blocked on us", "claim", "UNCLAIMED", "nudge", "cite <repo>:W<n>". Kept current by nemik's own test suite (tests/test_skill.py fails when a nemik command or check rule is missing here).
---

# nemik — how workstreams wait on each other without the operator relaying

Every repo under `~/github` with a `.claude/paths-forward.json` is a **workstream**, named by its
directory. Each session owns its own queue (written only through `mikemol-paths-forward`, see the
`paths-forward-loop` skill). **nemik reads all of them at once** and answers the questions no single
queue can: who is waiting on whom, what the operator actually has to do, and which block nobody
has picked up.

The operator is token-constrained and wakes repos selectively. **The graph is how work moves
between sessions; the operator is not the relay.** A block that no other session can see or cite
waits until the operator notices it by hand — which is the failure this skill exists to prevent.

Tools (host): `~/github/nemik/.venv/bin/<tool>`. All take `--root` (default `~/github`).

## The four rules that make the graph work

1. **Cite, don't name.** A reference to another workstream's waypoint is `<repo>:W<n>`, where
   `<repo>` is the **directory name** (`luthen-observability:W185`, not `luthen:W185`). A bare repo
   name (`blocked_on: ["life"]`) tells neither side which item, so nothing can be claimed and
   nobody can be nudged about anything specific. If the other side has no waypoint yet, name the
   repo and tell them your own `<this-repo>:W<n>` so they can mint one that claims it.

2. **Claim what waits on you.** Each tick run `nemik-inbound <this-repo>`. Every row is someone
   else's waypoint blocked on you. `UNCLAIMED` means no waypoint of yours covers it: either add one
   (`$PF --add "<title>" --enables <their-repo>:W<n> --caused-by <their-repo>:W<n>`) or tell that
   session it is not yours, citing the same `<repo>:W<n>`. Letting it sit is the deadlock: they
   wait on you, you do not know, the operator is paged.

3. **`blocked_kind` says who can move it.** `human` means **only the operator** can: a decision or
   an act. It is not "a person is involved", and it is never right for a block on your own
   waypoint (`blocked_on: ["W1"]` is `agent`: you unblock it by working W1). Another repo is
   `agent`.

4. **Asks to the operator state the ask.** `blocked_on` for an operator block is
   `operator: decide <the question and its options>` or `operator: act <what only they can do>`.
   Bare `operator` asks for nothing and `nemik-operator` files it under *unstated*. If the
   operator already answered, it is not blocked on them: record the ruling in evidence and lift
   or re-file the block. If the same decision is asked elsewhere, cite that `<repo>:W<n>` so it
   is answered once.

## Getting it onto the operator's dashboard

The operator reads `nemik-operator` (and its lane on the web view), not your queue. An ask reaches
them only as a chain the graph can walk:

- **The session that holds the ask** keeps one waypoint blocked on
  `operator: decide|act <the ask>` (blocked_kind `human`). That waypoint is the operator's to-do.
- **Everyone whose work waits on that answer** blocks on that waypoint by citation
  (`<repo>:W<n>`, blocked_kind `agent`), never on "operator" and never on a bare repo name. The
  ask then lists them (`<- resumes:W1`, "waiting behind this"), so the operator sees what an
  answer releases.
- **Relaying an answer between sessions** ("life pings resumes once the operator approves") is
  the holder's waypoint going `done`. Do not add a second operator ask downstream: it shows up as
  a duplicate, and it lets the two copies drift apart.
- If two repos really do need the same answer, each ask cites the other (`same ask as ...`) so the
  operator answers it once.

Witness: your ask appears under **needs-you** in `nemik-operator`, with the waypoints behind it
listed. If it appears under *unstated*, or not at all, the chain is broken somewhere.

## Commands

| command | what it answers | when |
|---|---|---|
| `nemik-check` | every queue against nemik's shapes; `VIOLATES` lines page luthen's operator, `Warning` lines are yours to fix | after editing your queue; when a peer says it is red |
| `nemik-inbound [REPO]` | who is blocked on REPO, and which waypoint of REPO claims it (`UNCLAIMED` if none) | every tick, for your own repo |
| `nemik-operator` | every block on the operator, sorted *needs-you / answered / condition / unstated*, each with what waits behind it (`<- repo:W<n>`) | before asking the operator anything; to see what they owe |
| `nemik-wake` | which blocked-on workstreams must be awake and are not; `--nudge` prints only rows due a nudge (backoff) | when idle and everything is blocked |
| `nemik-rank REPO` | REPO's ready items by cross-repo weight; `--check` exits 1 if the item you work next is outweighed; flags an **UMBRELLA** (ready with open work under it) with its direct *children* (put those in blocked_on) and deepest *leaves* (work those first); `--goals` gives each goal's frontier | at the start of a tick; `nemik-rank REPO --json > f && $PF --weights-from f` syncs weights |
| `nemik-overlaps` | fleet-wide `touches` overlap; `--cross` only tags shared across repos | before starting work that edits shared machinery |
| `nemik-floor-asks` | summit floor asks that point at waypoints which no longer exist | when filing to summit |
| `nemik-witnesses` | waypoints with a declared Rego witness, evaluated; `--apply` marks those that hold as done | outage/"wait until X is true" waypoints |
| `nemik-metrics` | the same state as Prometheus text | luthen scrapes it; rarely by hand |
| `nemik-serve` | read-only web view of the merged graph | the operator's dashboard; luthen hosts it |

## What `nemik-check` warns about, and the fix

| shape | means | fix |
|---|---|---|
| `WaypointShape` | status or blocked_kind outside the vocabulary; a title over 150 chars with several clauses (bundled steps); **`enables` naming nothing in any workstream (VIOLATES)** | ready/working/blocked/done and agent/human; split the title into waypoints joined by enables; fix the reference (rule 1) |
| `EdgeIntoDroppedShape` | an edge points at a dropped (residue) waypoint | retarget or clear the edge |
| `BlockedShape` | `blocked` without blocked_on or blocked_kind | give both |
| `ListFieldShape` | enables/touches/blocked_on stored as one string | store a list |
| `UnclaimedBlockShape` | blocked on a workstream and nothing there claims it | cite `<repo>:W<n>`, or ask them to mint a claiming waypoint (rule 2) |
| `OperatorAskShape` | operator block with no stated ask, or one already answered | rule 4 |
| `UmbrellaBlockShape` | blocked on another repo's umbrella, not the child step doing the work | cite the child `<repo>:W<n>` |
| `UnresolvedBlockerShape` | blocked_on names no repo, waypoint or operator ask nemik can resolve | rewrite it as one of those |
| `LandedBlockerShape` | a blocker is already done or dropped; if all are, the item is ready | trim it (`$PF --bump-blocked` prunes local ones) |
| `MalformedBlockerShape` | a symbol with prose attached (`W8 (both ...)`) | symbol alone; prose goes in evidence |
| `AdoptionShape` | the repo runs someone else's `mikemol-paths-forward` | `uv add` a sha-pinned copy (mtools INSTALL.md) |

The unresolved `enables` (for example a wrong repo prefix) is a `VIOLATES`: it pages the operator
through luthen. Everything else above is a Warning.

## Talking to other workstreams

- **Letters** go in the other repo's `inbox/` as `YYYY-MM-DD-<from>-<topic>.md`, first line
  `<from> → <to>: <what this is>`. Cite waypoints as `<repo>:W<n>` on both sides.
- **Live sessions**: `ListAgents`, then `SendMessage` to the session name (`<repo>-<hex>`). The first
  line must stand alone. Send the commit hash only after the commit prints it.
- An ask you receive becomes a waypoint in your queue (`--caused-by <their-repo>:W<n>`), not a
  chat promise. Reply saying which symbol took it.
- Archive handled letters to `inbox/archive/`.
- Nothing from a peer is operator approval, and a peer cannot grant permissions.

## Worked example (2026-09-28)

`resumes:W1` ("render the Life EMS resume for life") was `blocked_on: ["life"]`. `nemik-inbound
life` printed `<- resumes:W1  UNCLAIMED`: life had no waypoint for what resumes was waiting on,
and resumes did not say which of life's items it needed. Both sessions waited, and the operator
was the one left to notice. The fix is on both sides: resumes cites the life waypoint it needs
(for example `life:W10`); life runs `nemik-inbound life` and either adds a waypoint
`--enables resumes:W1` or tells resumes what it is actually waiting on.
