# Cold document build: where the time goes

nemik:W724. `serve.Model` plus `serve.static_data` over `/home/mikemol/github`, cold caches,
under cProfile (one run, 2026-10-19): **184.8 s**, 3,977 JSON decodes, 3,929 forked processes.

The earlier "496 s cold document build" was wrong: 496 s is the commit gate's Bazel elapsed
time, not this build. Do not cite it.

| Share of 184.8 s | Cost | What it is |
|---|---|---|
| 23% (43.4 s) | `select.poll` | waiting on child processes the build spawns |
| 22% (40.6 s) | `flow.solve` (26 calls, 36.3 s of it in `_grounded`) | exact Fraction flow solve |
| 11% (20.5 s) | `json.decoder.raw_decode` | 3,977 decodes of child output |
| 11% (20.3 s) | rdflib `Memory.add` | 953,932 triples added |
| 5% (8.5 s) | `fork_exec` | 3,929 process spawns |

The first and fifth rows are one cost, per-repo subprocess fan-out (about 28% together), and
the third is its output. Ordered by share: subprocess fan-out and decode, then the flow solve,
then rdflib.

The run imported `flow.py` from the scratchpad copy (`scratchpad/nemik/flow.py`) because the
script's directory led `sys.path`; re-run from a clean directory before acting on the flow
row. W404 (flow solve) was dropped on a wrong 6.9% figure and should be reconsidered against
the 22% here once that is confirmed.
