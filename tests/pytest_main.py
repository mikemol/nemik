"""Run pytest over the modules bazel staged, as a `py_test` entry point.

⚑⚑⚑ WITHOUT THIS, `main = <the test module>` RUNS THAT MODULE AS A SCRIPT. Import-time code
executes, nothing collects, and the process exits 0 — so every `py_test` target reported GREEN
OVER ZERO ASSERTIONS. Measured: a module whose only statement was `raise AssertionError` PASSED,
and a module raising `SystemExit` at import was the probe that finally showed it. 23 targets had
been reporting green over nothing.

⚑⚑ THE ARGUMENT IS THE FILE, NOT A DIRECTORY. Passing `tests/` would collect every module in
every target and turn 23 witnesses into 23 copies of one suite — the failure would still be
reported, but never located, and a per-module target that does not isolate a module is a naming
exercise rather than a gate.
"""

from __future__ import annotations

import sys

import pytest

if __name__ == "__main__":
    sys.exit(pytest.main([*sys.argv[1:]]))
