# Why the codon baseline stops at 130, and what would move it

Measured 2026-11-05 at 151ec05 (codon baseline 130 entries, ruff 0, mypy 0). Cards: nemik:W1411
(the campaign), nemik:W1671 (the batch design), nemik:W1672 (the last cheap row).

Every ratchet's target is zero and no floor may be declared (operator, host transcript 695f3e0a
line 141395: "A declared floor is a temptation to declare a problem too hard to solve."). This page
is therefore not a floor. It names what stands between 130 and zero, so each wall can be taken down
on purpose.

## How the census reads a row

`tests/test_codon_census.py` compiles `import nemik.<module>` for every module with the pinned
Codon, twice: as written, and with `from __future__ import annotations` stripped. A module is
listed in `codon-baseline.json` with the first error of each mode.

A probe compile stops at the FIRST error. The listed error is therefore the nearest blocker, not the
only one: `queuerows` reads `datetime.UTC`, and once that is fixed it still imports `rdflib`. The
census itself is the same compile loop over every module, so its 7 to 8 minutes is paid once per
stack, however many rows the stack changes. Batching rows into one stack is right; writing "all the
probes" first cannot list the blockers, because the compiler never gets past the first.

## The closure map

A module compiles only if everything it imports, directly or through other nemik modules, compiles.
The static map reads each module's blocked imports by `ast` and unions them over its nemik import
closure (the scratch script is `codonclosure.py`; committing it as `tools/codon_closure.py` is
open on W1411). At 151ec05, about 58 of the 65 listed modules reach `adapter`, and through it the
walls below.

## The walls

| wall | what it blocks | what would retire it |
|---|---|---|
| `rdflib` (adapter and everything importing it) | about 58 rows | an rdflib-free core of adapter (a pure row model beside an rdflib view) AND each of the nine modules that import rdflib directly moving to it; measured below: removing this wall alone frees no row |
| the `mikemol.*` libraries (`procrun`, `pathsforward`, `endpoints`, `otlp`) | `work`, `ask_cli`, `alarm`, `endpoint`, `marks`, `pins` and their dependents | measured 2026-11-05: the census does not stage the libs, and the venv's `mikemol` has no top-level `__init__.py`; with both added, `mikemol.procrun` compiles but `mikemol.procrun.proc` stops at `no module named select` (it also imports `subprocess`) and `mikemol.pathsforward.lock` at a dataclass decorator. So the libraries themselves do not compile: an mtools question, or nemik's own thin stand-ins for the few calls it makes |
| `argparse`, `tomllib`, `shutil`, `subprocess`, `shlex` | the CLI modules, config readers | the CLI shells moved into a module already in the baseline (what W1668, W1669 and W1672 did for `critical`, `wake` and `floorasks`), and a Codon-compatible TOML reader |
| `dataclasses` decorator arguments, `fractions`, `weakref`, `contextlib`, `collections.abc`, `hashlib`, `importlib.*` | `cards`, `flow`, `issues`, `projection`, `salience`, `score`, `index`, `shaclcache`, `cachestore`, `marks` | per module: plain classes for `@dataclass(frozen=True)` (the pinned Codon accepts plain classes), a `typing` or builtin spelling for the others |
| strict typing | `apischema` (import row FREED by nemik:W2043): its `SCALAR` table mixed string and list values and Codon types the dict strictly | the import row is done: the schemas are built on an arena of typed nodes (`jsonarena`, `jsonparse`, `schemagen`) and returned as JSON text; the dict makers are `serve.py` and the tests. Not done: `apischema.load` and `unmanifested` still read JSON as an untyped object and do not compile when called (nemik:W2049). The import-and-call census (`tools/codon_call.py`) found that `import` alone can pass where a call fails |
| `from __future__`, `TYPE_CHECKING`, keyword-only `*,` markers | the stripped-mode errors of `alarm`, `calendars`, `check`, `history`, `hostapply`, `rank`, `stackable_cli`, `wake` (the bare star-comma, a syntax error) | per module, mechanical, but each module sits behind another wall as well. Tuple `except` is NOT a blocker: `roundcli` and `pacecli` use it and are not in the baseline (corrected 2026-11-05 after the cold review) |

## What the pattern buys

A CLI shell moved into a module that is already in the baseline removes the pure core's row at no
cost: the baseline loses two entries (one per mode) and gains none. W1672 is the last cheap
instance (`floorasks`). A new hub module would add two entries of its own, so it pays only when it
frees three or more rows.

## Rows that remain, by cost

1. Single-wall rows with a mechanical fix: none are left that sit outside `adapter` and the
   `mikemol` libraries (`apischema`'s import row was the last, freed by nemik:W2043; its calls remain nemik:W2049) except the dataclass rows `score`,
   `cards`, `flow`, `issues`, `projection`, `salience` (each also reaches `adapter`, so freeing one
   of them alone does not make it compile).
2. There is no single structural move. The first version of this page named the `adapter` split as
   the one lever; the static measurement below shows it frees no row on its own.

## How many walls fall before a row frees

`tools/codon_closure.py`'s functions, applied greedily (2026-11-05, 65 baseline rows): treat one
blocker kind at a time as fixed, most common first, and count the rows whose whole closure is then
empty. Fixing `adapter`'s own blockers alone frees 0 rows, and so does each of the first three kinds.

| fixed so far (cumulative) | rows free |
|---|---|
| `mikemol`, `TYPE_CHECKING`, `collections.abc` | 0 |
| plus `hashlib` | 1 |
| plus `importlib`, `rdflib` | 2 |
| plus `tomllib` | 14 |
| plus `dataclasses` (decorator and import), `argparse` | 20 |
| plus `contextlib`, `fractions`, `weakref` | 31 |
| plus `datetime.UTC`, `pyshacl`, `shutil` | 53 |
| plus `http`, `xml`, `google`, `shlex` | 65 |

So the work is a campaign over about seven kinds before the first fourteen rows free, not a lever.
`tomllib` is the biggest single step (2 to 14 rows) once the kinds before it are fixed. The order
above is by how many closures a kind sits in; a cheaper order may exist and is a question for a
measurement, not a conclusion. This is a static bound from imports, so it overstates what compiles:
a freed row can still fail on a type error, as `apischema.load` still does (nemik:W2049).
