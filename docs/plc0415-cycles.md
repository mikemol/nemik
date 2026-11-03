# PLC0415 sites that stay function-local

Ruff's PLC0415 asks every import to sit at the top of its module. Eleven sites in `src/nemik` stay
inside a function today, and one in `adapter.py` stays for a Codon reason. None is a waiver: each is
a recorded residue (nemik:W1562, from nemik:W1175), with the import it needs, the import that closes
the cycle, and the structural fix that would let it move. The ruff baseline still counts them, and the
list below is the work that retires them.

How the cycle was read: `plc_probe2.py` (the nemik scratch directory) hoists each site alone on a
copy of `src`, then imports `nemik.check`, `nemik.serve`, `nemik.history` and `nemik.rank` in
separate interpreters; a `partially initialized module` ImportError is a cycle. It also runs house
ruff F402, F811 and F401 on the hoisted file, which found the five name clashes that stack 935 and
stack 940 resolved by renaming and aliasing. A cumulative hoist of the sites that were safe alone
was checked the same way before stack 940 landed.

| Site (module:line, 2026-11-03) | Import | What closes the cycle | Structural fix |
| --- | --- | --- | --- |
| `check.py:835` | `from nemik import stalled` | `nemik.stalled` imports `nemik.history`, which imports `LEDGER`, `QUEUE`, `default_root` and `workstream_files` from `nemik.check` | move those path constants and `workstream_files` to a leaf module that `history` and `check` both import |
| `critical.py:491` | `from nemik.check import default_root, survey` | `nemik.check` imports `cycles` from `nemik.critical` | `default_root` to the same leaf; `survey` stays behind a function, or `critical` takes the survey as an argument |
| `history.py:1296` | `from nemik.churn import run` | `nemik.churn` imports `QueueDoc` from `nemik.history` | move `QueueDoc` to a typed-rows leaf; `churn` then imports the leaf, not `history` |
| `rank.py:551` | `from nemik.salience import salience_of` | `nemik.salience` imports `Weights` from `nemik.rank` | move `Weights` (and `load_weights`) to a leaf; `salience` imports the leaf |
| `rank.py:883` | `from nemik.salience import ask_effect, show` | the same `Weights` edge | the same leaf |
| `rank.py:906` | `from nemik.metrics import residue_gaps` | `nemik.metrics` is a hub that imports `nemik.rank` at module level (`checks/claims.py` pins that edge) | `residue_gaps` sits above `rank` in the stack; it moves to a module below both, or `rank` takes it as an argument |
| `rank.py:907` | `from nemik.salience import audit, load_gate_weights, load_wait_weight, show` | the same `Weights` edge | the same leaf |
| `rank.py:1151` | `from nemik.check import default_root, survey` | `nemik.check` imports `rank` | the `default_root` leaf; `survey` through an argument |
| `rank.py:1172` | `from nemik.critical import assume_done` | `nemik.critical` imports `rank` (`successors`) | move `assume_done` below both |
| `witnesses.py:608` | `from nemik.witwait import poller, seconds, wait` | `nemik.witwait` imports `_get` from `nemik.witnesses` | make `_get` a public name in a leaf used by both |
| `adapter.py:435` | `import hashlib` | not a cycle: standing rule 4, `hashlib` is outside Codon's supported modules | none until Codon supports it, or a Codon-friendly digest in a leaf |

The `Weights` edge accounts for three of the eleven (`rank.py` 551, 883, 907) and `default_root` for
two (`critical.py` 491, `rank.py` 1151), so two leaf modules retire five sites. A new `src/nemik`
module has costs the stack must pay: `bazel build //:.venv` before any wiring (hooks import `check`
and `rank`), `test_codon_census` compiled against the pinned Codon, and `checks/claims.py`'s declared
dependency sets for the hubs; the memory notes `new-module-breaks-live-readers` and
`new-module-must-compile-under-codon` hold the detail. That is why this is written down rather than
done in one stack.

Three other sites are not in `src/nemik`: `checks/claims.py` lines 126, 145 and 175 import nemik
modules inside functions because `claims.py` is run as a script and inserts `src` on `sys.path` after
its own imports; hoisting them would swap PLC0415 for E402 (module-import-not-at-top).
