# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2161: the image's interpreter is 3.14.7 or newer, with the generational collector.

The image once ran CPython 3.14.2 (the floating base tag's content), whose incremental collector
made the builder's nemik-serve use about 20 percent more memory than on 3.13 and got the pods
OOMKilled (nemik:W2159). A digest pins an image, not a behaviour, so the Containerfile runs this
right after `uv sync` and the build stops when it fails; tests/test_interpreter_floor.py holds the
rule itself. The collector is read by its behaviour: gc.get_threshold() carries a third generation
(10 on the generational collector, 0 on the incremental one), so a later patch that changes the
collector again is caught by what it does, not by its number.

    python3 tools/interpreter_floor.py        # exit 0: this interpreter passes
"""

import gc
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

FLOOR = (3, 14, 7)
THIRD_GENERATION = 2


def problems(
    version: Sequence[int], threshold: Sequence[int], executable: str
) -> list[str]:
    """Say what is wrong with an interpreter, one sentence each.

    Args:
        version: Its (major, minor, micro).
        threshold: Its gc.get_threshold().
        executable: Its sys.executable.

    Returns:
        The problems, empty when the interpreter passes.

    """
    found: list[str] = []
    if tuple(version[:3]) < FLOOR:
        have = ".".join(str(n) for n in version[:3])
        want = ".".join(str(n) for n in FLOOR)
        found.append(f"CPython {have} is below {want}")
    if len(threshold) <= THIRD_GENERATION or threshold[THIRD_GENERATION] == 0:
        found.append(
            f"gc.get_threshold() is {tuple(threshold)}: "
            "a zero third generation is the incremental collector"
        )
    if not executable:
        found.append("sys.executable is empty")
    return found


def main() -> int:
    """Check this interpreter and report on stdout or stderr.

    Returns:
        0 when it passes, 1 when it does not.

    """
    info = sys.version_info
    version = (info.major, info.minor, info.micro)
    found = problems(version, gc.get_threshold(), sys.executable)
    if found:
        sys.stderr.write("interpreter_floor: " + "; ".join(found) + "\n")
        return 1
    sys.stdout.write(
        f"interpreter_floor: CPython {'.'.join(str(n) for n in version)} at "
        f"{sys.executable}, gc.get_threshold() {gc.get_threshold()}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
