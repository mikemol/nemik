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

## The card lifecycle

A waypoint is `ready`, `working`, `blocked`, `done` or `dropped`, and every change goes through
`$PF --update W<n>` (or `--drop`). The model is `src/nemik/data/workflows.toml`, and
`tests/test_workflows.py` fails if this section and the model disagree.

- **Start a card: `--update W<n> --status working`.** Exactly one card is working at a time.
  `nemik-check` warns when items are ready and none is working, and when more than one is; a commit
  that changes code or tests while ready cards exist and none is marked working is refused by the
  pre-commit hook. A card that stays `working` after it lands is the same lapse, so close it.
- **Finish: `--update W<n> --status done --evidence-append "<what a stranger can check>"`.** A commit
  hash, a path, a command and its output; "looks right" is not evidence.
- **It waits on someone: `--update W<n> --status blocked --blocked-kind agent|human --blocked-on <who>`.**
  `blocked_on` and `blocked_kind` are both required (the four rules above say how to write them).
- **The wait ends: `--prune-landed --root <fleet root>`** trims landed blockers, local and foreign, and returns the card to `ready` once none is left. `--bump-blocked` only counts ticks; do not run it as the remedy.
- **It no longer earns its place: `--drop W<n> "<reason>"`.** The reason is required and kept as
  residue; the symbol is never reused.

## Commands

