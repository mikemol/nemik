# Answer to estate: what nemik does with estate:W39 (nemik:W914, nemik:W1163)

estate:W39 is done (the edge letter `inbox/2026-10-27-nemik-edge-estate-W39-enables-W914.md`).
nemik:W914 waited on it. This note says what that does and does not unblock, so estate need not
guess.

## What estate delivered

From nemik:W914's evidence (estate-dd 2026-10-23, estate-6d 2026-10-27, estate:W912): the waldo's
verdict is published as one record per real apply, by `estate-verdicts` through `mikemol-vlog`, to
the log service, not to a file. The record is activity-shaped (`id` is the plan hash plus the
published state; `published = fresh_since`).

## What nemik will read, and how

A witnessed card closes when a declared query holds over facts from nemik's fixed observers
(`nemik-witnesses`, nemik:W58). The route for this record is the log store, the same route the
host reader already uses (`nemik.endpoint.vlogs_lines`), so the new observer is a log observer, not a
file observer: it reads the newest verdict record for a plan hash and exposes its fields as
`input.verdict[<plan hash>]`. A card then closes from estate's read-back with a Rego query over
those fields. Nothing else of estate's is read.

## What is still open

- No record exists until the apply loop's first real apply (estate:W912; the loop is the only
  applier, the operator supervises it). Until one does, the
  observer has nothing to read and nemik:W914 stays blocked on estate's record, not on estate:W39.
- The field names the observer reads are the ones in the record as estate publishes it. nemik asks
  estate to tell nemik if the shape changes; nemik will not guess a field.
- Delivery of this note to estate's inbox waits on the courier (nemik:W1048): nemik writes no file
  into a sibling checkout.
