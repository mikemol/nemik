# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W543: the house mypy flags as a paydown-only ratchet.

mypy-house.ini holds mtools' strict flag set. Applying it through pyproject.toml would refuse every
edit to a file that already carries findings, so it is applied only by this stage, against a
baseline (mypy-baseline.json) of findings per file and error code. A count may fall, never rise,
and a code that shows up in a file with no baseline entry is a new finding. `--write` lowers the
baseline and refuses when any count would rise, so the file only ever records progress.

    python tools/mypy_ratchet.py            check the tree against the baseline (the gate)
    python tools/mypy_ratchet.py --write    lower the baseline to the current counts
    python tools/mypy_ratchet.py --init     write the first baseline (refused when one exists)
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from mypy import api

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "mypy-house.ini"
BASELINE = ROOT / "mypy-baseline.json"
TREES = ("src", "tests", "checks", "tools")
CLEAN_OR_FINDINGS = (0, 1)

Counts = dict[str, dict[str, int]]


def measure(root: Path = ROOT) -> Counts:
    """Count findings per file and error code over the tracked trees, by the house config.

    Args:
        root: The checkout to measure.

    Returns:
        {file: {error code: count}}, files relative to the root.

    Raises:
        SystemExit: When mypy itself fails rather than reporting findings.

    """
    out, err, status = api.run(
        [
            "--config-file",
            str(CONFIG),
            "--output",
            "json",
            "--no-error-summary",
            "--no-incremental",
            "--show-traceback",
            *(str(root / tree) for tree in TREES if (root / tree).is_dir()),
        ]
    )
    if status not in CLEAN_OR_FINDINGS:
        message = f"mypy_ratchet: mypy failed ({status}):\n{err}\n{out}"
        raise SystemExit(message)
    seen: Counter[tuple[str, str]] = Counter()
    for line in out.splitlines():
        item = json.loads(line)
        if item["severity"] != "error":
            continue
        name = str(Path(item["file"]).resolve().relative_to(root.resolve()))
        seen[name, item["code"] or "syntax"] += 1
    counts: Counts = {}
    for (name, code), n in sorted(seen.items()):
        counts.setdefault(name, {})[code] = n
    return counts


def regressions(now: Counts, base: Counts) -> list[str]:
    """List every file and code whose count is above the baseline's.

    Args:
        now: The current counts.
        base: The baseline counts.

    Returns:
        One line per regression.

    """
    return [
        f"{name}: {code} {n} > baseline {base.get(name, {}).get(code, 0)}"
        for name, codes in now.items()
        for code, n in codes.items()
        if n > base.get(name, {}).get(code, 0)
    ]


def total(counts: Counts) -> int:
    """Sum every count.

    Args:
        counts: Findings per file and code.

    Returns:
        The number of findings.

    """
    return sum(n for codes in counts.values() for n in codes.values())


def main(argv: list[str] | None = None) -> int:
    """Check, lower or initialise the baseline.

    Args:
        argv: The command line after the program name, or None for sys.argv.

    Returns:
        0 when no count is above the baseline, 1 otherwise.

    """
    parser = argparse.ArgumentParser(
        description=(__doc__ or "").split("\n", maxsplit=1)[0]
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="lower the baseline")
    mode.add_argument("--init", action="store_true", help="write the first baseline")
    args = parser.parse_args(argv)
    now = measure()
    if args.init:
        if BASELINE.exists():
            sys.stderr.write("mypy_ratchet: a baseline exists; use --write\n")
            return 1
        BASELINE.write_text(json.dumps(now, indent=1, sort_keys=True) + "\n")
        sys.stdout.write(f"mypy_ratchet: baseline of {total(now)} findings written\n")
        return 0
    base: Counts = json.loads(BASELINE.read_text())
    worse = regressions(now, base)
    if worse:
        sys.stderr.write("mypy_ratchet: findings above the baseline (fix them):\n")
        sys.stderr.write("\n".join(worse) + "\n")
        return 1
    if args.write:
        BASELINE.write_text(json.dumps(now, indent=1, sort_keys=True) + "\n")
    sys.stdout.write(f"mypy_ratchet: {total(now)} findings, baseline {total(base)}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
