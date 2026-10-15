# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W502: serve a published snapshot as files, with no model, no graph and no rdflib.

Operator ruling 2026-10-15 (W500): the pod serves prebuilt snapshots and does no graph work, so
request count and graph churn scale independently. A request is a file read; a rebuild happens in a
short-lived process elsewhere and is published under ROOT/current (a symlink flipped atomically) or
simply as ROOT itself. Pieces are validated by the sha256 hashes.json already lists (nemik:W414), so a
client revalidating with If-None-Match costs a header exchange, not a body.

stdlib only on purpose: a test holds this module to never importing rdflib.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import shutil
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript",
    ".json": "application/json",
    ".ttl": "text/turtle",
    ".css": "text/css",
}
METRICS_TYPE = "text/plain; version=0.0.4"


def snapshot(root: Path) -> Path:
    """The directory being served: ROOT/current when a publisher flips that link, else ROOT."""
    live = root / "current"
    return live if live.is_dir() else root


def resolve(base: Path, target: str) -> Path | None:
    """The file a URL path names under `base`, or None when it names nothing there or escapes it."""
    parts = [p for p in unquote(urlsplit(target).path).split("/") if p]
    if any(p in {".", ".."} or "\\" in p or "\x00" in p for p in parts):
        return None
    path = base.joinpath(*parts)
    if path.is_dir() and (path / "index.html").exists():
        path = path / "index.html"
    elif not path.is_file() and parts:
        # /wake, /operator, /inbound[/<repo>] and /goals/<repo>, as the live server spelled them
        path = path.with_name(path.name + ".json")
    try:
        real = path.resolve(strict=True)
    except OSError:
        return None
    top = base.resolve()
    inside = real == top or top in real.parents
    return real if inside and real.is_file() else None


class Hashes:
    """hashes.json, reread only when its file changes."""

    def __init__(self) -> None:
        self._seen: tuple[Path, int] | None = None
        self._table: dict[str, str] = {}

    def table(self, base: Path) -> dict[str, str]:
        path = base.resolve() / "hashes.json"
        try:
            stamp = (path, path.stat().st_mtime_ns)
            if stamp != self._seen:
                loaded = json.loads(path.read_text())
                self._table = {str(k): str(v) for k, v in loaded.items()}
                self._seen = stamp
        except (OSError, ValueError, AttributeError):
            self._table, self._seen = {}, None
        return self._table


def etag(base: Path, real: Path, table: dict[str, str]) -> str:
    """A file's validator: its published sha256 when hashes.json lists it, else size and mtime."""
    rel = real.relative_to(base.resolve()).as_posix()
    if digest := table.get(rel):
        return f'"{digest}"'
    stat = real.stat()
    return f'W/"{stat.st_mtime_ns:x}-{stat.st_size:x}"'


def matches(header: str | None, tag: str) -> bool:
    """Whether an If-None-Match header covers `tag`."""
    if not header:
        return False
    wanted = [t.strip() for t in header.split(",")]
    return "*" in wanted or tag in wanted or tag.removeprefix("W/") in wanted


def handler(root: Path) -> type[BaseHTTPRequestHandler]:
    hashes = Hashes()

    class H(BaseHTTPRequestHandler):
        def reply(
            self, code: int, ctype: str, body: bytes, tag: str | None = None
        ) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache")
            if tag:
                self.send_header("ETag", tag)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def stream(self, real: Path, ctype: str, tag: str) -> None:
            """A file in 64 KiB chunks: memory does not grow with the file or with concurrent reads."""
            try:
                with real.open("rb") as f:
                    self.send_response(200)
                    self.send_header("Content-Type", ctype)
                    self.send_header(
                        "Content-Length", str(os.fstat(f.fileno()).st_size)
                    )
                    self.send_header("Cache-Control", "no-cache")
                    self.send_header("ETag", tag)
                    self.end_headers()
                    if self.command != "HEAD":
                        shutil.copyfileobj(f, self.wfile, 64 * 1024)
            except (BrokenPipeError, ConnectionResetError):
                pass  # the client went away mid-body

        def serve(self) -> None:
            base = snapshot(root)
            path = urlsplit(self.path).path
            if (
                path == "/healthz"
            ):  # the process is up: a liveness probe, apart from any snapshot
                self.reply(200, "text/plain", b"ok\n")
                return
            if path == "/metrics":  # the build wrote it; none yet means not ready
                found = resolve(base, "/metrics")
                if found is None:
                    self.reply(503, "text/plain", b"no snapshot published yet\n")
                else:
                    self.reply(200, METRICS_TYPE, found.read_bytes())
                return
            real = resolve(base, self.path)
            if real is None:
                self.reply(404, "text/plain", b"not found\n")
                return
            tag = etag(base, real, hashes.table(base))
            if matches(self.headers.get("If-None-Match"), tag):
                self.send_response(304)
                self.send_header("ETag", tag)
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                return
            ctype = TYPES.get(real.suffix) or (
                mimetypes.guess_type(real.name)[0] or "application/octet-stream"
            )
            self.stream(real, ctype, tag)

        def do_GET(self) -> None:
            self.serve()

        def do_HEAD(self) -> None:
            self.serve()

        def log_message(self, *_: object) -> None:
            pass

    return H


def parser() -> argparse.ArgumentParser:
    """The command line, separate from main so a deployment manifest can be checked against it."""
    ap = argparse.ArgumentParser(
        prog="nemik-static",
        description="serve a published nemik snapshot as files (W502)",
    )
    ap.add_argument(
        "--root", type=Path, required=True, help="the publish root (or one build)"
    )
    ap.add_argument("--bind", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8750)
    return ap


def main(argv: list[str] | None = None) -> None:
    args = parser().parse_args(argv)
    ThreadingHTTPServer((args.bind, args.port), handler(args.root)).serve_forever()


if __name__ == "__main__":
    main()
