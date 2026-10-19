# Cold document build: where the time goes

nemik:W724, corrected by W729. `serve.Model` plus `serve.static_data` over
`/home/mikemol/github`, cold caches, under cProfile, 2026-10-19. Run it with
`PYTHONSAFEPATH=1 PYTHONPATH=src`, so that neither the script's directory nor the installed
`nemik` in the venv (older than the source) is imported.

## The profile that counts: the repo source

**472.8 s** under cProfile (three commit gates were running, so the absolute time is inflated;
the shares are what to read).

| Share | Cost |
|---|---|
| 76% (358 s) | `shaclinc.findings`: pyshacl validating the shapes; 322 s of it is the 14 SPARQL constraints, 83,062 evaluations, mostly rdflib's `evalFilter` and `evalDistinct` |
| 7% (32 s) | `flow.solve`, 26 calls |
| 2% (7 s) | git, 85 process spawns (see below) |
| the rest | rdflib term churn, JSON decode, everything else |

The cost to cut is the SHACL SPARQL constraints (W729).

## What the earlier profiles got wrong

Two earlier runs (184.8 s and 157.8 s) imported the **installed** `nemik`, a stale build that
lacks the SHACL work, so they showed a subprocess-bound build (wait 23%, `flow.solve` 22%,
JSON decode, 3,931 git forks). That picture was real for that code but is not the build that
runs. Two claims made from it were wrong: that the earlier "496 s" figure was the commit gate's
time (it was probably this repo-source build, which runs at that order of magnitude), and that W404
(flow solve) should reopen at 22%. W404 was right to drop; W726 (a flow cache) was built,
measured at 2 s saved (931 of 3,375 sources repeat), and dropped.

## What did hold

The git fan-out was real in the code that ran it: `history.snapshots` forked `git show` once
per queue commit (3,931 calls, 43.6 s cumulative in the stale profile). After W725 (399075e) a
repo-source build spawns 85 git processes, 7.2 s cumulative.
