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
| `rdflib` (adapter and everything importing it) | about 58 rows | an rdflib-free core of adapter: the graph builder is the foundation of every reader, so this is a split of adapter into a pure row model and an rdflib view, then each reader moving to the row model |
| the `mikemol.*` libraries (`procrun`, `pathsforward`, `endpoints`, `otlp`) | `work`, `ask_cli`, `alarm`, `endpoint`, `marks`, `pins` and their dependents | those libraries compiling under the pinned Codon (an mtools question), or nemik's own thin stand-ins for the three or four calls it makes |
| `argparse`, `tomllib`, `shutil`, `subprocess`, `shlex` | the CLI modules, config readers | the CLI shells moved into a module already in the baseline (what W1668, W1669 and W1672 did for `critical`, `wake` and `floorasks`), and a Codon-compatible TOML reader |
| `dataclasses` decorator arguments, `fractions`, `weakref`, `contextlib`, `collections.abc`, `hashlib`, `importlib.*` | `cards`, `flow`, `issues`, `projection`, `salience`, `score`, `index`, `shaclcache`, `cachestore`, `marks` | per module: plain classes for `@dataclass(frozen=True)` (the pinned Codon accepts plain classes), a `typing` or builtin spelling for the others |
| strict typing | `apischema`: its `SCALAR` table mixes string and list values and Codon types the dict strictly | a typed row class in place of the mixed dict |
| `from __future__`, `TYPE_CHECKING`, keyword-only `*,` markers, tuple `except` | the stripped-mode errors of `alarm`, `calendars`, `check`, `history`, `hostapply`, `rank`, `stackable_cli`, `wake` | per module, mechanical, but each module sits behind another wall as well |

## What the pattern buys

A CLI shell moved into a module that is already in the baseline removes the pure core's row at no
cost: the baseline loses two entries (one per mode) and gains none. W1672 is the last cheap
instance (`floorasks`). A new hub module would add two entries of its own, so it pays only when it
frees three or more rows.

## Rows that remain, by cost

1. Single-wall rows with a mechanical fix: none are left that sit outside `adapter` and the
   `mikemol` libraries except `apischema` (a typed row class) and the dataclass rows `score`,
   `cards`, `flow`, `issues`, `projection`, `salience` (each also reaches `adapter`, so freeing one
   of them alone does not make it compile).
2. The structural move: split `adapter` into a pure row model and an rdflib view. It is the only
   change that moves most of the list, it touches nearly every module, and it belongs to its own
   card with its own measurement.
