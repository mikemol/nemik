# Cold document build: where the time goes

nemik:W724, corrected by W729. `serve.Model` plus `serve.static_data` over
`/home/mikemol/github`, cold caches, 2026-10-19. Measure it with `PYTHONSAFEPATH=1
PYTHONPATH=src`, so that neither the script's directory nor the installed `nemik` in the venv
(older than the source) is imported.

## Use a sampler, not cProfile

cProfile adds a cost to every function call, so it overstates call-heavy code (rdflib, pyshacl)
and understates tight loops. It put SHACL at 76% of the build; timed without a profiler the 14
SPARQL constraints take 4.7 s of a 130 s build (3.6%). A stack sampler (the main thread's stack
read every 20 ms, a few lines of Python with `sys._current_frames`) adds no per-call cost.

## The sampled build (81 s wall)

Share of samples with the function on the stack:

| Share | Where |
|---|---|
| 34% | `history.snapshots`: git reads 18%, JSON-parsing each committed queue 17% |
| 25% | `flow.solve` (`_grounded` 22%) |
| 21% | `check.survey` |
| about 13% | the adapter's graph builds (`_stamped`, `queue_graph`, `ledger_graph`) |
| under 4% | the SPARQL constraints |

So after the git change below the targets are the history parse (W729, W731), the flow
solve (W404 was right to be filed; a per-source cache measured 2 s and was dropped, W726),
and the survey.

## What the earlier numbers got wrong

- Two runs (184.8 s and 157.8 s) imported the installed `nemik`, a build older than the source,
  so they showed a subprocess-bound build (3,931 git forks).
- A run under cProfile (472.8 s) showed SHACL at 76%: profiler overhead, as above.

## What held

`history.snapshots` forked `git show` once per queue commit (3,931 calls). Since W725 (399075e)
it reads them through one `git cat-file --batch`: a repo-source build spawns 85 git processes,
7.2 s cumulative under cProfile.

## Not yet measured

The size of a committed queue. Today's nemik queue is 650,150 bytes over 621 commits; the
average over the history is unmeasured, and how much is accumulated card `evidence` text is
unknown. W731's first step measures it before anything is cached.
