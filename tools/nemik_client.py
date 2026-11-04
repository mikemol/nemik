# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W442: a minimal client for nemik's read API, standard library only.

It is the example another app copies: read hashes.json, fetch only the documents whose hash moved
since the last call, and keep them by path. Run against any static build or the deployed view:

    python3 tools/nemik_client.py https://<host>/            # every document, once
    python3 tools/nemik_client.py https://<host>/ --watch 60  # poll; print what changed

The contract is openapi.json and schema/*.schema.json, published beside the data.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from typing import IO, cast


class Client:
    """Keeps the documents it has fetched, keyed by path, with the hash it fetched them at."""

    def __init__(self, base: str) -> None:
        """Remember `base` with a trailing slash and start with no documents fetched."""
        self.base = base.rstrip("/") + "/"
        self.docs: dict[str, object] = {}
        self.seen: dict[str, str] = {}

    def _get(self, path: str) -> object:
        # JSON documents decode; anything else (the TRS feeds are Turtle, W449) is kept as text
        opened = cast("IO[bytes]", urllib.request.urlopen(self.base + path, timeout=30))
        with opened as r:
            if path.endswith(".json"):
                return cast("object", json.load(r))
            return r.read().decode()

    def refresh(self, prefix: str = "") -> list[str]:
        """Fetch every path under `prefix` whose hash moved; return the paths fetched.

        Returns:
            The paths fetched, in sorted order.

        """
        raw = self._get("hashes.json")
        hashes = (
            {str(p): str(h) for p, h in raw.items()} if isinstance(raw, dict) else {}
        )
        moved = [
            p
            for p, h in sorted(hashes.items())
            if p.startswith(prefix) and self.seen.get(p) != h
        ]
        for path in moved:
            self.docs[path] = self._get(path)
            self.seen[path] = hashes[path]
        return moved


class Options(argparse.Namespace):
    """The parsed command line, typed so reading it adds no Any."""

    base: str
    watch: float | None


def main(argv: list[str] | None = None) -> int:
    """Fetch the published view's changed paths, once or on each poll with --watch.

    Returns:
        0, after printing the paths fetched.

    """
    ap = argparse.ArgumentParser(
        prog="nemik_client", description=(__doc__ or "").splitlines()[0]
    )
    ap.add_argument("base", help="the view's base URL, e.g. https://nemik.example/")
    ap.add_argument(
        "--watch", type=float, metavar="SECONDS", help="poll and print what changed"
    )
    args = ap.parse_args(argv, namespace=Options())
    client = Client(args.base)
    while True:
        for path in client.refresh():
            sys.stdout.write(f"{path}\n")
        if not args.watch:
            return 0
        time.sleep(args.watch)


if __name__ == "__main__":
    raise SystemExit(main())
