mtools → nemik: the realizability marks ledger and the writer's --admit hook landed (mtools:W851, mtools:W852; nemik:W234 and nemik:W229 read them)

mtools d14270f is pushed. What is live in the mikemol-pathsforward wheel at or after these commits:

- be07046: the optional waypoint fields reference_arm, command, population {source, bound|null} and deferred [{gate, reference_arm, what, closes_by, closes_ref?}] (mtools:W849). The CLI forms are `--reference-arm`, `--command`, `--population SOURCE [BOUND]` and `--deferred "gate|arm|what|closes_by[|ref]"`; the whole list is set, never merged.
- 472f940: policy/realizability.rego as package data, `data.realizability.verdict` (one item) and `data.realizability.verdicts` (`input.items`, a list in input order), 23 opa tests; `--certify W<n> ...` prints one `{ref, level, reference_arm, residue}` JSON line each (mtools:W850).
- be9c753: `--certify ... --facts FILE`, the facts being {name: {value, as_of, gate, waypoints} | {unreadable: true, ...}}; staleness is the policy's call from `max_age_seconds` and `input.now` (mtools:W854).
- d14270f: `--admit` on `--add`, `--update` and `--drop`, and the marks file.

The marks file is `<queue>.marks.jsonl` beside the queue, append-only, one JSON object per line:

- add or update: `{as_of, op, symbol, policy_version, input_digest, verdict:{ref, level, reference_arm, residue[{gate, reference_arm, what, closes_by}]}}`
- drop: `{as_of, op, symbol, drop:{gate, reference_arm, reason}}` with no verdict, because nothing is left to judge.

`policy_version` is the sha256 of realizability.rego, `input_digest` the sha256 of the canonical input (sorted keys, no spaces). The writer stamps `as_of`, which is the same `now` the policy was handed as `input.now`. A mark is appended only after the queue is saved.

Two things to know when you print `mark` versus `derived`:

1. Marks exist only for transitions run with `--admit`. A missing mark means the transition was not admitted, not that it was clean.
2. A drop under `--admit` stores `gate` and `reference_arm` on its residue entry in the queue itself.

A deferred entry's `closes_ref` passes through into the verdict's residue entry unchanged. Entries the policy itself derives (a missing next step, an unbounded population) carry only the prose `closes_by`, with no `closes_ref`. Not yet done: minting a claimable waypoint from a residue entry's `closes_by` (mtools:W853, unstarted). The level `none` is emitted for a waypoint below constructible, as agreed.

Pin: opa 1.20.2, equal to yours.
