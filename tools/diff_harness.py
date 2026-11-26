# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
r"""nemik:W1522: a differential harness: freeze the inputs, mask clock fields, run old-new-old.

A change that must not alter a command's output is proved by running the command on the OLD source
tree, the NEW one, and the OLD one again, over the SAME frozen queue files, and comparing. The
second old run is the control: if it differs from the first, the inputs are not frozen (a clock, a
hash order) and the comparison means nothing, so the harness says `unstable` and names what moved,
never `equal`. Fields that legitimately hold a clock are masked by regexes named on the command
line (the proven ones: `\d+ h` and `\d+\.\d d`). PYTHONHASHSEED is 0 for every run.

  tools/diff_harness.py --old TREE --new TREE --mode "nemik.check --warnings --root <root>" \
      [--mode ...] [--mask REGEX ...] [--root ROOT]

`<root>` in a mode is the scratch copy of the queue files (each repo's paths-forward.json and
ledger), made once and shared by all three runs. A mode is `<module> <args>`, run as
`python -m <module> <args>` with `<tree>/src` first on PYTHONPATH. Exit 0 when every mode is equal,
1 on any drift, 2 on any unstable mode.
"""

import argparse
import re
import shutil
import sys
import tempfile
from pathlib import Path

from nemik.queuefiles import LEDGER, QUEUE, default_root, workstream_files
from nemik.spawn import capture

ROOT_MARK = "<root>"  # in a mode: the frozen copy of the queue files
EQUAL = "equal"
DRIFT = "drift"
UNSTABLE = "unstable"
SHOWN = 5  # differing lines printed
LIMIT = 600  # seconds one run may take
STATUS = {EQUAL: 0, DRIFT: 1, UNSTABLE: 2}


def masked(text: str, patterns: list[str]) -> str:
    """Replace every match of each pattern with a fixed token, so a clock field compares equal.

    Args:
        text: A run's output.
        patterns: Regexes naming the fields that legitimately differ between runs.

    Returns:
        The text with each match replaced by `<masked>`.

    """
    for pattern in patterns:
        text = re.sub(pattern, "<masked>", text)
    return text


def differences(left: str, right: str, limit: int = SHOWN) -> list[str]:
    """Name the first lines at which two texts differ.

    Args:
        left: The reference text.
        right: The text compared with it.
        limit: How many differing lines to name at most.

    Returns:
        One `line N: left | right` entry for each of the first `limit` differing lines, counting a
        line one side lacks as empty; none when the texts are equal.

    """
    a, b = left.splitlines(), right.splitlines()
    found: list[str] = []
    for at in range(max(len(a), len(b))):
        one = a[at] if at < len(a) else ""
        other = b[at] if at < len(b) else ""
        if one != other:
            found.append(f"line {at + 1}: {one} | {other}")
            if len(found) == limit:
                break
    return found


def verdict(
    first: str, changed: str, again: str, patterns: list[str]
) -> tuple[str, list[str]]:
    """Judge an old-new-old triple.

    Args:
        first: The old tree's output.
        changed: The new tree's output.
        again: The old tree's output, a second time.
        patterns: The clock-field regexes to mask (see masked).

    Returns:
        (UNSTABLE, the lines that moved between the two old runs) when the control differs, since
        nothing can then be concluded; else (DRIFT, the first lines at which new differs from old)
        or (EQUAL, []).

    """
    one, two, three = (masked(t, patterns) for t in (first, changed, again))
    moved = differences(one, three)
    if moved:
        return UNSTABLE, moved
    drift = differences(one, two)
    return (DRIFT, drift) if drift else (EQUAL, [])


def snapshot(root: Path, scratch: Path) -> int:
    """Copy each repo's queue and ledger to a scratch root, once.

    Args:
        root: The directory holding the repos.
        scratch: An empty directory to fill.

    Returns:
        How many files were copied.

    """
    copied = 0
    for name in (QUEUE, LEDGER):
        for repo, path in workstream_files(root, name):
            target = scratch / repo / ".claude" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            copied += 1
    return copied


def run(tree: Path, mode: str, root: Path, scratch: str) -> str:
    """Run one mode on one source tree over the frozen root.

    Returns:
        The run's stdout then its stderr, so a failure shows too.

    """
    words = mode.replace(ROOT_MARK, str(root)).split()
    argv = [
        "env",
        "PYTHONHASHSEED=0",
        f"PYTHONPATH={tree}/src",
        sys.executable,
        "-m",
        *words,
    ]
    done = capture(argv, LIMIT, scratch)
    return done.stdout + done.stderr


class Options(argparse.Namespace):
    """The parsed command line."""

    old: Path
    new: Path
    mode: list[str]
    mask: list[str] | None
    root: Path


def main(argv: list[str] | None = None) -> int:
    """Freeze the inputs, run each mode old-new-old and print the verdicts.

    Returns:
        0 when every mode is equal, 1 when any drifts, 2 when any is unstable.

    """
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--old", type=Path, required=True)
    ap.add_argument("--new", type=Path, required=True)
    ap.add_argument("--mode", action="append", required=True)
    ap.add_argument("--mask", action="append")
    ap.add_argument("--root", type=Path, default=default_root())
    args = ap.parse_args(argv, namespace=Options())
    worst = 0
    with tempfile.TemporaryDirectory() as made:
        frozen = Path(made) / "root"
        count = snapshot(args.root, frozen)
        sys.stdout.write(f"froze {count} files under {frozen}\n")
        for mode in args.mode:
            first = run(args.old, mode, frozen, made)
            changed = run(args.new, mode, frozen, made)
            again = run(args.old, mode, frozen, made)
            state, found = verdict(first, changed, again, args.mask or [])
            sys.stdout.write(f"{state}: {mode}\n")
            for line in found:
                sys.stdout.write(f"  {line}\n")
            worst = max(worst, STATUS[state])
    return worst


if __name__ == "__main__":
    sys.exit(main())
