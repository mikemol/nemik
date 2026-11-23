# Gate slots are the capacity side of the cost model (nemik:W2436, v2)

The operator, typed in the host session and relayed by github-00 (2026-11-22): "gate slots sound like a
resource management problem that ought to be able to figure into fence, membudget and nemik scheduling
automatically", and then: "I thought that's what the vector and cost models were for?" They are. A gate
slot is not a new mechanism: it is the **capacity side of the cost model already being built**. In
nemik:W2360 a card's own cost is gate CPU-seconds per landing, which is also slot occupancy (with one
slot, a card's gate run holds it for its duration). In nemik:W2325 v11 the cost is the con rail and the
order is demand per unit cost. "Queued for the slot" is therefore the ranking over cost against a
capacity, not a separate scheduler. v2 starts from that, from the submit queue that already exists as the
observed holder, and adds only what is missing: the declared capacity as the con rail's limit. A design,
for review; nothing is built.

v1 (refs/review/W2436-v1) proposed a `gate` ledger in membudget. github-00's review, raised by the
operator ("don't mtools and g-calculus already have katas around submit queues?"), asked for the survey
first. It is below; it removes the ledger.

## Units: throughput, not wall clock

The operator's ruling (host line 213965, uuid 91d9f552-6cf0-4692-b069-e9f36e00bbe6, 2026-11-22T23:07:46Z):
"series over samples, not just series over time; sessions won't always be awake to process cards, so
predictions based on wall clock won't work. Predictions based on throughput will mesh better with when
the worker is working." Here: slot occupancy is in ACTIVE seconds of the holder (its process tree's
CPU-seconds, never elapsed minutes), and a card's wait for the slot is counted in landings ahead of it in
the queue, not in minutes. A wall-clock estimate, where one is wanted, is a separate step that multiplies
by an observed wake rate, itself a series.

## What exists (read through git objects, not run)

- **`mikemol-commit` queues stacks, per repository.** mtools `hooks/src/mikemol/hooks/commit_kata.py`
  (`claim_of`, line 807): a submitted stack waits on fence's zero-capacity claim
  `hold 0 claim:path:<git dir>/mtools/commit`, keyed on the repository being committed (it was keyed on
  the launcher's checkout once, so a paperkit gate held every mtools commit; fixed, W886/W910). The wait
  has no deadline and ends when the holder does; the fence reaps a holder that died (W1463). Stacks queued
  behind a running gate join its run and gate once at the joined tip (W1654). So the slot is real, it is
  **per repo**, and the queue already holds it.
- **The queue is observable.** `mikemol-commit REPO --in-gate [--json]` lists who is in flight and who is
  queued: key, state, waypoints, began_ns; the queue depth is the length of the list. A queued submission
  leaves with `--withdraw KEY`. Refusals read "refused at submit, before it waits".
- **Across repos only memory is shared.** The gate beneath the claim leases from the HOST memory ledger
  with the host's ceilings (the claim's own ledger has the load and zram gates off). So one repo's
  gate does not wait on another's, except through memory.
- **gcalculus:** at its committed HEAD it carries no submit-queue tool of its own; the only hits are
  mentions of the mtools kata (`katas.py precommit`). **summit's capability index MISSED under the
  spelling "submit queue"** (github-00 ran `summit capability "submit queue"` from the host); the other
  spellings ("commit queue", "in-gate", "claim", "katas", "pending") are still to try, or the spelling
  is to be filed with summit.
- **What is NOT in the queue:** `tools/presubmit.sh`, nemik's own pre-check, runs a full gate on the
  repo's bazel server without taking the claim. That is how a presubmit and a stack gated at once on one
  checkout, and the likeliest reading of the W2403 stall (not shown: the failing output had no bazel line).

## The design, on that structure

1. **Capacity is declared as the con rail's limit, in nemik.** One number per repo and host: concurrent
   whole-gate runs (1 today, the claim's own capacity). It sits with the rank's declared choices
   (rank-weights.toml), next to the cost unit, so the order "demand per unit cost" reads against it. No
   new ledger: the claim IS the capacity for a repo, and the host memory ledger is the shared limit.
2. **The holder is observed from the queue that already exists.** A `nemik-witnesses` observer over
   `mikemol-commit REPO --in-gate --json` gives `input.commit_queue[<repo>]` with the in-flight key, its
   waypoints, `began_ns` and the queued entries. A holder is a card (its waypoints), not a pid. An
   unanswered or unreadable queue is UNKNOWN, never "no holder". **The shape is settled from the
   source** (`commit_counts.live_json`): a JSON array of `{key, state, waypoints, began_ns}`, in the
   order given; `key` is the submission time in nanoseconds (so a smaller key is an earlier
   submission), `began_ns` is when the GATE began and is null for a queued entry; a dead entry is not
   listed; the read queues nothing and takes no lease. **Run read-only on 2026-11-22** the pinned bin
   printed `[]` for `nemik` and for `luthen-observability`: no stack was in flight or queued then (the
   presubmit that was running is not a stack, which is point 4's gap).
   **Scope mismatch, said plainly:** the claim queue is PER REPO but the capacity that matters is the
   HOST's (CPU and memory). So the observed holders are the UNION of every repo's `--in-gate`, and the
   declared capacity is per host; a column that read only this repo's queue would show a free slot
   while another repo's gate fills the machine.
3. **The round reads it, derived and never stored.** For a ready or working card whose stack is queued or
   in flight, the round shows `queued for slot (behind W<n>)` or `in the gate`; a card whose next step
   needs the gate and finds the slot taken is shown as queued, never as blocked, and gets no `blocked_on`
   edge. Sessions stop encoding the slot as a blocker, because the round already says it. The cost model
   then orders what is NOT yet queued by demand per unit of slot-seconds (W2360's derived cost).
4. **The presubmit joins the queue (nemik's own).** `tools/presubmit.sh` takes the same
   `claim:path:<git dir>/mtools/commit` (or is a mode of the queue) so a presubmit and a stack serialize
   by the mechanism that serializes stacks. This is nemik's tool, not mtools'.
5. **W2403 (the stall detector)** stays mtools': a wait on a claim whose holder is alive and spending CPU
   is not a stall of the waiter. The queue is where that fix belongs; the letter to mtools says so and no
   longer asks for a `gate` ledger.

## Owners

| Part | Owner | Carried by |
|---|---|---|
| the declared slots per repo and host, as the con rail's limit | nemik | W2325 v11's declared choices, with W2360's cost |
| the `input.commit_queue` observer over `--in-gate --json` | nemik | a card after review |
| the derived `queued for slot` column in the round | nemik | a card after review |
| presubmit taking the claim | nemik | a card after review (tools/presubmit.sh) |
| the stall detector reading a live holder's CPU as the waiter's progress | mtools (parked) | the letter, nemik:W2403 |

## What this does not claim

- That a NON-EMPTY `--in-gate --json` matches the source's shape on the live bin: the two live runs
  returned `[]`, so an entry's fields are read from `live_json`, not seen; the observer's test plants one.
- That presubmit taking the claim is free of deadlock with a stack's own nested calls (`HELD_ENV` guards a
  nested claim in `claim_of`; whether a presubmit launched from a stack hook is nested is unread).
- The slot count, and any cross-repo slot: the queue is per repo; a host-wide gate limit would be the
  memory ledger's, which already exists and is mtools'.
- summit's index: not queried.
