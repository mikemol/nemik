# W58: blockers a machine can wait on

Operator ask, 2026-09-27: "a way to declare blockers/waiters/waypoints on, e.g. a given host PID or
vmalert condition or k8s job; something that can be mechanically waited on to automatically
wake/unblock, rather than force a polling action by a token-consuming agent."

## Revision 3 (operator): "I'd suggest not executing arbitrary code, but instead declare a rego rule or some such."

Revision 2 made the witness a command, so any string in any repo's queue would become code that
`nemik-witnesses --apply` runs on a timer. That makes the queue file an execution surface, and
nothing the witness does can be audited from the queue.

Revisions 1 and 2 were each half right:
- rev 1 had a **closed, typed set of observers** (pid, k8s job, alert, promql, git, file, time),
  but encoded the test inside a URI;
- rev 2 had the **waypoint shape** (blockers stay `<repo>:W<n>`, W125 prunes, wake follows).

Combined: **observation is fixed, trusted code nemik owns, and the predicate is declared data.**

- **Observers (nemik, closed set).** Each FFI waypoint names what to look at in the `observe`
  part of its witness. `nemik-witnesses` gathers exactly those facts into an input document,
  e.g. `{"pid": {"localhost/41233": {"alive": false, "start": "..."}}, "k8s_job": {...},
  "alert": {...}, "git_ref": {...}, "file": {...}, "now": "..."}`. An observer can only read,
  and it touches only the hosts and endpoints that nemik configuration allows (luthen by name,
  per endpoints_query).
- **Witness = a Rego rule (declared).** `witness` holds a Rego query over `input`, e.g.
  `not input.pid["localhost/41233@<start>"].alive` or
  `input.k8s_job["ns/trace"].succeeded > 0`. `opa eval` (installed at /usr/bin/opa) decides it.
  Rego is side-effect free, so the queue carries a predicate rather than a program.
- **Which facts to gather** comes from the query's own references (`input.pid[...]` keys), or
  from an explicit `observe` list if parsing proves brittle. That is an open question below.
- Outcomes are true (done), false (not yet) and undefined (a fact is missing, i.e. can't
  observe). Undefined is the repeated-exit-2 finding from rev 2, now structural.
- Everything after is unchanged from rev 2: mark done with the fact snapshot as evidence, W125
  prunes, wake follows.

Open: is the observe set derived from the query or declared beside it? Derived keeps one field
and is the leading option. Should mtools validate Rego syntax (`opa parse`)? That needs opa at
check time, so probably not: nemik-check can do it.

## Residue: revision 2 (witness = executable command; rejected: queue becomes an execution surface)

### (rev 2 heading) (operator, same day): "This might look like an FFI waypoint. Something like a paperkit witness"

The URI-scheme design below is kept as residue. Its flaw is that it adds a third *kind of
blocker*. Blockers already have a single uniform shape, `<repo>:W<n>`, and every tool reads it:
nemik-inbound, `--bump-blocked` pruning (mtools:W125), enables/waitsFor, and wake. So the
mechanical thing should be a **waypoint**, not a blocker kind.

**An FFI waypoint** is an ordinary waypoint with a `witness` field, a command stored as data.
It is done when the witness exits 0, the same contract as paperkit's `witness = "checks/arch.py"`.
It is the boundary where the queue calls out to the world instead of to a mind:

    W70  "trace W109 finishes"   witness = "nemik-witness pid-gone localhost 41233@<starttime>"
    W69  blocked_on = [W70]      (plain local block; W125 prunes it the moment W70 is done)

- **mtools** (one writer): a `witness` string on waypoints, set with `--add/--update --witness CMD`.
  `--check` flags a witnessed waypoint that is `working` (no mind works it). Nothing else changes:
  `blocked_kind` stays agent|human.
- **nemik-witness** (nemik): the standard witness library, one subcommand per observer: `pid-gone`,
  `k8s-job-done`, `alert-state`, `promql-nonempty`, `git-ref`, `file-exists`, `after-time`.
  Each exits 0/1/2 (holds, doesn't hold yet, can't observe). Output is one line of evidence.
  Any executable also works, so it is an FFI rather than a closed enum.
- **nemik-witnesses --apply**: runs every open witnessed waypoint across the fleet with no LLM,
  and marks passes done with the witness's line as evidence. After that it is ordinary
  machinery: W125 prunes blockers, the parent turns ready, and `live iff workable` / nemik-wake
  wake whoever now has work. It runs from a timer or a luthen CronJob.
- A witness that keeps exiting 2 (can't observe) is itself a finding, surfaced like an unstated ask.

The scheme table below survives as the witness subcommand list.

## Residue: revision 1 (blocked_kind=condition with URI schemes)

## The shared structure

`agent` and `human` blockers need a mind to decide they are resolved. Some blockers do not: an
exit, a job status, an alert state, a pushed ref. Each of these has an observer that costs no
tokens. What they share is a **predicate on observable state**. It needs an address (what to
look at) and a test (what "resolved" means), both written as data. Then a cheap evaluator can
decide it, and an agent only wakes when it returns true.

So `blocked_kind` gains a third value, `condition`, and `blocked_on` holds a condition URI:

| scheme | resolved when | observer |
|---|---|---|
| `pid:<host>/<pid>[@<starttime>]` | the process is gone | `/proc` (local host) or ssh; starttime guards against PID reuse |
| `k8s:job/<ns>/<name>` | `.status.succeeded>0` or `failed` | `kubectl wait` / watch |
| `alert:<vmalert-rule>[{labels}]=<firing\|inactive>` | the alert reaches that state | vmalert `/api/v1/alerts` (luthen) |
| `promql:<expr>` | the expression returns non-empty | victoriametrics query |
| `git:<repo>@<ref>` / `git:<repo>:<path>` | the ref or path exists | `git ls-remote` / local clone |
| `file:<path>` | the path exists | stat |
| `time:<iso8601>` | now ≥ t | clock |

A failed job also resolves the block. The waypoint wakes up to handle the failure, not to find
out whether it happened. So the evaluator records *which* outcome occurred in evidence.

## The pieces

1. **Schema (mtools, one writer).** `--blocked-kind condition` accepts only a parseable condition
   URI in `--blocked-on`. `--check` flags an unknown scheme.
2. **Evaluator (nemik).** `nemik-conditions` evaluates each open `condition` block across the
   fleet with one probe per scheme. It prints resolved ones, and with `--apply` it unblocks
   them through `$PF --update`, stamping the outcome into evidence. It uses no LLM, so a
   systemd timer or luthen CronJob can run it every minute for free.
3. **Wake.** A resolved condition that unblocks a waypoint in a dormant repo lands in
   `nemik-wake` as "must be woken, for W<n>". An armed session gets an inbox line or a
   cross-session message. The loop's `live iff workable` rule then does the rest: suspended
   loops re-arm only when something *became* workable.
4. **In-session shortcut.** While a session is alive and waiting on its own process (the W109
   trace in the screenshot), Claude Code's `Monitor` with an until-loop already waits at zero
   token cost. The skill should say so: a lock held across a background process should wait via
   Monitor, not ticks.

## Residue / open questions

- Remote PIDs need host reachability. Should `pid:` be restricted to the evaluator's own host at first?
- Should alert/promql probes go through luthen's endpoints_query rather than hard-coded URLs? (see
  memory luthen-stores-resolve-by-name). Probably yes.
