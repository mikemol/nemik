# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2357: write the retro handoff baseline, which can only shrink.

The baseline (src/nemik/data/retro-handoff-baseline.json) names the retros whose handoff broke the
self-probe rule (nemik:RetroHandoffProbeShape) when it was cut; nemik-check reads those results as
Info and every other one as a Violation. It is never typed by hand:

  tools/retro_handoff_baseline.py --seed   write today's violators; refused once the file exists
  tools/retro_handoff_baseline.py --write  keep only the baselined retros that still violate
  tools/retro_handoff_baseline.py          print what --write would keep and drop, write nothing

--write can drop an id and never add one (nemik.retrobaseline.shrink), and the file is a registered
ratchet (ratchets.json) that rebaselines.json may never declare, so the gate refuses any growth.
"""

import argparse
import sys
from pathlib import Path

from nemik.check import RETRO_BASELINE, parse_retro_baseline, probe_violators
from nemik.queuefiles import default_root
from nemik.retrobaseline import shrink, stale

FILE = Path(__file__).resolve().parents[1] / "src" / "nemik" / "data" / RETRO_BASELINE
REFUSED = 2
SEED = "write today's violators once"
SHRINK = "drop the ids that no longer violate"


class Options(argparse.Namespace):
    """The parsed command line."""

    root: Path
    seed: bool
    write: bool


def render(ids: list[str]) -> str:
    """Write the baseline's text, as json.dumps(sorted(ids), indent=1) writes it.

    Args:
        ids: The retro ids (repo and retro, no character JSON escapes).

    Returns:
        A sorted JSON list, one id per line.

    """
    if not ids:
        return "[]\n"
    return "[\n" + ",\n".join(f' "{ident}"' for ident in sorted(ids)) + "\n]\n"


def main(argv: list[str] | None = None) -> int:
    """Seed, shrink or report the baseline.

    Args:
        argv: The arguments, or None for sys.argv.

    Returns:
        0 when done, 2 when a seed is refused because the baseline exists.

    """
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--root", type=Path, default=default_root())
    ap.add_argument("--seed", action="store_true", help=SEED)
    ap.add_argument("--write", action="store_true", help=SHRINK)
    args = ap.parse_args(argv, namespace=Options())
    today = probe_violators(args.root)
    if args.seed:
        if FILE.exists():
            sys.stdout.write(f"refused: {FILE.name} exists; it only shrinks\n")
            return REFUSED
        FILE.write_text(render(today), encoding="utf-8")
        sys.stdout.write(f"seeded {len(today)} retros\n")
        return 0
    held = parse_retro_baseline(FILE.read_text(encoding="utf-8"))
    kept = shrink(held, today)
    dropped = stale(held, today)
    if args.write and dropped:
        FILE.write_text(render(kept), encoding="utf-8")
    verb = "dropped" if args.write else "would drop"
    said = " ".join(dropped)
    sys.stdout.write(f"kept {len(kept)}, {verb} {len(dropped)}: {said}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
