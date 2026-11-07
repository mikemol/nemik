# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2043: the import-and-call census builds its probe and refuses a bad command line."""

from pathlib import Path

import pytest
from codon_call import main, program, run_cpython

SRC = Path("src")
USAGE_ERROR = 2


def test_the_probe_imports_the_module_and_prints_one_call() -> None:
    """The probe is two lines: the dotted import and the printed call."""
    assert program("jsonparse", 'parse("[1]")') == (
        'import nemik.jsonparse\nprint(nemik.jsonparse.parse("[1]"))\n'
    )


def test_a_wrong_number_of_arguments_is_a_usage_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Too few or too many arguments print the usage and exit 2 without running anything."""
    assert main(["codon", "src", "jsonparse"]) == USAGE_ERROR
    assert "codon_call.py CODON SRC MODULE EXPR" in capsys.readouterr().err


def test_cpython_runs_the_same_probe_against_the_source_tree() -> None:
    """The CPython side reports the printed text on success and the last stderr line on failure."""
    assert run_cpython(SRC, "print(1 + 1)\n") == (0, "2")
    status, out = run_cpython(SRC, "raise KeyError('x')\n")
    assert status == 1
    assert "KeyError" in out
