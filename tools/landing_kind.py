# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""landing_kind: whether a landed commit ships to the pod, from its paths (nemik:W1083).

nemik:R495 finding 3: `landed` needs a witness and `done` needs none, so when the close refused
eight landed marks the cheapest compliant act was to mark them done. Which landings ship is
derivable from the paths: a push to main is a Flux ship (build, deploy-state, namespace nemik), and
only some paths reach the running image. This names the kind; writing the mark and refusing `done`
without a witness on an image landing belong to the writer (mtools), and the hook that calls this
is carded.

    python3 tools/landing_kind.py PATH [PATH ...]    prints `image` or `ref`

Pure: standard library only, no git, no queue.
"""

import sys

# the paths the runtime image is built from (Containerfile: the final stage copies the package, its
# vendored wheels and manifests, and the dependency pins); a change under one reaches the pod
IMAGE_PREFIXES = ("src/", "vendor/", "deploy/", ".forgejo/")
IMAGE_FILES = ("Containerfile", "pyproject.toml", "uv.lock")


def ships(path: str) -> bool:
    """Say whether a changed path reaches the running image.

    Returns:
        True for a path under the package, its vendored wheels, the deploy manifests or the build
        workflow, and for the Containerfile and the dependency pins.

    """
    return path.startswith(IMAGE_PREFIXES) or path in IMAGE_FILES


def kind(paths: list[str]) -> str:
    """Name a landing's kind from the paths it changed.

    Returns:
        `image` when any path ships (its witness is an image tag that carries the commit), else
        `ref` (a git ref witness: tests, docs, tools and queue files reach no pod).

    """
    return "image" if any(ships(p) for p in paths) else "ref"


def main(argv: list[str]) -> int:
    """Print the kind of a landing named by its paths.

    Returns:
        0, or 2 when no path is given.

    """
    if not argv:
        sys.stderr.write("usage: landing_kind.py PATH [PATH ...]\n")
        return 2
    sys.stdout.write(f"{kind(argv)}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
