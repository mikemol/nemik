"""nemik:W522: the house ruff rules as a paydown-only ratchet.

mtools selects every ruff rule. Selecting them here would refuse every edit to a file that already
carries findings, so the house config (ruff-house.toml) is applied only by this stage, against a
baseline (ruff-baseline.json) of findings per file and rule. A count may fall, never rise, and a rule
that shows up in a file with no baseline entry is a new finding. `--write` lowers the baseline and
refuses when any count would rise, so the file only ever records progress.

    python tools/ruff_ratchet.py            check the tree against the baseline (the gate)
    python tools/ruff_ratchet.py --write    lower the baseline to the current counts
    python tools/ruff_ratchet.py --init     write the first baseline (refused when one exists)
"""

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "ruff-house.toml"
BASELINE = ROOT / "ruff-baseline.json"
TREES = ("src", "tests", "checks", "tools")

Counts = dict[str, dict[str, int]]


def measure(root: Path = ROOT) -> Counts:
    """Findings per file and rule over the tracked trees, by the house config."""
    run = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--config",
            str(CONFIG),
            "--output-format",
            "json",
            "--no-cache",
            *(str(root / tree) for tree in TREES if (root / tree).is_dir()),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if run.returncode not in (0, 1):
        raise SystemExit(f"ruff_ratchet: ruff failed ({run.returncode}):\n{run.stderr}")
    seen: Counter[tuple[str, str]] = Counter()
    for item in json.loads(run.stdout):
        name = str(Path(item["filename"]).relative_to(root))
        seen[name, item["code"] or "syntax"] += 1
    counts: Counts = {}
    for (name, code), n in sorted(seen.items()):
        counts.setdefault(name, {})[code] = n
    return counts


def regressions(now: Counts, base: Counts) -> list[str]:
    """Every file and rule whose count is above the baseline's."""
    return [
        f"{name}: {code} {n} > baseline {base.get(name, {}).get(code, 0)}"
        for name, codes in now.items()
        for code, n in codes.items()
        if n > base.get(name, {}).get(code, 0)
    ]


def total(counts: Counts) -> int:
    return sum(n for codes in counts.values() for n in codes.values())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="lower the baseline")
    mode.add_argument("--init", action="store_true", help="write the first baseline")
    args = ap.parse_args(argv)
    now = measure()
    if args.init:
        if BASELINE.exists():
            print("ruff_ratchet: a baseline exists; use --write", file=sys.stderr)
            return 1
        BASELINE.write_text(json.dumps(now, indent=1, sort_keys=True) + "\n")
        print(f"ruff_ratchet: baseline of {total(now)} findings written")
        return 0
    base: Counts = json.loads(BASELINE.read_text())
    worse = regressions(now, base)
    if worse:
        print(
            "ruff_ratchet: findings above the baseline (fix them, never baseline them):",
            file=sys.stderr,
        )
        print("\n".join(worse), file=sys.stderr)
        return 1
    if args.write:
        BASELINE.write_text(json.dumps(now, indent=1, sort_keys=True) + "\n")
    print(f"ruff_ratchet: {total(now)} findings, baseline {total(base)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
