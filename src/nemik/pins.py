"""nemik:W273 (gcalculus:W225): how far behind a peer's HEAD is each repo's pin of it?

A pin is `git+https://github.com/<owner>/<peer>[.git]@<sha>` in a repo's pyproject.toml or
MODULE.bazel. For each pin of a peer that is also cloned under the root, this prints how many
commits the peer's HEAD is ahead of the pinned one. It reads local clones only and writes nothing:
whether the peer has PUBLISHED that HEAD is not asked here (a pin can only name a published commit).
"""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path
from typing import NamedTuple

from nemik.check import default_root

_PIN = re.compile(
    r"git\+https://github\.com/[\w.-]+/([\w.-]+?)(?:\.git)?@([0-9a-f]{7,40})\b"
)
_FILES = ("pyproject.toml", "MODULE.bazel")


class Pin(NamedTuple):
    repo: str
    peer: str
    sha: str


def pins(root: Path) -> list[Pin]:
    """Every distinct (repo, peer, sha) pin in the pin files of each repo under `root`."""
    found: set[Pin] = set()
    for name in _FILES:
        for path in sorted(root.glob(f"*/{name}")):
            if path.parent.name.startswith("."):
                continue  # a worktree of another repo, not a repo (see check.workstream_files)
            for m in _PIN.finditer(path.read_text(errors="replace")):
                found.add(Pin(path.parent.name, m[1], m[2]))
    return sorted(found)


def behind(root: Path, pin: Pin) -> int | None:
    """Commits the peer's HEAD is ahead of the pin; None when the peer is not cloned under `root`
    or does not know the pinned commit."""
    clone = root / pin.peer
    if not (clone / ".git").exists():
        return None
    run = subprocess.run(
        ["git", "-C", str(clone), "rev-list", "--count", f"{pin.sha}..HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    return int(run.stdout) if run.returncode == 0 and run.stdout.strip() else None


def main(argv: list[str] | None = None) -> int:
    """nemik-pins: how many commits each repo's pin of a peer is behind that peer's HEAD."""
    ap = argparse.ArgumentParser(
        prog="nemik-pins", description=(main.__doc__ or "").splitlines()[0]
    )
    ap.add_argument("repos", nargs="*", help="only these repos' pins (default: all)")
    ap.add_argument("--root", type=Path, default=default_root(), help="~/github")
    ap.add_argument(
        "--max-behind",
        type=int,
        default=None,
        help="exit 6 when any pin is more than this many commits behind",
    )
    args = ap.parse_args(argv)
    worst = 0
    for pin in pins(args.root):
        if args.repos and pin.repo not in args.repos:
            continue
        n = behind(args.root, pin)
        shown = "unknown (peer not cloned, or commit not in it)" if n is None else n
        print(f"{pin.repo} pins {pin.peer}@{pin.sha[:12]}: behind {shown}")
        worst = max(worst, n or 0)
    over = args.max_behind is not None and worst > args.max_behind
    return 6 if over else 0


if __name__ == "__main__":
    raise SystemExit(main())
