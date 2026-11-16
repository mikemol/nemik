# The ratchet atomizer: one leaf card per debt row, one umbrella per ratchet row

Design for nemik:W1994 under nemik:W1993. The operator's words (host transcript 695f3e0a, line
142923, uuid 43f11ee8-ffdf-4fe5-a8d7-5a0f4fb6cd90, 2026-11-06T00:49:59.912Z, human origin):
"This is why I want mechanized atomization of ratchet work." The case that prompted it: one rolling
card over about 45 `hooks/pyproject.toml` entries held a second card for days, and nothing could say
which entry mattered. One card per entry makes such a block precise, or visibly false.

## What it generalizes

`tools/atomize_walls.py` cards the Codon walls: a wall card per blocker kind, a row card per baseline
module waiting on the walls of its import closure. That is one ratchet. The atomizer takes any
declared ratchet.

## Input: rows as data

A row is `(ratchet, key, file, rule)`:

- `ratchet`: the ratchet file the census reads (`codon-baseline.json`, a `pyproject.toml`
  per-file-ignores table, a text baseline).
- `key`: the entry's identity in its own file.
- `file` and `rule`: where the shape has them. A per-file-ignores entry is one `(file, rule)` per
  RULE, so a ratchet's value counts rules, not files. A text baseline lists the line as the key and
  has no rule.

The reader of the census is mtools' (`mikemol-ratchet census --entries`, mtools:W2306): read-only, one
JSON line per entry, the per-entry counts equal the census value. Until it lands the generator runs
on nemik's own rows. The plan function takes the rows as DATA, not the Codon closure, so a test feeds
it fixture rows.

## Output: a dry-run plan

- One umbrella card per ratchet row (the ratchet file, or the file within it that holds the debt).
- One leaf card per entry `(file, rule)`, under its umbrella through an `enables` edge.
- The plan is a list of specs (title, manifest, size, waits-on) and is printed by default; `--apply`
  writes it, through the repo's own paths-forward writer and never the file, and never through a
  sibling's queue.

Idempotent by title. A title is a function of the row alone (ratchet, key, rule), so a second run
finds each card again, writes its manifest and blockers again, and creates none. A partial run is
finished by running it again.

## Close: derived, never by hand

A leaf closes when its row has left the census. The open set is derived from the ratchet file; the
cards of rows that are gone are closed through the writer. A check warns on a leaf closed by hand
while its row is still in the census (nemik:W1995). This is the half that stops a card claiming a
fall the ratchet does not show.

## Grouping

Where the ratchet's rows are Python modules and an import graph exists, the leaves of a module wait on
the leaves of the modules it imports, as the hierarchy mode already does for Codon
(`tools/codon_closure.py` own_row deps), so the flow's downstream weight finds the levers (nemik:W1996).
A ratchet with no graph gets its leaves under its umbrella only.

## Counts and caveats (read-only, from the published pace of 2026-11-06T00:47:24Z, 106 rows)

106 ratchet rows and 555 entries: mtools 90 rows and 422 entries (`hooks/pyproject.toml` 113,
`.claude/unmanifested-baseline.txt` 124, `pyproject.toml` 30, pkgbuild 17, pathsforward 14, gatecheck
10, importdag 9), nemik 5 rows and 133 (codon 130; the ruff and mypy values were stale), the rest 0.

- A glob-keyed or non-path row may not map to one card per file and rule.
- An `unknown` row carries a stale value and is skipped, not planned.
- mtools' `.claude/unmanifested-baseline.txt` entries ARE cards already: a leaf per entry would
  duplicate them, so that ratchet is excluded, or its leaves are the existing cards.

## Owner

nemik owns the generator, the close derivation and the grouping (the import graph and the flow's
salience are nemik's). mtools owns the census row reader. A fleet tool drains into mtools when a second
repo runs it. Each repo applies the plan to its own queue.

## Order

1. The plan over rows as data, with a test on fixture rows (this design's first code).
2. The close rule and its check (nemik:W1995), after the plan.
3. The grouping by import graph (nemik:W1996), after the plan.
4. The census input, when mtools:W2306 lands.
5. The rolling-blocker check (nemik:W1997) is independent: it reads the landings document.
