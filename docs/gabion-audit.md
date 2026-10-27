# What gabion finds in nemik

nemik:W1189, for W1175 (module splits) and W1176 (typed documents). Operator ruling, 2026-10-27 (relayed
by github-8f): gabion is the prior art for files that do too much; "I can't speak to whether or not
gabion does it well". Its output is **advisory evidence**: no nemik target, test or presubmit depends on
it, and a bundle is a candidate to confirm by reading, then pay down through nemik's own codemods.

## What was run

- gabion at `0d4041d9` (a `git archive` of ~/github/gabion, read-only; gabion was not woken or changed).
- `python -m gabion --analysis-budget-checks 50000000 check raw -- src/nemik`, on a scratch copy of
  `src/nemik` (144 files), under `systemd-run --user --scope` with MemoryMax=8G, MemorySwapMax=0 and
  CPUQuota=200%. The first run on the default budget (1,000,000 deadline checks, a count) stopped at 109
  of 144 files; the second finished all 144 in about 90 s.
- It exits 1 on its own gates (83 policy violations, 6 type ambiguities): gabion's governance rules for
  its own repo, not findings about nemik's code.

## Install findings (gabion is not patched)

1. It imports `click` and does not declare it (typer 0.27 no longer brings it).
2. Its declared `requires-python` is `>=3.11`, but it uses `ast.Interpolation` (Python 3.14), so it runs
   on 3.14 only; nemik's gate is 3.13, so it lives in a throwaway 3.14 venv outside nemik's build.
3. Installed as a wheel it reads repo-relative data files (`in/lg_kernel_ontology_cut_elim-1.ttl`) and
   fails outside a source tree: run it with `PYTHONPATH` at the extracted tree's `src`.
4. It maps paths against its working directory, so the analysed tree must sit inside it (a target outside
   the cwd fails in `path.relative_to(project_root)`): analyse a copy under the run directory.

## What it found

The audit reports parameter groups that travel together ("dataflow-grammar bundles"). The synthesis
output names about 80 tier-2 bundles, almost all two or three names. Its refactor plan keeps 22 of them,
nearly all inside one function, so they are weak evidence: `blue, green, red` in a luminance function is a
colour, not a missing type. The ones worth reading:

| Bundle (parameter names) | Where | Reading |
|---|---|---|
| `g, gate_weights, repo, residue, toward, weights, without, workable` (8) | names that travel between rank.py and salience.py (`gate_weights` is in only those two) | one call-context record: the 8-name group is the clearest "does too much" signal in the run |
| `fruit_row, g, repo, weights, with_working` (5) | the same pair of modules, by name (no function of that name in src: they are call keywords) | the same context, a smaller slice |
| `g, repo, weights` and `g, repo` | rank, blocks, stackable, history | the graph-and-repo pair passed everywhere; a `FleetView` record candidate |
| `now, window`, `now, start`, `now, days`, `now, seen`, `now, burst, rate`, `cites, interval, now, worked` | metrics, forecast, history, churn | a time window travels with its `now`: one `Window` record |
| `values, window` and `prior, values, window` | ratchetpace | already one concern; a `Series` record |
| `repo, root, workstreams`, `exports, root`, `check, phases, root` | check, serve, exportcli | the fleet root and its repos |
| `start, end, rrule, done, trigger` | calendars | a recurrence record |
| `since, dump`, `since, full`, `since, match`, `since, items, status` | history | the flags of one command |
| `self, touches, vector`, `self, when`, `self, tag` | score, rank classes | methods that pass fields of one object |
| `end, start` | climate | two functions: a span |

## What it does not see

It reads parameters, not documents. The 93 percent of nemik's mypy debt that comes from `json.loads` and
`tomllib` answers (`dict[Any, Any]`, `list[Any]`) shows up in none of its bundles. That gap is not
gabion's to fill. The user's ruling (2026-10-27): the shape of a document is what **JSON Schema** (the
declared shape, checked at the boundary) and **abstract base classes** (the typed interface consumers
read through) are for. So for **W1176** gabion is only a hint at where a record would replace a parameter
pile (`FleetView`, `Window`); the document boundary is designed from a schema per document, not derived
from the keys consumers happen to read (see W1176).

## Against the split signal (W1175)

The lazy-import census (158 function-local imports in 24 modules: serve 27, rank 24, check 15, vtodo 13,
calendars 11, witnesses 10, wake 9, mspdi 9) and gabion agree on **rank**: it holds the 8-parameter bundle,
the second-largest count of local imports and 24 of its own. That makes rank the first split to plan after
mspdi: separate the flow-solving functions (which take the 8-name context) from the row-composition ones.
`serve` and `check` hold many local imports but few bundles: their problem is breadth (each function
serves a different document), not a shared parameter pile, so gabion does not help there.

## Verdict

Useful as a second sensor, not a driver. It finds the signature pile in rank and the `now`/window family
cheaply; it misses the document-shaped debt that dominates the ratchet. Re-run it after a split to see
whether the bundle dissolved.