| command | what it answers | when |
|---|---|---|
| `nemik-check` | every queue against nemik's shapes; `VIOLATES` lines page luthen's operator, `Warning` lines are yours to fix | after editing your queue; when a peer says it is red |
| `nemik-check --realizability` | each live waypoint's realizability coordinate (none < constructible < reachable < observable < coverable) and its residue ledger: per gate, what is missing and what closes it, judged by mtools' policy under the pinned opa; the first line says the `as_of` and policy sha used, and each row says `(mark)`, `(derived)` or `(stale)` against the writer's `.claude/paths-forward.marks.jsonl` (a stale mark is named, never read as current); exit 0 all runtime-valid, 1 residue, 2 not judged | before marking a card done; to see why a card sits at its coordinate |
| `nemik-pins`'s host line (W379) | `host installs nemik@<sha>: behind N`, read from uv's receipt for the host install of nemik's tools (`~/.local/share/uv/tools/nemik/uv-receipt.toml`, `--receipt` to point elsewhere), and when behind, the `uv tool install --force 'nemik @ git+file://...@<HEAD>'` that levels it; counts toward `--max-behind` | after nemik lands a change other repos run by name; reinstalling is deliberate, never a post-commit action |
| `nemik-inbound REPO`'s letter rows (W376) | besides the waypoints waiting on REPO, each letter in REPO's inbox that no waypoint cites (dated within 14 days) prints as `REPO <- letter <file> UNCLAIMED -- claim with: <the --add>`; run the printed command (it sets caused_by to the letter) or answer the sender | every tick, in the same step as the waypoint rows; older letters are `nemik-check --letters --fold`'s |
| `nemik-work W<n> [--state FILE] [--dry-run]` | makes W<n> the ONE working card in one command: every other working card goes back to `ready`, then W<n> is marked `working`, all through mikemol-paths-forward (it never edits the queue file); prints each update (W330) | at the start of a card, instead of two `--update` calls and the "more than one working card" warning |
| `nemik-pacing` | each repo's new cards against a declared pace, read as a token bucket: `[pacing]` in rank-weights.toml declares a rate per day (50), a burst on top (150) and a window (14 days); the bucket starts full, refills at the rate, and each new card (`issued_at`) takes a token; prints new cards, how far over the bucket went, tokens left now, and `OVER PACE NOW` while it is negative. Report only; enforcing a pace is a separate decision (W327) | when a repo seems to mint faster than it closes, or after a bulk import |
| `nemik-export` | the cards as MS Project XML (MSPDI) on stdout, for MS Project, ProjectLibre or GanttProject (W365): each card a task, each blocker a finish-to-start PredecessorLink, a blocker in another repo a CrossProject link, done cards at 100%; `--repo R` (repeatable) exports only those repos. `--format issues` prints issue-tracker JSON instead (W366): one issue per card with its cite, open/closed, the repo as a label and `blocked_by` cites, the shape GitHub's and Forgejo's dependency endpoints take. No dates or durations are invented. Read-only: nothing is written back | to look at a repo's queue in a Gantt tool, or hand a plan to someone who uses one |
| `nemik-import` | `--from mspdi|issues FILE [--state Q]`: prints (never runs) the `mikemol-paths-forward` commands that bring another tool's tasks into queue Q (W367): an `--add` per task with `--caused-by <format>:<file>#<uid>`, then `--update` lines setting blockers by the symbols the adds will get (predicted from Q's counter) and done tasks. A task whose source id a card already carries is skipped, so a re-import prints only what is new. Review, then run the lines | to bring a plan made in a Gantt tool or an issue tracker into a queue |
| `nemik-exports --withheld FILE --out DIR [--root R]` | writes each repo's version-2 export (`DIR/<repo>.json`: the cards not withheld, and the repo's withheld refs) from the queues and luthen's version-1 withheld list (W635), the compatible-first step of docs/withholding-at-source.md. `nemik-serve --static\|--publish --exports DIR` then withholds every card a repo's export does not publish; a repo with no export publishes none of its cards. A build from the derived exports equals a build from the version-1 list (tests/test_exportcli.py) | when the pod's build should read per-repo exports and the repos do not emit their own yet |
| `nemik-ask --filer REPO --to REPO --slug SLUG --claim TEXT [--owner-card W<n>] [--apply]` | file an ask to summit's floor mechanically: with `--apply` it mints the FILER's waypoint through the one writer (blocked on the owner, or on `<owner>:W<n>` when `--owner-card` is given) and then writes `floor/inbox/<slug>.bib` (`kind=ask by=<filer> to=<owner>`, `waypoint = {<filer>:W<n>}`) in the form summit's place_intake validates; a dry run prints both; it refuses a bad slug, unbalanced braces in the claim, or an existing entry (W587) | when you have an ask for another repo, instead of hand-writing the entry and the card |
| `nemik-replica [--repo PATH]` | the image test stage's verdict for the pushed sha: reads `.git/image-replica.last` (written by tools/image_replica_runner.sh, which post-commit starts detached) and the `origin/main` ref, prints GREEN, RED, STALE or NONE, and exits 1 on RED; read-only, so a tick files `--gate-red` or `--gate-green` from what it says (W594) | at a tick, after pushes, to learn the image failed minutes after the push instead of when the forge's build reaches it |
| `nemik-starved [repo ...] [--days N] [--json]` | lists ready cards that waited past the declared age (`[starvation] days` in rank-weights.toml, 14) while newer-issued cards ranked above them, with how many overtook each; reporting only, ranking has no aging term (W326) | when a low-weight ready card seems to sit forever |
| `nemik-critical [--repo R] [--card <repo>:W<n>] [--assume-done <repo>:W<n> ...] [--json]` (`--fires` lists each open interrupt-minted card that holds up planned, tick-minted work downstream, with how many cards longer the critical path is while it stays open, heaviest first: the planned work fires delay; W347) (`--assume-done` is a what-if: the path length, the cards that leave or join a longest chain, and how many open cards' slack changes if the named cards were closed; W351) | the critical path through the open dependency graph, fleet-wide (`--repo` bounds it to one repo's own cards, `--card` to one card's cone, everything it transitively waits on and everything waiting on it; both together intersect; W333): every open card counts one step, every card on ANY longest chain is printed, one line per rank, with tied alternatives joined by `|` and counted `(xN tied)`: the dependency order is a poset, so equal chains are alternatives, never ranked by sort order (W344; `--json` has each card's rank and the number of longest chains through it), and each card's slack (how far it can slip before it lengthens the path; 0 = on a longest chain; `--json` has every card's) is the measure a project lead calls float (W313). It also lists the dependency cycles among open cards (W324): a cycle cannot clear by itself, since every card in it waits on another; one with a member blocked on the operator (blocked_kind human) is marked "operator can break" (the `same ask as` convention makes two asks cite each other on purpose), any other is a DEADLOCK, and a cross-repo one is flagged | to see which chain bounds the fleet, and which work can wait without costing anything |
| `nemik-pins [REPO...] [--max-behind N]` | for each `git+https://github.com/<owner>/<peer>[.git]@<sha>` pin in a repo's pyproject.toml or MODULE.bazel, how many commits that peer's local clone HEAD is ahead of the pinned one (`unknown` when the peer is not cloned under the root or lacks the commit); exit 6 when any pin is more than N behind. Reads clones only; whether the peer published that HEAD is not asked | to answer "is my pin of paperkit or mtools stale, and by how much" (W273, gcalculus:W225) |
| `nemik-check --committed [REPO...]` | prints the `provenance: queue <repo> ...` lines and exits 4 when any named repo (none named: every repo) is read from an uncommitted or untracked queue, 0 when each is at its last commit; validates nothing | to assert a claim about a peer rests on what the peer committed, never on its working tree (W272, gcalculus:W224) |
| `nemik-check --letters` | reads every `<repo>/inbox/*.md` first line (`from → to:` or `->`) and exits 5 when a letter sits in an inbox other than the one it names, or names no workstream; prints how many letters have no header. Receiving side only: a letter never put in any inbox is invisible here. `--fold` adds, for every letter whose file name no text of its repo's queue contains (a letter is a waypoint's evidence in file form, W275), the `--add ... --caused-by inbox/<file>` that would give it a waypoint; an orphan whose references to its own repo's waypoints are all closed is listed as an `mv` into `inbox/archive/` instead; it prints and applies nothing. `--repo REPO` scopes it to one inbox (each repo migrates its own, W282) and `--older-than DAYS` also makes an uncited letter whose file name is dated more than DAYS days ago stale (an `mv`), never a card: nothing cited it, so it produced no work. `--apply` (with `--fold`) carries the plan out: each live letter's waypoint is minted through mikemol-paths-forward and each stale letter moved to `inbox/archive/`; idempotent, since a cited letter is no longer an orphan (W301). A machine alert pair (`...-alert-<name>-opened-<id>.md` with a `-resolved-<id>.md` dated the same day or later) needs no card: both are stale, an opened with no resolved twin stays live. `--repo` also scopes the MISDELIVERED lines to that repo. A misdelivered letter whose header names a workstream is delivered by COPY into that workstream's `inbox/` (the plan prints `cp` lines, `--apply` copies; the sender keeps its copy, a waypoint there may cite it), and once the recipient holds it the letter no longer counts as misdelivered (W310). With `--older-than 14` the fleet on 2026-10-10 was 69 live, 147 stale. If the nemik-inbound hint shows a "Fold <repo>'s inbox" row waiting on you, run `nemik-check --letters --fold --repo <you> --older-than 14`, apply the `mv` lines, mint or claim a card for each `--add` line | after writing a letter, to see it landed where it says (W271, gcalculus:W224). A letter counts as owned when any waypoint in the fleet cites its path (`<repo>/inbox/<file>.md`); plain `nemik-check` warns "cites the letter <path>, which is not under the root" when a waypoint cites a letter that does not exist (a file moved to `inbox/archive/` still resolves) |
| `nemik-inbound [REPO]` | who is blocked on REPO, and which waypoint of REPO claims it (`UNCLAIMED` if none); each row ends `[letter: <path>]` for every letter file (`<repo>/inbox/<file>.md` or `.claude/letters/<file>.md`) the waiting waypoint cites in its evidence or next step: a letter is a waypoint's evidence in file form (W275), so cite the file in evidence (or pin it with `mikemol-paths-forward --update W<n> --attach PATH`, mtools:W930, which stores `attachments: [{path, sha256}]`) and the recipient is shown it. The `--json` rows carry `letters`; the served and published documents do not | every tick, for your own repo; when you ask a peer, put the letter path in the waiting waypoint's evidence |
| `nemik-stackable REPO` | which of REPO's ready cards one `mikemol-commit --stack` can carry now: in rank order, the cards whose declared manifests (`$PF --update W<n> --manifest <exact file>... --size small\|medium\|large`, mtools:W1426) are pairwise disjoint and disjoint from the files already staged; prints `STACK` or `WAITING` per planned card and a total with the count of ready cards that have no manifest. Greedy in rank order, not the maximum set (W613). `--propose` drafts a manifest for each ready card without one from its next step's file mentions, its `file:<path>!w` touches and the files its citing commits touched (bare names resolved against git's tracked files), printed as `--manifest` flags for you to confirm, never written: declaring it is the planning act. A repo's generated files (`.claude/generated.json` = `{"version": 1, "generated": [{"path": <exact file>, "generator": <command>}]}`, W624) leave the overlap test and print as `last entry carries: <file>`, because every card that regenerates one would otherwise conflict with every other | before building a stack, to see what can ride together; write a stack file from its STACK lines |
| `nemik-operator` | every block on the operator, sorted *needs-you / answered / condition / unstated*, each with what waits behind it (`<- repo:W<n>`) and a leading number: the flow-model salience the ask absorbs, i.e. the demand (nemik-rank's units, class weights of rank-weights.toml) that answering it would release; heaviest first within a category (W298). An ask that itself waits on another open card shows 0, its demand flows to that card. The `--json` rows, `/operator` and the lane panel carry `salience` | before asking the operator anything; to see what they owe, heaviest first |
| `nemik-wake` | which blocked-on workstreams must be awake and are not; `--nudge` prints only rows due a nudge (backoff); `--alarms` lists alarms fired on open waypoints, and `--alarms --nudge` only firings not yet delivered (each delivered once) | when idle and everything is blocked |
| `nemik-rank REPO` | REPO's ready items in the declared composed order (`rank-weights.toml [order]`: Pareto fronts over priority band and cross-repo weight; an operator ask is NOT a tier above them but a demand source inside `weight` with the declared `operator` class weight (15, nemik:W249; the strict tier is one declaration away), so it rises within its band and responds to the model; `weight` is the exact current-flow salience (`[order] weight = "flow"`, nemik:W241; `"downstream"` is the old transitive sum, kept as the comparison arm); `--json`'s `weight` is that order, `downstream` the raw sum); `--check` exits 1 if the item you work next is outweighed (DRIFT), sits below the `bands.toml` floor while a ready item at the floor exists (INVERSION), or shares a touches surface with an open `trust-boundary` item (POLICY; each names the pair), and prints `UNSCORED <n>`, open items with no vector; flags an **UMBRELLA** (ready with open work under it) with its direct *children* (put those in blocked_on) and deepest *leaves* (work those first); `--goals` gives each goal's frontier; `--band VECTOR` or `--item repo:W<n>` names the priority band (and the rule) for any vector or waypoint, open or done; `nemik-rank --all` (no REPO) puts every workstream's ready items in one cross-repo order, the host visitor's view of what the fleet should work next (nemik:W202); `nemik-rank REPO --flow` prints the flow model's exact salience (shown rounded) beside the old downstream weight for each ready card and every pair the two order differently, the audit before the model replaces the ranking (nemik:W240); `--assume-done repo:W<n> ...` ranks as if those cards were closed, a what-if (nemik:W351); `nemik-rank REPO --toward repo:W<n>` ranks by the demand of that ONE milestone card alone (an umbrella is a milestone already), so the order reads as what moves it, with no operator or residue demand added (nemik:W316); `nemik-rank REPO --ask repo:W<n>` shows what that waiting card (an operator ask) needs, as the ready cards that absorb its demand, and which of REPO's ready cards sit lower because of it, so an ask is read inside the model rather than as a tier above it (nemik:W244); `--flow --workable` grounds only cards in state ready or working (the ranking's own ground: a card blocked outside the graph absorbs nothing, nemik:W252) and `--flow --residue` adds each recorded realizability gap as demand at its card, weighted by gate from `rank-weights.toml [residue]` (nemik:W251, W253; an audit option, off in the ranking: unit weights ranked paperwork) | at the start of a tick; `nemik-rank REPO --json > f && $PF --weights-from f` syncs weights, and must be re-run after any status change (working, done, a new item): the stored weight is a rank position, so a change renumbers it |
| `nemik-days [N]` | the next N days of the operator's calendars opted in via `~/.config/nemik/calendars.toml`, each event with the waypoints blocked on it (`blocked_on: cal:<label>/<uid>`); a calendar may carry `include = [patterns]` (case-sensitive substrings of the summary) in `calendars.toml`, and a filter that keeps nothing prints `0 of N matched`, not a free day; an entry repeated in two calendars is one row (`[also: ...]`; `--no-dedupe` shows every copy); host-side only, never served | to see what a `cal:` block is waiting for |
| `nemik-calendar-write [--apply]` | writes the open dated waypoints (`dtstart`/`due`, alarms, recurrence) of the repos a calendar opts in to, into that calendar, one event per waypoint with UID `nemik:<repo>:W<n>` (upserted; the event of a done or undated waypoint is removed; only `nemik:` events are ever touched). A calendar is read-only unless `calendars.toml` says both `write = true` and `mirror = ["repo", ...]`; the account must also hold write rights on it (`nemik-akonadi-tasks --rights` reads them), else it refuses (exit 2) before writing anything. Plans unless `--apply`; host-side only, never served | to put your dated waypoints on the operator's calendar: the operator opts the calendar and your repo in, nothing is written implicitly |
| `nemik-history REPO... [--all] --from REV\|DATE [--to REV\|DATE] [--json]`, or `--time-in-state` / `--weekly` instead of a diff | how a repo's graph changed between two points in the git history of its committed `.claude/paths-forward.json`: minted, closed, dropped, status flips (not into done), edges added and removed (`enables` and `waits`), and the new blocks on other workstreams. A date means the last commit before it (a bare date is the START of that day); `--to` defaults to HEAD; `--baseline [REV|DATE]` reports planned versus actual since a baseline: the cards open then, now closed, dropped or still open (and the done share), and the cards added since, split by how they were minted (interrupt, tick, unrecorded); without a value it reads the repo's declared `.claude/baseline` (its first word; W318); a `shape:` line adds how far the graph's shape moved (edges added and removed, planned cards retitled or re-wired, and the share of planned cards touched; W349); reads history only, never writes. `--time-in-state` prints each open waypoint's time in each status over the committed history (a commit's state holds until the next one); `--weekly` prints one row per ISO week: opened, closed, open, blocked share, the longest-running block, the median lead time (first commit to closed) of the cards closed that week, `utilization` (opened over closed: above 1 the queue is growing), `implied_wait_days` (Little's law: open cards over the weekly close rate) and `flow_efficiency` (working time over ready, working and blocked time of the cards closed that week; low until cards are actually marked `working`), and the operator's own queue: asks opened and answered that week (a card entering or leaving `blocked_kind` human), asks open at the week's end, and `operator_wait_days` (Little's law on the operator alone; W357); `--toil` prints, per week, the ledger activity by effort class and the interrupt share (interrupt over forecast plus interrupt: the tax unplanned work levies on planned work; W314). The class comes from the ledger line's kind: `tick` and `arm` are forecast; `op`, `peer`, `msg`, `manual`, `main` and `swarm` are interrupt; anything else is unclassified. So log operator-directed work with `--kind op` and a peer's request with `--kind peer` (`mikemol-paths-forward --ledger W<n> advanced <mechanism> "<note>" --kind peer`), or the toil ratio reads low | to answer "what moved since last Monday", "how long has this sat blocked" or "are we opening faster than we close" for a repo or the fleet (W267-W269; an age metric follows as W270) |
| `nemik-overlaps` | fleet-wide `touches` overlap; `--cross` only tags shared across repos. Each OVERLAP row ends `[<repo> held by <pid:start> (<age>)]` when a session holds mtools' work claim `claim:label:touch:<repo>:<tag>` for that tag (read from `mikemol-membudget claims`; `$NEMIK_MEMBUDGET` names the binary); advisory display only, and with no membudget it says so once and prints no holder (W305, mtools:W913) | before starting work that edits shared machinery |
| `nemik-floor-asks` | summit floor asks that point at waypoints which no longer exist | when filing to summit |
| `nemik-witnesses` | waypoints with a declared Rego witness, evaluated; `--apply` marks those that hold as done. `--wait '<PromQL expression or Rego query>' [--timeout 12h] [--every 30s]` blocks on one ad-hoc witness, background it and get one notification: exit 0 it held (prints the value and when), 1 timed out (prints the last value), 2 it cannot be evaluated (probe down, endpoint unset, bad query: unknown is not "not yet"); a bare PromQL expression holds while its result is non-empty, so write the comparison (`x > 0.99`) | outage/"wait until X is true" waypoints; instead of hand-polling /proc, `ls` or a commit log |
| `nemik-ics` | the operator's needs-you asks, from repos opted in via `~/.config/nemik/ics.toml` (`repos = [...]`), as an iCalendar file of VTODOs (UID `nemik:<repo>:W<n>`), each with an RFC 5545 `PRIORITY` (1 highest) from the flow salience the ask holds back (steps in `[ask_priority]` of rank-weights.toml, W299); host-side only, never in the export | to put your repo's operator asks on the operator's calendar/phone: opt in, and state the ask as `operator: decide|act ...` |
| `nemik-tasks --list NAME [--apply]` | the same needs-you VTODOs synced into the operator's Google Tasks list through Akonadi (host helper built by `./setup.sh`); plans unless `--apply`; groups by repo by default (a parent task per repo, each ask a subtask; `--flat` opts out) and, with `--apply`, reruns while a child's parent is not on Google yet; prints `DONE-CLAIM <repo>:W<n>` when the operator ticked a task whose ask is still open; exit 0/1/2 | luthen's timer will run it (luthen W234 declares the unit; none exists yet, so today it runs by hand); a DONE-CLAIM about your waypoint is a claim to verify from your own readings, never a reason to mark it done unread |
| `nemik-metrics` | the same state as Prometheus text, including `nemik_realizability_waypoints{repo,coordinate}` (live waypoints per realizability coordinate) and `nemik_realizability_unjudged{repo}` (1 when a queue could not be judged: absent counts mean not checked, never clean), and `nemik_waypoint_age_seconds{repo,state,quantile}` (the median, quantile 0.5, and the oldest, quantile 1, age of the open waypoints per state, from `issued_at`; W270), and `nemik_operator_salience{repo}` with `nemik_operator_asks{repo}` (the flow salience the repo's needs-you operator asks hold back, summed, and how many asks that is; W300), and `nemik_repo_health{repo}` (0 green, 1 amber, 2 red: the worst of blocked share, loop ticks the longest-blocked card has waited, and needs-you asks owed, each against the `[amber, red]` pair `[health]` declares in `rank-weights.toml`, calibrated to the measured fleet; the view's repo chips carry the same verdict as a colour, a glyph and the reasons on hover; W317) | luthen scrapes it; rarely by hand |
| `nemik-serve` | read-only web view of the merged graph; `--static OUT --withheld FILE` writes it as static files behind luthen's withheld list (missing list: exit 2, nothing written) | the operator's dashboard; luthen hosts it and builds the public copy |
| `nemik-static` | serves a published snapshot (the `--static` output, or `ROOT/current` flipped atomically) as files: no model, no rdflib, validators from `hashes.json` (304), `/healthz` and a `/metrics` the build wrote (W502; measured 80k requests, 29.7 to 33.1 MB RSS) | the pod's server once it stops building graphs (W500); any host that should only serve |

## What `nemik-check` warns about, and the fix

| shape | means | fix |
|---|---|---|
| `WaypointShape` | status or blocked_kind outside the vocabulary; **`enables` naming nothing in any workstream (VIOLATES)** | ready/working/blocked/done and agent/human; fix the reference (rule 1) |
| `BundledTitleShape` | an open waypoint's title is over 150 chars with several clauses (bundled steps); done waypoints are exempt | split the title into waypoints joined by enables |
| `CausedByResolvesShape` | `caused_by` cites a `<repo>:W<n>` or `W<n>` that is nothing in any workstream; the message names it | fix the repo prefix or symbol |
| `EdgeIntoDroppedShape` | an edge points at a dropped (residue) waypoint | retarget or clear the edge |
| `CheckableNextStepShape` | a ready or working card's next step names a repo file (so it is checkable) and the card declares no witness | add `--witness` (and `--witness-lang`), so a query, not prose, says the step is done |
| `LifecycleWordShape` | a ready or working card's next step says armed, shipped, host-shipped, live, takes effect, rides the next apply or deployed, which blur the change-lifecycle steps | say landed, installed, held, enabled, active or applied (`nemik:ChangeLifecycle`) |
| `EditDeclaredShape` | a ready or working card's next step names a repo file and the card declares no `file:<path>!w` touches | declare what it edits, so `--overlaps` can flag a real edit collision |
| `UnwarrantedRulingShape` | an open card's title, evidence or next step claims an operator ruling (a phrase from `[rulings]` in rank-weights.toml) and the card has no `warrants` | attach the transcript record: `mikemol-paths-forward --warrant SYMBOL --transcript PATH --uuid UUID` (W597) |
| `MalformedWarrantShape` | an entry of the card's `warrants` list is not valid JSON-LD, so no record joins the graph | rewrite it with `mikemol-paths-forward --warrant SYMBOL --transcript PATH --uuid UUID` (W598) |
| `WarrantRecordShape` | a transcript record a card is `prov:wasDerivedFrom` (a warrant, W3C PROV-O as JSON-LD on the card) lacks `prov:generatedAtTime` (xsd:dateTime), `prov:wasAttributedTo` a `prov:Agent`, or `prov:wasGeneratedBy` a `prov:Activity` | complete the record: the operator is `urn:nemik:operator`, the utterance a `prov:Activity`, the record's IRI `file:///path#uuid` (W599; mtools:W1384 writes to it) |
| `BlockedShape` | `blocked` without blocked_on or blocked_kind | give both |
| `ListFieldShape` | enables/touches/blocked_on stored as one string | store a list |
| `UnclaimedBlockShape` | blocked on a workstream and nothing there claims it | cite `<repo>:W<n>`, or ask them to mint a claiming waypoint (rule 2) |
| `OperatorAskShape` | operator block with no stated ask, or one already answered | rule 4 |
| `UmbrellaBlockShape` | blocked on another repo's umbrella (2+ open children enable it), not the child step doing the work; a single-child chain step is fine to cite | cite the child `<repo>:W<n>` |
| `ReadyUmbrellaShape` | ready or working, yet 2+ of your own open cards enable it: an umbrella that cannot land before its children (W436) | `--update W<n> --status blocked --blocked-on <the children>`, or drop the `enables` edges that are not prerequisites |
| `UmbrellaCompleteShape` | an open umbrella whose local children are all done, with no next step, no working state and no foreign blocker: it is realized by construction (W488; Info) | `$PF --close-umbrellas --write` closes exactly this set |
| `OrphanLeafShape` | an open card with no edge at all: nothing enables it, it enables nothing, it waits on nothing and nothing waits on it (W487; Info while the fleet count is read) | give it an edge (`--enables <the card or goal that needs it>`, or `--add-enables`), or `--drop` it with a reason |
| `ManifestShape` | a ready leaf (no open card enables it) with no manifest of planned changes: the stackable pick cannot tell it is disjoint from anything (W612; Info while the fleet count is read) | `$PF --update W<n> --manifest <exact repo-relative file>... --size small\|medium\|large`; atomize until each leaf has one |
| `OversizeShape` | a ready or working card declared `large`: not a leaf yet (W612; Info) | atomize it into small or medium cards joined by `enables` edges |
| `RetroPrecommitShape` | a `nemik:Retro` node with no (or an empty) `nemik:precommit`: narrative only, nothing records what the card predicted (W648, gate G0; Info) | copy the card's mint-time next step and witness into the retro's precommit |
| `RetroRootShape` | a retro that names no trigger or no root, or whose root equals its trigger (W648, gate G3; Violation) | name the symptom that started the review as the trigger and why it could happen as the root |
| `ReadyBehindOpenShape` | ready, yet one open card (any repo) enables it: it cannot land first, and its salience reads blank (W465; raised from Info to Warning at 8 fleet-wide, W493) | `--update W<n> --status blocked --blocked-on <that card>`, or drop the `enables` edge if it is not a prerequisite; mtools:W1131's `--block-behind-open` will do it for you |
| `UnresolvedBlockerShape` | blocked_on names no repo, waypoint, operator ask or calendar event (`cal:<label>/<uid>`) nemik can resolve | rewrite it as one of those |
| `LandedBlockerShape` | a blocker is already done or dropped; if all are, the item is ready | trim it (`$PF --prune-landed --root <fleet root>` prunes local and foreign ones) |
| `MalformedBlockerShape` | a symbol with prose attached (`W8 (both ...)`) | symbol alone; prose goes in evidence |
| `ActiveCardShape` | no `working` card while items are ready (operator 2026-10-01: one active card per repo unless everything open is blocked) | mark the item you are doing `$PF --update <W> --status working` |
| operator saturation (`N needs-you operator asks are open (cap C, oldest issued D)`, W348) | the repo holds more needs-you asks than `[saturation] needs_you_per_repo` in rank-weights.toml (10): the operator is its bottleneck, and asks queue behind one another | batch related asks into one, withdraw those another path now answers, or cite a shared ask (`same ask as <repo>:W<n>`) so the operator answers once |
| umbrella re-point (Info: `waits on <repo>:W<n>, whose open step(s) are ...`, W405) | your card waits on another repo's umbrella (a card two or more open children enable, so its work IS its children, often after the other repo atomized it); the descent passes through umbrellas and stops at the first real step | run the printed `mikemol-paths-forward --update W<n> --blocked-on <step>` (one step), or cite the one of the listed steps that actually unblocks you; Info never changes the verdict |
| cross-repo SLA (`has kept <repo>:W<n> waiting N loop ticks (SLA S)`, on the blocker's card, W356) | another repo's card has been blocked on this open card for more than `[sla] cross_repo_ticks` in rank-weights.toml (48, a day at the 30-minute cadence); a blocker that itself waits on the operator is not warned (operator saturation counts that load) | answer the waiting card, re-scope this one so it can, or tell the waiting repo why it waits (a letter or peer message citing both cards) |
| dependency cycle (a check finding from `nemik.critical`, W331) | cards that wait on each other in a loop, none of them blocked on the operator: none can become ready; usually an umbrella that lists its children under `enables` while being `blocked_on` them. A cycle with an operator-blocked member is left to the operator (the same-ask pair) | clear the `enables` (or the `blocked_on`) that closes the loop; `nemik-critical` lists every cycle |
| `AdoptionShape` | the repo runs someone else's `mikemol-paths-forward` | `uv add` a sha-pinned copy (mtools INSTALL.md) |

The unresolved `enables` (for example a wrong repo prefix) is a `VIOLATES`: it pages the operator
through luthen. Everything else above is a Warning.

## Waiting on an outage (weather)

When your work is blocked by something being *down* (a registry, an API, a host, a CI runner), not
by another session's work, that is **weather**, and it gets one waypoint of its own (nemik:W173):

- **The blocked repo mints it**, not the owner of the broken thing: you are the one who needs to
  know when it is back. One outage is one waypoint, `--add "weather: <what is down>"`, and your real
  work blocks on it by citation (`blocked_on: ["<this-repo>:W<n>"]`, blocked_kind `agent`).
- **It carries a witness**, a one-line Rego query over a probe fact (`$PF --update W<n> --witness
  '<query>'`), e.g. `input.alert["RegistryDown"].state == "inactive"` or
  `input.promql["up{job=\"forgejo\"}"].values[0] == 1`. Facts come only from nemik's fixed observers
  (`input.pid`, `file`, `git_ref`, `alert`, `promql`, `apply`, `now`); see `nemik-witnesses`.
  `input.apply["<row id>"].applied` reads luthen's host-apply export (`<root>/host-apply.json`,
  nemik:W233): true only for a fresh, well-formed export whose row is applied (its live file equals
  its declared source); a row the export does not hold, or a stale one, is never done, and a row
  luthen's unprivileged exporter could not read (`unobservable`, a root-only path) is undefined:
  unknown, not pending (nemik:W259). Cite a row in a
  waypoint as `host:<id>` (`blocked_on: ["host:home-mount"]`, a condition like `cal:`); `nemik-check`
  warns when the export is readable and does not hold that row (nemik:W256).
- **It is monotone**: once the witness holds, `nemik-witnesses --apply` marks it done with the facts
  as evidence and wakes whoever waits on it. It is never reopened. If the thing breaks again, that
  is a new outage and a new waypoint.
- A witnessed waypoint is never worked by a tick (mtools skips it); nobody "fixes" weather from
  inside the waiting repo. If the outage needs a fix, that fix is the owner's waypoint, and your
  weather item may cite it in evidence.

## Talking to other workstreams

- **Letters** go in the other repo's `inbox/` as `YYYY-MM-DD-<from>-<topic>.md`, first line
  `<from> → <to>: <what this is>`. Cite waypoints as `<repo>:W<n>` on both sides.
- **Live sessions**: `ListAgents`, then `SendMessage` to the session name (`<repo>-<hex>`). Before
  concluding a repo has no live session (and holding an ask for later), run `ListAgents`: it is a
  reading, not a recollection, and sessions start all the time. A repo with no `inbox/` can still
  be messaged live. The first
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
