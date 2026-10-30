# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W273 (gcalculus:W225): how far each repo's pin of a peer trails the peer's HEAD.

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
from nemik.tomlview import table, tables

_PIN = re.compile(
    r"git\+https://github\.com/[\w.-]+/([\w.-]+?)(?:\.git)?@([0-9a-f]{7,40})\b"
)
_FILES = ("pyproject.toml", "MODULE.bazel")
# A vendored mtools wheel names its commit in its file name:
# mikemol_<dist>-0.1.0+<sha>-py3-none-any.whl (vendor/wheels/README.md); every mikemol_*
# distribution there is built from the mtools repo.
_WHEEL = re.compile(r"mikemol_\w+-[\d.]+\+([0-9a-f]{7,40})-py3-none-any\.whl")


class Pin(NamedTuple):
    """One repo's pin of a peer: the repo that holds it, the peer and the pinned sha."""

    repo: str
    peer: str
    sha: str


def pins(root: Path) -> list[Pin]:
    """Every distinct (repo, peer, sha) pin in the pin files of each repo under `root`.

    Returns:
        The distinct pins, sorted.

    """
    found: set[Pin] = set()
    for name in _FILES:
        for path in sorted(root.glob(f"*/{name}")):
            if path.parent.name.startswith("."):
                continue  # a worktree of another repo, not a repo (see check.workstream_files)
            text = path.read_text(errors="replace")
            found.update(Pin(path.parent.name, m[1], m[2]) for m in _PIN.finditer(text))
            found.update(
                Pin(path.parent.name, "mtools", w[1]) for w in _WHEEL.finditer(text)
            )
    return sorted(found)


def behind(root: Path, pin: Pin) -> int | None:
    """Count the commits the peer's HEAD is ahead of the pin.

    None when the peer is not cloned under `root` or does not know the pinned commit.

    Returns:
        The commit count, or None when the peer is not cloned or does not know the commit.

    """
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


RECEIPT = Path.home() / ".local/share/uv/tools/nemik/uv-receipt.toml"
_REV = re.compile(r"[?&]rev=([0-9a-f]{7,40})")


def installed(receipt: Path) -> str | None:
    """nemik:W379: the commit the host's `uv tool install` of nemik was made from.

    Read from uv's receipt (`git = "file:///...?rev=<sha>"`); None when nemik is not installed that
    way.

    Returns:
        The rev in the receipt's nemik requirement, or None when there is no receipt or no such
        requirement.

    """
    if not receipt.is_file():
        return None
    import tomllib

    tool = table(table(tomllib.loads(receipt.read_text(encoding="utf-8"))).get("tool"))
    for req in tables(tool.get("requirements")):
        if req.get("name") == "nemik" and (m := _REV.search(str(req.get("git", "")))):
            return m[1]
    return None


_IMAGE_SHA = re.compile(r"-([0-9a-f]{40})$")


def deployed(namespace: str = "nemik") -> str | None:
    """nemik:W455: the commit the cluster's nemik Deployment runs, from its image tag.

    The tag reads `.../nemik:<epoch>-<sha40>`; None when kubectl or the cluster cannot be read.

    Found 2026-10-13: pushes were confirmed on origin, but the ship stopped at 3470e43 and the page
    ran 60 commits behind for a day and a half with nothing saying so.

    Returns:
        The 40-hex commit at the end of the image tag, or None when kubectl or the cluster cannot
        be read or the tag carries none.

    """
    try:
        run = subprocess.run(
            [
                "kubectl",
                "-n",
                namespace,
                "get",
                "deploy",
                "-o",
                "jsonpath={.items[0].spec.template.spec.containers[0].image}",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    m = _IMAGE_SHA.search(run.stdout.strip()) if run.returncode == 0 else None
    return m[1] if m else None


class Options(argparse.Namespace):
    """The parsed command line of nemik-pins (nemik:W1187)."""

    repos: list[str]
    root: Path
    max_behind: int | None
    receipt: Path
    cluster: bool
    stuck_after: int


def main(argv: list[str] | None = None) -> int:
    """nemik-pins: how many commits each repo's pin of a peer is behind that peer's HEAD.

    Returns:
        6 when --max-behind is given and some pin is further behind than it, else 0.

    """
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
    ap.add_argument(
        "--receipt",
        type=Path,
        default=RECEIPT,
        help="uv's receipt for the host install of nemik (W379)",
    )
    ap.add_argument(
        "--no-cluster",
        dest="cluster",
        action="store_false",
        help="skip the deployed-image check (W455)",
    )
    ap.add_argument(
        "--stuck-after",
        type=int,
        default=5,
        help="call the ship stuck past this many commits (a fresh push is always briefly behind)",
    )
    args = ap.parse_args(argv, namespace=Options())
    worst = 0
    # nemik:W379: the host's own install of nemik's tools is a pin too, of nemik by the operator's
    # PATH; reinstalling stays a deliberate step, so this says how far behind it is and how to
    # level it.
    if not args.repos or "nemik" in args.repos:
        sha = installed(args.receipt)
        if sha is not None:
            n = behind(args.root, Pin("host", "nemik", sha))
            head = subprocess.run(
                ["git", "-C", str(args.root / "nemik"), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=False,
            ).stdout.strip()
            shown = "unknown" if n is None else n
            print(f"host installs nemik@{sha[:12]}: behind {shown}")
            if n:
                print(
                    f"  level it: uv tool install --force "
                    f"'nemik @ git+file://{args.root / 'nemik'}@{head}'"
                )
            worst = max(worst, n or 0)
        # nemik:W455: a push is not a deploy until the cluster runs it
        live = deployed() if args.cluster else None
        if args.cluster:
            if live is None:
                print(
                    "cluster deploys nemik@unknown (kubectl or the Deployment unreadable)"
                )
            else:
                n = behind(args.root, Pin("cluster", "nemik", live))
                shown = "unknown" if n is None else n
                print(f"cluster deploys nemik@{live[:12]}: behind {shown}")
                if n and n > args.stuck_after:
                    print(
                        "  the ship is stuck: a stuck ship goes to luthen-observability"
                    )
                elif n:
                    print(
                        "  in flight: the newest pushes are still building or rolling"
                    )
                worst = max(worst, n or 0)
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
