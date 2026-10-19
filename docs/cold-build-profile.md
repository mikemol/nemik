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

The first run imported `flow.py` from a scratchpad copy because the script's directory led
`sys.path`. A clean re-run (`PYTHONSAFEPATH=1`, the installed `nemik.flow`) took **157.8 s**:
subprocess wait 35.8 s (23%), `flow.solve` 34.4 s (22%, 30.7 s in `_grounded`), rdflib
`Memory.add` 21.0 s (13%), JSON decode 15.1 s (10%), fork 2.9 s (2%). The ranking holds, with
the subprocess wait, decode and fork together at 35%. W404 (flow solve) was dropped on a wrong
6.9% figure; 22% justifies reopening it.
