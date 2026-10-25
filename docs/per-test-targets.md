# One Bazel target per test: what it costs (nemik:W1035)

A measurement for the generator W1036 would write, run on the host on 2026-10-25 while a commit gate
was also running. The load matters: every figure below is a loaded figure, not a floor.

## How many tests

`pytest --collect-only` collected 1452 test items. Five test files (`test_check_run_rows`,
`test_cvd_palette`, `test_published_valid`, `test_run_row_schema`, `test_runrows`) could not be
collected by the bare interpreter, because they need native jsonschema and numpy modules; together
they define 19 test functions. So nemik has at least 1471 test items, and parametrized ones may
add more. Nemik today has about 410 Bazel targets, one per test module.

## What Bazel itself costs at that count

A scratch workspace of 1500 trivial `sh_test` targets (a `t.sh` that exits 0), made by a list
comprehension in one BUILD file:

| Run | Wall time |
| --- | --- |
| cold, fresh server and output base (includes fetching `rules_shell`) | 13.0 s |
| warm, nothing changed | 2.1 s |

Loading and analysis of 1500 targets is not the obstacle.

A cold analysis of nemik's own 411 targets (172 packages, 9836 configured targets) took 35 s on a
fresh output base.

## What one target costs to run

`bazel test //:test_shard_select --cache_test_results=no`, a test of three pure functions that does
no work: the test action spent about 50 s in the sandbox (critical path 50.6 s), almost all of it
before pytest started. The runfiles each target stages are large and the same for every module:
the built venv, Chromium, opa, the Codon compiler and the corpus. The cost is staging them into a
sandbox, once per target.

So a target per test node would pay that fixed cost 1471 or more times. A target per module pays
it about 410 times, and `test_pdf` split into three shards (W1044) pays it three times for one
module. This is the reason a per-test generator cannot start by writing targets.

## What this does not show

- The 50 s is under load from a running gate. An idle figure was not taken, so how much of it is
  contention is unknown.
- How much of the staging is the venv, how much Chromium and how much the rest was not separated.
- Whether Bazel reuses staged runfiles between targets under other sandboxing settings was not
  tried.
- Whether luthen's gate series (`mikemol.gate.target.*`) can carry a label per test was not asked.

## What follows

W1036 should not be a generator of targets from collected nodes until the data of a target is the
data its test reaches. Narrowing each target's `data` (importdag, when mtools has it) comes first;
until then the gain is in sharding the slow modules, as W1044 does.
