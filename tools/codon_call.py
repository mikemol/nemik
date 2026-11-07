# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2043: the import-and-call census, the sensor for "passes alone, fails when called".

The census compiles `import nemik.<module>` only, and Codon checks a function body only when
something instantiates it, so a module can compile in the census and still fail on its first call.
This stages the package exactly as `codon_census.stage` does, writes a probe that imports a module
and prints one call, and runs the probe with the pinned Codon in both census modes (as written and
with the annotations future stripped) and with CPython. Each line says OK when the outputs agree
(and match the expected text, if one is given) and DIFF otherwise, with the compiler's first error.

    codon_call.py CODON SRC MODULE EXPR [EXPECTED]

CODON is the compiler binary, SRC the directory holding the nemik package, MODULE a module name
such as jsonparse, EXPR a call on it such as parse("[1]").
"""

import os
import sys
import tempfile
from pathlib import Path

from codon_census import first_error, stage
from mikemol.procrun.proc import capture

MODES = (("as_written", False), ("stripped", True))
USAGE_ERROR = 2
MIN_ARGS = 4
MAX_ARGS = 5


def program(module: str, expr: str) -> str:
    """Write the probe: import a module and print one call on it.

    Returns:
        The text of the probe program.

    """
    return f"import nemik.{module}\nprint(nemik.{module}.{expr})\n"


def run_codon(codon: Path, tree: Path, text: str) -> tuple[int, str]:
    """Run a probe with the compiler, from the staged package directory.

    Returns:
        The exit status and the standard output, or the first error line when it failed.

    """
    probe = tree / "probe_call.py"
    probe.write_text(text, encoding="utf-8")
    done = capture([str(codon), "run", str(probe)], cwd=tree)
    if done.returncode:
        return done.returncode, first_error(done.stderr)
    return 0, done.stdout.rstrip("\n")


def run_cpython(src: Path, text: str) -> tuple[int, str]:
    """Run the same probe with CPython against the source directory.

    Returns:
        The exit status and the standard output, or the last stderr line when it failed.

    """
    env = dict(os.environ, PYTHONPATH=str(src))
    done = capture([sys.executable, "-c", text], env=env)
    if done.returncode:
        return done.returncode, done.stderr.strip().splitlines()[-1]
    return 0, done.stdout.rstrip("\n")


def verdicts(
    codon: Path, src: Path, module: str, expr: str, expected: str | None
) -> list[str]:
    """Call one expression in both census modes and under CPython.

    Returns:
        One line per mode: OK, or DIFF with what each side printed.

    """
    text = program(module, expr)
    py_status, py_out = run_cpython(src, text)
    lines = []
    for mode, strip in MODES:
        with tempfile.TemporaryDirectory(prefix="codon-call-") as tmp:
            tree = Path(tmp)
            stage(src, tree, strip=strip)
            status, out = run_codon(codon, tree, text)
        same = status == 0 and py_status == 0 and out == py_out
        right = expected is None or out == expected
        if same and right:
            lines.append(f"OK    {mode:10} {module}.{expr} -> {out[:60]}")
        else:
            lines.append(
                f"DIFF  {mode:10} {module}.{expr} codon rc {status}: {out[:80]}"
                f" | cpython rc {py_status}: {py_out[:80]}"
            )
    return lines


def main(argv: list[str]) -> int:
    """Print the verdict lines for one module call.

    Returns:
        0 when every line is OK, 1 when any differs, 2 on a usage error.

    """
    if not MIN_ARGS <= len(argv) <= MAX_ARGS:
        sys.stderr.write(__doc__ or "")
        return USAGE_ERROR
    expected = argv[MIN_ARGS] if len(argv) == MAX_ARGS else None
    lines = verdicts(Path(argv[0]), Path(argv[1]), argv[2], argv[3], expected)
    sys.stdout.write("\n".join(lines) + "\n")
    return int(any(line.startswith("DIFF") for line in lines))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
