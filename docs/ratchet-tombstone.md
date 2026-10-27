# The ratchet tombstone

nemik:W1111, caused by mtools:W2045. How a repo retires a ratchet so the pace stops judging it, and
how the pace tells a retired ratchet from a broken one. **Read from mtools' source on 2026-10-27;
nothing here is nemik's invention.**

## The rule

**Retired is written, never inferred from silence** (operator, host 695f3e0a line 96701). A
ratchet's value series can stop because it was paid to zero, because it was renamed, or because the
census broke. Only a written tombstone tells the first two from the third.

## Where a repo writes one

In the repo's own `ratchets.json` (`mikemol.ratchet.declaration`), beside its live ratchets:

    {
      "ratchets": [{"path": "corpus/exit-baseline.txt", "kind": "baseline"}],
      "retired": [
        {"path": "old-baseline.json", "reason": "paid-to-zero-and-removed", "sha": "<retiring sha>"},
        {"path": "a.tsv", "reason": "renamed-to", "sha": "<retiring sha>", "to": "b.tsv"}
      ]
    }

- `reason` is one of `reclassified-not-a-ratchet`, `paid-to-zero-and-removed`, `renamed-to`.
- `sha` names the commit that retired it. It is required.
- `to` is given exactly when the reason is `renamed-to`, and only then.
- A path both declared and retired is a refusal, not a choice: one file cannot be a live ratchet and
  a dead one.
- A missing `ratchets.json` is no declaration, and a malformed one is a refusal, never read as empty.

## How it reaches nemik

1. `mikemol-ratchet census --repo <dir>` prints a line per live ratchet and one per tombstone,
   `<repo> <path> retired reason=<reason> sha=<sha>` (with ` to=<path>` after a rename).
2. `mikemol-ratchet-emit` (the gate's emit step) sends each tombstone as the series
   `mikemol.ratchet.retired{repo, ratchet, reason} = 1`, on every run for as long as the
   declaration lists it.
3. The pace run reads the store's export of it. `nemik.pacerun.retired_of` returns the
   `repo` + newline + `ratchet` keys whose newest sample is 1 or more.

## What the pace does with it (nemik:W1039, W1040)

| The ratchet's value series | A tombstone in the store | The pace row |
|---|---|---|
| goes on | none | judged as usual |
| goes on | listed | still judged: a retired ratchet that is still written stays judged |
| ended while its repo's others went on | none | `unknown`, never ok and never behind |
| ended while its repo's others went on | listed | **leaves the file**: it has no verdict to give |

So retiring a ratchet takes two things together: the series stops, and the tombstone is written. Stop
the series alone and the row reads `unknown` until someone writes the tombstone.

## A worked example

nemik retires `old-baseline.json` after paying it to zero:

1. Delete the file, and add `{"path": "old-baseline.json", "reason": "paid-to-zero-and-removed", "sha": "<sha>"}` to
   `retired` in the same commit.
2. The next gate run emits `mikemol.ratchet.retired{repo="nemik", ratchet="old-baseline.json", reason="paid-to-zero-and-removed"} = 1`
   and no value sample.
3. The next pace run sees the series ended and the tombstone listed, and drops the row.

## What is not covered

- A tombstone is not a re-baseline. A change of what a ratchet counts, with the file still live, is
  declared in `src/nemik/rebaselines.py` (W1046), and a requirement that was wrongly pinned is reset
  there too (W1165). Neither retires anything.
- `retired_of` takes the newest sample, so a tombstone removed from `ratchets.json` stops being
  sent, and a ratchet whose series has ended reads `unknown` again.
