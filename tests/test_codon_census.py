# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W566: no module of src/nemik gets further from Codon than the recorded baseline.

The operator aims all Python at Codon compatibility (nemik:W561). tools/codon_census.py compiles an
import of every module with the pinned compiler (MODULE.bazel @codon), as written and with the
annotations future stripped. A module that compiled must keep compiling and a new module must not
start out failing; codon-baseline.json holds what each module hits first today.

On the host, `NEMIK_CODON_WRITE=1` rewrites the baseline from the current census, and only when
nothing is worse, so the file records progress and nothing else.

Idioms Codon refused here (nemik:W631): a return annotated `X | None` ("unsupported operand type(s)
for |: type[int] and Optional[T.8]", also for `list[list[str]] | None`). Use Optional[X] instead
(mtools probed Optional[int] on Codon 0.20.3 and it compiles on both paths; nemik has not yet),
a sentinel of the same type (shapedepth.UNBOUNDED = -1), or raise and let the caller catch.
"""

import json
import os
from pathlib import Path

import installed
import pytest
from codon_census import Census, census, failing, first_error, modules, regressions

ROOT = Path(__file__).resolve().parents[1]
_STAGED = os.environ.get("NEMIK_CODON")
if not _STAGED:
    pytest.skip(
        "the pinned Codon comes from bazel (MODULE.bazel @codon, W566)",
        allow_module_level=True,
    )
CODON = Path(_STAGED).resolve()
BASELINE = ROOT / "codon-baseline.json"


def _build(program: Path, out: Path) -> tuple[int, str]:
    """Run the pinned compiler on one probe file.

    Returns:
        The exit status and the compiler's standard error.

    """
    run = installed.run(
        str(CODON), "build", "-o", str(out), str(program), cwd=program.parent
    )
    return run.returncode, run.stderr


def _baseline() -> Census:
    """Read the recorded census.

    Returns:
        {module: {mode: first error or ""}}, empty when no baseline exists yet.

    """
    if not BASELINE.exists():
        return {}
    raw: object = json.loads(BASELINE.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return {}
    return {
        str(name): {str(mode): str(verdict) for mode, verdict in modes.items()}
        for name, modes in raw.items()
        if isinstance(modes, dict)
    }


def test_no_module_is_further_from_codon_than_the_baseline(tmp_path: Path) -> None:
    """A module that compiled stops compiling, or a new one fails to, and the gate refuses."""
    now = census(ROOT / "src", tmp_path, _build)
    base = _baseline()
    worse = regressions(now, base) if base else []
    assert worse == [], "\n".join(worse)
    if os.environ.get("NEMIK_CODON_WRITE") or not base:
        BASELINE.write_text(json.dumps(now, indent=1, sort_keys=True) + "\n")


def test_the_baseline_names_only_modules_that_exist() -> None:
    """A baseline entry for a deleted or renamed module would hide a rise under the old name."""
    assert set(_baseline()) <= set(modules(ROOT / "src"))


def test_a_module_that_stops_compiling_or_starts_failing_is_a_regression() -> None:
    """The ratchet's rule: compiled-before and fails-now, or new and failing."""
    base: Census = {
        "a": {"as_written": "", "stripped": ""},
        "b": {"as_written": "x", "stripped": "y"},
    }
    now: Census = {
        "a": {"as_written": "no module named 'x'", "stripped": ""},
        "b": {"as_written": "z", "stripped": "y"},
        "c": {"as_written": "", "stripped": "q"},
    }
    assert regressions(now, base) == [
        "a (as_written): no module named 'x'",
        "c (stripped): q",
    ]


def test_first_error_reads_the_first_error_line() -> None:
    """Colour codes go, and the text after the first 'error:' is the verdict."""
    stderr = "\x1b[1mfoo.py:1\x1b[0m: \x1b[31merror:\x1b[0m no module named 'x'\nnext"
    assert first_error(stderr) == "no module named 'x'"


def test_failing_counts_per_mode() -> None:
    """A mode's count is the number of modules with a first error."""
    counted: Census = {
        "a": {"as_written": "e", "stripped": ""},
        "b": {"as_written": "e", "stripped": "e"},
    }
    assert failing(counted) == {"as_written": 2, "stripped": 1}
