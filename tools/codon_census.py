# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W566: the Codon-compatibility census of src/nemik, as logic a test can ratchet.

The operator aims all Python at Codon compatibility (nemik:W561). For every module this compiles
`import nemik.<module>` twice: as written, and with the `from __future__ import annotations` line
stripped from a scratch copy, because that one line blocks most modules and hides what comes next.
A module's entry is Codon's first error line, or "" when it compiles.

Two limits, both Codon's: it reports only the first error, and it checks function bodies only when
something instantiates them, so "compiles" here is an upper bound. The ratchet is on what can be
measured: a module that compiled must keep compiling, and a new module must not start out failing.

This file runs nothing itself. `census` takes a `Build` callable, which the test wires to the
installed-script runner, so the compiler is a hashed input (MODULE.bazel @codon), not found on PATH.
"""

import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path

ANSI = re.compile(r"\x1b\[[0-9;]*m")
FUTURE = re.compile(r"^from __future__ import annotations\s*$", re.MULTILINE)
MODES = ("as_written", "stripped")
WORKERS = 4

Build = Callable[[Path, Path], tuple[int, str]]
Census = dict[str, dict[str, str]]


def first_error(stderr: str) -> str:
    """Pick the first error line out of Codon's output.

    Args:
        stderr: The compiler's standard error, possibly coloured.

    Returns:
        The text after the first "error:", or the tail of the output when there is none.

    """
    for line in ANSI.sub("", stderr).splitlines():
        if "error:" in line:
            return line.split("error:", 1)[1].strip()
    return stderr.strip()[-200:]


def modules(src: Path) -> list[str]:
    """List the importable modules of the package, without __init__.

    Args:
        src: The directory holding the nemik package.

    Returns:
        The module names, sorted.

    """
    top = [p.stem for p in (src / "nemik").glob("*.py") if p.stem != "__init__"]
    # nemik:W818: the shared core is a subpackage the page runs as wasm: held to the census too
    core = [
        f"core.{p.stem}"
        for p in (src / "nemik" / "core").glob("*.py")
        if p.stem != "__init__"
    ]
    return sorted([*top, *core])


def stage(src: Path, tree: Path, *, strip: bool) -> None:
    """Copy the package into a scratch tree, optionally without the annotations future.

    Args:
        src: The directory holding the nemik package.
        tree: The scratch directory to fill.
        strip: Whether to remove `from __future__ import annotations` lines.

    """
    (tree / "nemik").mkdir(parents=True)
    for path in (src / "nemik").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        (tree / "nemik" / path.name).write_text(
            FUTURE.sub("", text) if strip else text, encoding="utf-8"
        )
    if (src / "nemik" / "core").is_dir():
        (tree / "nemik" / "core").mkdir()
        for path in (src / "nemik" / "core").glob("*.py"):
            text = path.read_text(encoding="utf-8")
            (tree / "nemik" / "core" / path.name).write_text(
                FUTURE.sub("", text) if strip else text, encoding="utf-8"
            )


def probe(build: Build, tree: Path, module: str) -> str:
    """Compile an import of one module from a staged tree.

    Args:
        build: Runs the compiler on a probe file, writing to an output path.
        tree: The staged scratch tree.
        module: The module to import.

    Returns:
        "" when it compiles, otherwise Codon's first error line.

    """
    flat = module.replace(".", "_")
    program = tree / f"probe_{flat}.py"
    program.write_text(f"import nemik.{module}\n", encoding="utf-8")
    status, stderr = build(program, tree / f"out_{flat}")
    return "" if status == 0 else first_error(stderr)


def census(src: Path, work: Path, build: Build) -> Census:
    """Measure every module in both modes.

    Args:
        src: The directory holding the nemik package.
        work: An empty scratch directory.
        build: Runs the compiler on a probe file, writing to an output path.

    Returns:
        {module: {"as_written": first error or "", "stripped": first error or ""}}.

    """
    names = modules(src)
    result: Census = {name: {} for name in names}
    for mode, strip in (("as_written", False), ("stripped", True)):
        tree = work / mode
        stage(src, tree, strip=strip)
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            verdicts = pool.map(partial(probe, build, tree), names)
            for name, verdict in zip(names, verdicts, strict=True):
                result[name][mode] = verdict
    return result


def regressions(now: Census, base: Census) -> list[str]:
    """Name every module that is worse than the baseline.

    Args:
        now: The current census.
        base: The recorded baseline.

    Returns:
        One line per module and mode that fails now but compiled in the baseline, or is new and
        fails.

    """
    return [
        f"{name} ({mode}): {verdict[:100]}"
        for name, modes in now.items()
        for mode, verdict in modes.items()
        if verdict and (name not in base or not base[name].get(mode))
    ]


def failing(counted: Census) -> dict[str, int]:
    """Count the modules that do not compile, per mode.

    Args:
        counted: A census.

    Returns:
        {mode: number of modules with a first error}.

    """
    return {mode: sum(1 for m in counted.values() if m.get(mode)) for mode in MODES}
