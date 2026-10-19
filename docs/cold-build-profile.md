# Cold document build: where the time goes

nemik:W724, corrected by W729. `serve.Model` plus `serve.static_data` over
`/home/mikemol/github`, 2026-10-19.

## How to measure

- **Put the repo source on the path:** `PYTHONSAFEPATH=1 PYTHONPATH=src`. Two early profiles
  imported the `nemik` installed in the venv, a build older than the source, and measured code
  that no longer runs.
- **Sample, do not cProfile.** cProfile adds a cost to every function call, so it overstates
  call-heavy code (rdflib, pyshacl). A stack sampler (the main thread's stack read every 20 ms
  with `sys._current_frames`, a few lines of Python) adds none.
- **Say which caches are warm.** There are two, and the results differ by a factor of two:
  - the SHACL and flow result cache (`cachestore`, `build-caches-*.pickle` in the user cache
    directory), and
  - the slim queue per git blob (`slim/<blob id>.z` in the same directory, W729).
  A "cold" build means both empty: point `NEMIK_CACHE_DIR` at an empty directory.

## Measured (sampler, one run each)

| Run | Wall | Where the time is (share of samples with the function on the stack) |
|---|---|---|
| History cache absent, SHACL cache warm | 81 s | `history.snapshots` 34% (git reads 18%, JSON parse 17%), `flow.solve` 25%, `check.survey` 21% |
| Both caches empty (a freshly started pod) | 162 s | `shaclinc.findings` 67%, `history.snapshots` 14%, `flow.solve` 9% |
| SHACL cache empty, slim history files kept | 96 s | `shaclinc.findings` 46%, `flow.solve` 19%, `history_doc` 5.7% |

So: history was a third of a SHACL-warm build and is now about 6% of one (W725 removed the git
forks, W731 and W729 the parse and the reads). With every cache empty the build is two thirds
SHACL validation. Which case matters depends on whether the pod restores its cache at start,
which has not been checked here.

## What the earlier numbers got wrong

- Two runs (184.8 s and 157.8 s) imported the stale installed `nemik` and showed a
  subprocess-bound build (3,931 git forks).
- A cProfile run (472.8 s) put SHACL at 76%; unprofiled and with a warm SHACL cache the 14
  SPARQL constraints take 4.7 s, because most validations are answered from the cache.
- `flow.solve` was 6.8% under cProfile and 9 to 25% sampled, depending on the other work. A
  per-source cache of its solves (W726) saved 2 s and was dropped.

## Not yet measured

- Whether the pod starts with an empty cache directory (then the 162 s row is its first build).
- The size of a committed queue over time: today's nemik queue is 650,150 bytes over 621
  commits, mean 215,236 bytes per commit, half of it card `evidence` text.
