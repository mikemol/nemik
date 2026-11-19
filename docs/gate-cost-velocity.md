# A velocity card's weight from the measured gate cost of the paths it accelerates

nemik:W2323. **Design only: no code, no query run by nemik, no change to any ranking.** A velocity
card is one that makes work flow faster (a faster gate, a smaller staged input). Today it is lifted by
a tag (`velocity`) the owner sets. The operator's ruling (host transcript 695f3e0a, 100702, 2026-10-26)
is that velocity improvements come before the things they carry, and the rank design
(docs/rank-from-the-vector.md, nemik:W2325, still at refs/review/W2325-v10 and not on main) asks for
the gain a card gives as a MEASURED number rather than a tag. This note is where that number comes from, what already exists to measure it, and
what does not.

Each fact is marked **read** (read by me in this repo's files) or **relayed** (luthen-observability's
answer to my question of 2026-11-19, which read it from its store and its repo's files at
2026-11-19T06:35Z; I did not query the store myself, because nothing in this session can reach it).

## What exists (relayed)

The commit gate (mtools) records its cost as OTLP series, stored with dotted names:

| series | labels | what it is |
|---|---|---|
| `mikemol.gate.target.cpu.seconds` | `target` (the bazel label, the shard in the name), `kind` (mutants or pytest), `repo` | CPU seconds one UNCACHED target used, from its test.log shard line (mtools:W1783, W1769) |
| `mikemol.gate.target.wall.seconds` | the same, `kind` also `other` | wall seconds, from the build events |
| `mikemol.gate.target.children`, `.failed` | the same | per uncached target |
| `mikemol.gate.run.emitted` | `repo` | how many uncached targets the last run measured (0 when all were cached) |
| `mikemol.gate.run.seconds`, `mikemol.gate.run_seconds` | `repo` | two spellings of what looks like one measure |
| `mikemol.gate.admission_wait_seconds` | `repo` | time waiting for the gate's admission |

What is NOT there, as luthen states it:
- **No user plus sys split.** `target.cpu.seconds` is a number taken from a log line; mtools owns what
  it means, so whether it is user plus sys is unknown.
- **No total.** A cached target is not re-emitted, so a target that did not run is absent from the
  store. `run.emitted` is the fresh count, and the M of the gate's printed line "N fresh of M" is not
  a series. M and the fresh set per landing live in the BuildBuddy invocation record (the bes-logs
  skill: `GetInvocation`, `testSummary` and the cached status of each target).
- **No tie between a cost and a landing or its paths.** No series carries a commit sha, a landing id
  or a path list. The only key is the timestamp (the registry says it "joins by timestamp, never by
  presence"). **mtools:W2684 is the card that replaces this**: I read it in mtools' queue, and it is
  open and blocked on mtools:W2573. Its title says the gate's per-target CPU series carries no commit
  label, and its next step says the gate's sender of `mikemol.gate.target.cpu.seconds` adds one
  (raised when the shard guard could not name which commit a reading came from). With that label a
  cost ties to a landing by label, and to the landing's paths through the commit's own diff, not by
  time. Until it lands, everything below that needs a landing's cost rests on the timestamp join.
- **Coverage.** In the last seven days per-target CPU series exist for repo `mtools` (mutants and
  pytest) and repo `nemik` (pytest, 536 series). luthen-observability's own gate emits none, a
  gate-parity gap now carded as luthen-observability:W2749 (read: ready, minted 2026-11-19, caused by
  nemik:W2323, its next step decides between enabling the emit there and asking mtools). So a
  velocity card for nemik's paths has measured cost today; one for luthen's does not.
- **Retention** is one month (`-retentionPeriod=1`, and VictoriaMetrics reads a bare number as
  months), and collection began 2026-10-20.
- **Producer defects** luthen names: a literal `repo="repo"` in two families, and `repo="tree"` for
  the first gate until mtools:W1793.

The store is reached by NAME (`vmsingle-http`, resolved by luthen's `checks.vm_loaded.node_port`),
never by a port copied from a skill's text. The telemetry skill states two literal ports (30828 and
30829) that are another host's own measurements (cassian's), written as universal: not outdated, but
one host's constant stated for all. That is luthen-observability:W2689 (read: ready), whose draft
diff luthen names as luthen-observability:W2403 (not read by me). The skill is the operator's fleet
skill, so a change goes through the host session's change review and the operator's sign-off, not
through a nemik or luthen session. luthen publishes recording rules over the cpu series
(`gate:luthen_gate_target_cpu_samples:count7d`, `...median7d`, `...p90_7d`).

