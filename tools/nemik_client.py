"""nemik:W442: a minimal client for nemik's read API, standard library only.

It is the example another app copies: read hashes.json, fetch only the documents whose hash moved since
the last call, and keep them by path. Run against any static build or the deployed view:

    python3 tools/nemik_client.py https://<host>/            # every document, once
    python3 tools/nemik_client.py https://<host>/ --watch 60  # poll; print what changed

The contract is openapi.json and schema/*.schema.json, published beside the data.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
from typing import Any


class Client:
    """Keeps the documents it has fetched, keyed by path, with the hash it fetched them at."""

    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/") + "/"
        self.docs: dict[str, Any] = {}
        self.seen: dict[str, str] = {}

    def _get(self, path: str) -> Any:
        with urllib.request.urlopen(self.base + path, timeout=30) as r:
            return json.load(r)

    def refresh(self, prefix: str = "") -> list[str]:
        """Fetch every path under `prefix` whose hash moved; return the paths fetched."""
        hashes: dict[str, str] = self._get("hashes.json")
        moved = [
            p
            for p, h in sorted(hashes.items())
            if p.startswith(prefix) and self.seen.get(p) != h
        ]
        for path in moved:
            self.docs[path] = self._get(path)
            self.seen[path] = hashes[path]
        return moved


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="nemik_client", description=(__doc__ or "").splitlines()[0]
    )
    ap.add_argument("base", help="the view's base URL, e.g. https://nemik.example/")
    ap.add_argument(
        "--watch", type=float, metavar="SECONDS", help="poll and print what changed"
    )
    args = ap.parse_args(argv)
    client = Client(args.base)
    while True:
        for path in client.refresh():
            print(path)
        if not args.watch:
            return 0
        time.sleep(args.watch)


if __name__ == "__main__":
    raise SystemExit(main())
