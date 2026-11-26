# A repo's findings as a bazel action (nemik:W2511, design for review)

Status: DESIGN, not built. Written for github-82's review before any code.

## Why

`nemik-check --repo X --warnings` cost 328 CPU-s because the survey ran every queue to print one
repo's rows. W2511-v1 added a hand cache keyed by `cachestore.content_key(survey_inputs(...))` in
nemik's cache dir. The operator's rule is that the cache is bazel's and inputs are named: a private
cache keyed by our own hash is a second cache bazel cannot see, with its own invalidation to get
wrong. So a repo's findings become a bazel ACTION; bazel's action cache IS the cone-keyed cache.
W2511-v1 stays only as the transitional floor; its removal is carded for when the action lands.

## What the survey reads (the inputs, today)

`check.survey_inputs(root, digest)` already lists them, which is the named-input list to start from:
every repo's queue and ledger, the host-apply export, the loop prompt (root's and each repo's
acknowledged copy), each repo's `pyproject.toml`, each repo's inbox letters, the clock's bucket
(`time` enters through stale and wait-age findings), and nemik's own code and data (shapes.ttl,
rank-weights.toml, the baselines, every module the survey imports).

Two of those are not files: the CLOCK and the HOST'S state (the process table or the pace file, when
a finding reads them). A finding that reads the clock is not a function of its files. It must take
the clock as a declared, bucketed input (an epoch bucket passed as an attribute), or it cannot be a
cached action. This is the first thing the design has to settle, not a detail.

## The action

`nemik_findings(repo)`: a rule whose output is that repo's finding lines (the text
`warning_rows` writes today) and whose inputs are NAMED:

1. the repo's queue, ledger and its own inbox, and its `pyproject.toml`;
2. the queues of every peer repo in the repo's findings cone (below), each as a CAPTURE;
3. nemik's code cone (the `NEMIK_PY` and data lists in `bazel/nemik_src.bzl`) and the pinned
   Python, so a code change invalidates, as `stamp()` does today;
4. the epoch bucket, if (and only if) the settled clock rule needs one.

## Capture (hermeticity form 4, never a path into a peer's tree)

A queue lives in another repo. The action never reads `~/github/<peer>`. A capture step, run where
git runs (the gate script, not the sandbox), writes each queue AT A COMMITTED BLOB into a generated
input directory: `git show <sha>:.claude/paths-forward.json` for the published sha of each peer
(read through git objects, memory "read peers through git objects"). Each captured file is named by
its repo and blob id, so the action's input set changes exactly when a peer's committed queue does.
Open question: a session's UNCOMMITTED queue (the live working tree) is what the check reads today;
a capture at a commit does not see it. Either the action judges committed queues only (a real change
of meaning: the per-tick queue write is not committed), or the capture reads the live file by
content and names it by its sha256. The second is the truthful one and the one I propose; it is also
a read of a peer's working tree, which the operator's rule forbids, so it needs a ruling.

## The cone: what a repo's findings depend on

Not yet defined, and the point of this note. Findings come in two kinds:

- LOCAL: a function of the repo's own queue (shape results on its cards, manifest and size
  warnings, ratchet, ready-but-gating). These need only input (1).
- CROSS: a function of the merged graph (a card blocked on a peer's card, the fleet's cycle
  check, inbound claims, salience and rank over the downstream closure, operator asks). These read
  peer queues through edges.

A bazel action's inputs are fixed at analysis time, so "the peer queues this repo's edges reach"
cannot be selected dynamically from queue content. Two honest options:

A. Split the survey into a per-queue LOCAL action (inputs: that queue and the code) plus one CROSS
   action over SUMMARIES: each queue's small edge-and-state summary, itself a per-queue action. A
   change to one queue reruns its two small actions and the cross step; a peer's local-only change
   never reruns another repo's local findings. The cross step reruns when any summary changes,
   which is the fleet-wide part and stays cheap if the summary is small.
B. One action per repo with ALL queues as inputs. Correct and simple, and no better than the
   fleet-keyed cache: any queue change anywhere reruns every repo.

I propose A. It requires splitting `survey` into local and cross functions, which is the real work;
the measured 328 CPU-s says which half is expensive (SHACL validation per queue, probably local, and
the flow solve, cross), and that must be measured per phase before the split.

## Cost of the cache hit, and the series

A hit costs bazel's input hashing plus a read of one file. nemik-check records its own CPU per run
with a `cache=hit|survey` label (nemik:W2513), so progress is a trend.

## Not decided here

The clock rule; capture of uncommitted queues; the local/cross split's seam; whether `nemik-check`
runs `bazel build` itself (the SessionStart hook must stay under 60 s wall, and a bazel server
start is not free) or reads a published action output from a known path.

## Steps, in order

1. Measure the survey per phase (CPU per queue's SHACL, per cross step) as a series (W2513).
2. Settle the clock rule and the capture rule (two rulings).
3. Split `survey` into local and cross functions with tests holding the union to today's output.
4. Add the per-queue actions, then the cross action; reading `--repo X` becomes a build of one
   output.
5. Remove W2511-v1's hand cache.