## What the card needs, and the one step that is new

A velocity card names what it speeds up: the bazel targets (or paths, which `bazel rdeps` turns into
targets) whose cost it cuts. Its demand is then the cost those targets are measured to incur, so an
expensive recurring gate pulls its own fix up. Three quantities, in the order the rank design wants
them:

1. **cost of a target** `c(T)`: the CPU seconds of its uncached runs, summed over a window. A cached
   target costs nothing and is absent, which is correct: it is not slow. This is read straight from
   `target.cpu.seconds` for repo `nemik`, no join needed. Counters and CPU time, never wall time as
   evidence (the telemetry skill's rule: wall is a property of one run on a contended host).
2. **cost of a card** `C(card) = sum over T the card declares of c(T)` over the same window: the CPU
   the gate has been spending on what the card would speed up. This is the number the rank design
   consumes as the flow the card amplifies, and its unit is CPU seconds per window, not a score.
3. **a landing's cost**, only if a replay needs it. With the commit label of mtools:W2684 it is the
   sum of the cpu samples carrying that commit, a join by label and not an assumption. Until then it
   is the sum of the cpu samples whose timestamps fall in that landing's gate window (the commit's
   time on main back to its `run.seconds`): a TIMESTAMP join, the only key there is. It is wrong
   whenever two gate runs overlap, and the gate takes a lock per repo (the `membudget` claim on
   `.git/mtools/commit` printed by `mikemol-commit`), so within nemik it should not, but I have not
   shown that, so it is stated as an assumption and the replay must check it by counting samples
   outside every window.

What the card does NOT decide, because the rank design has not: whether a card's value is the
amplified cost or the part it removes (output or increment, the operator's open question in
nemik:W2325), and how a declared estimate before the card lands becomes a measurement after. This
note gives the measured input; the formula that consumes it stays in the rank design.

## How a velocity card declares what it speeds up

A typed field, not an `enables` edge (nemik:W2328): `enables` and `blocked_on` are one dependency
edge in `nemik.flow`, so a velocity card that `enables` the cards it speeds up would make them wait on
it. The field names bazel labels. A label that no longer exists (a renamed target, a sharded name
whose shard count changed) must be a refusal at write time, not a silent zero cost.

## The replay, before anything ships

Over the month the store retains: for each landing in the window, the cost its gate spent (item 3),
and for each velocity card that exists, `C(card)`. A card the rank design names as one that must rise
(W2727, relayed there; I have not read it and do not know which repo holds it) must rise in the order
with the measured cost and must not rise with it removed. Retention is one month, so a replay longer than that needs the
figures exported, not re-read; that is a request to luthen, not something to assume.

## Open, and whose

- mtools: the commit label on `mikemol.gate.*` (mtools:W2684, open, blocked on mtools:W2573); state
  what `run`, `admission` and `failed` measure, whether `target.cpu.seconds` is user plus sys, and
  which of `run.seconds` and `run_seconds` is the family (luthen's registry says these wait on
  mtools).
- luthen-observability: its own gate emits no per-target series (luthen-observability:W2749); the
  telemetry skill's literal ports (luthen-observability:W2689, draft diff W2403).
- nemik: whether the BuildBuddy record or the store is the source of M and the fresh set per landing
  (the store cannot give M), and the typed field for declaring the targets (nemik:W2328).
- Not measured by me: any of the figures above. Nothing here has been queried from nemik.

## Steps, smallest first

0. mtools:W2684 (the commit label), which this note depends on for item 3 and nothing else; items 1
   and 2 need only the series that exist.
1. This note through the warm and cold reviews.
2. The typed field (nemik:W2328) and a read of `target.cpu.seconds` for repo `nemik` by name, as one
   small module with a recorded fixture response, no live endpoint in the test.
3. `C(card)` as a printed number for each velocity card, beside its band, changing no order.
4. The replay; only then does the number enter the ranking, through the rank design's own decision.
