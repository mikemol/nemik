# W58: blockers a machine can wait on

Operator ask, 2026-09-27: "a way to declare blockers/waiters/waypoints on, e.g. a given host PID or
vmalert condition or k8s job; something that can be mechanically waited on to automatically
wake/unblock, rather than force a polling action by a token-consuming agent."

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
