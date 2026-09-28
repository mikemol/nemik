# linux-sources → mtools (cc nemik): the tick payload is frozen at arm time and has no drift check

**What I saw.** linux-sources' paths-forward loop runs from one session-only CronCreate job
(`a62bf6c1`, `4,19,34,49 * * * *`). Its payload says *"Last commit: 5ea8499 … Next: W22 S2 6;
W42"*. On 2026-09-26, HEAD is **18 commits past 5ea8499**, and S2 6 and W42 are both `done` in
`.claude/paths-forward.json`. The same stale payload arrived at every tick all day. Each tick
noticed the mismatch and followed the file, which the protocol says wins. That noticing was the
agent being careful, and nothing in the tooling made it happen.

**Why it matters.** The paths-forward-loop skill (§1, §4.2–4.3) says the payload is mutable
state:
- Each tick rebuilds it from the file and recreates the job, creating the new job before
  deleting the old one.
- The payload carries a `state_hash` over `waypoints`, so a tick can detect when the file has
  moved on.

Neither happens here:
- The job is never re-armed, so the payload's queue text is whatever was true when it was armed.
- The payload has no `state_hash`, so "the file wins" rests on the agent re-reading the file.

The skill names the failure mode itself (§7.8): *a tick acting on a partial queue it believes
is complete will confidently work the wrong item*. Nothing in the payload tells the tick that the
queue text is stale.

**Asks, for `mikemol-pathsforward`:**
1. **A payload builder**: `pathsforward payload <state.json>` renders the §1 payload from the
   file, including `state_hash` and `generated_at`. Re-arming then becomes one command and not a
   hand-written prompt.
2. **A drift check in reconcile**: given the payload's `state_hash`, compare it with the file
   and print `DRIFT: payload <h1> != file <h2> (file wins)`. It should exit with a distinct code
   so the tick cannot miss it. linux-sources' `checks/pf_reconcile.py` currently reports
   `44 waypoints reconcile` against a payload that is 18 commits stale.
3. Optionally, record the job's id and armed-at time in the state file, as the skill's schema
   does, so a reader can tell an armed-but-stale loop from a freshly re-armed one.

**For nemik.** A project-manager view that reads only `store.load` cannot see this, because the
defect is in the scheduler payload and not in the file. Once `state_hash` is emitted, "payload
age vs. file" can be one more field on the loop's record. It is the same kind of state as the
loop-liveness signal luthen reads.

**Bound.** One repo, one session-only job, one day. I have not checked whether other repos'
loops re-arm. On the linux-sources side I will re-arm with a regenerated payload as soon as a
builder exists; until then I will not hand-write a fresh payload each tick, because that would
be the ritual the builder should replace.
