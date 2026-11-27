# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W502: serve a published snapshot as files, with no model, no graph and no rdflib.

Operator ruling 2026-10-15 (W500): the pod serves prebuilt snapshots and does no graph work, so
request count and graph churn scale independently. A request is a file read; a rebuild happens in a
short-lived process elsewhere and is published under ROOT/current (a symlink flipped atomically) or
simply as ROOT itself. Pieces are validated by the sha256 hashes.json already lists (nemik:W414), so
a client revalidating with If-None-Match costs a header exchange, not a body.

stdlib only on purpose: a test holds this module to never importing rdflib.
"""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from nemik.flags import command_line, parse_flags
from nemik.say import warn
from nemik.tomlview import table

CHUNK = 64 * 1024  # the streaming read size

# nemik:W1179: a fixed suffix table, not the host's mimetypes module (a Codon wall, and its answer
# also depends on the machine's /etc/mime.types). A suffix not listed is served as octet-stream.
TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript",
    ".json": "application/json",
    ".jsonld": "application/ld+json",
    ".ttl": "text/turtle",
    ".css": "text/css",
    ".wasm": "application/wasm",
    ".svg": "image/svg+xml",
    ".ics": "text/calendar",
    ".md": "text/markdown",
    ".txt": "text/plain",
}
UNKNOWN_TYPE = "application/octet-stream"
METRICS_TYPE = "text/plain; version=0.0.4"


def snapshot(root: Path) -> Path:
    """Pick the directory to serve: ROOT/current when a publisher flips that link, else ROOT.

    Returns:
        ROOT/current when that is a directory, else ROOT.

    """
    live = root / "current"
    return live if live.is_dir() else root


def resolve(base: Path, target: str) -> Path | None:
    """Find the file a URL path names under `base`, or None when it names nothing or escapes it.

    Returns:
        The resolved file, or None when the path names nothing, escapes `base` or is not a file.

    """
    parts = [p for p in unquote(urlsplit(target).path).split("/") if p]
    if any(p in {".", ".."} or "\\" in p or "\x00" in p for p in parts):
        return None
    path = base.joinpath(*parts)
    if path.is_dir() and (path / "index.html").exists():
        path /= "index.html"
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
        """Start with no table read and nothing seen."""
        self._seen: tuple[Path, int] | None = None
        self._table: dict[str, str] = {}

    def table(self, base: Path) -> dict[str, str]:
        """Give the snapshot's published hashes, rereading hashes.json only when its file moved.

        Args:
            base: the snapshot directory that holds hashes.json.

        Returns:
            Path to sha256 hex, or an empty table when the file is missing or unreadable.

        """
        path = base.resolve() / "hashes.json"
        try:
            stamp = (path, path.stat().st_mtime_ns)
            if stamp != self._seen:
                loaded: object = json.loads(path.read_text())
                self._table = {str(k): str(v) for k, v in table(loaded).items()}
                self._seen = stamp
        except (OSError, ValueError):
            self._table, self._seen = {}, None
        return self._table


def etag(base: Path, real: Path, table: dict[str, str]) -> str:
    """Give a file's validator: its sha256 when hashes.json lists it, else size and mtime.

    Returns:
        A quoted sha256 when `table` lists the file, else a weak validator of its mtime and size.

    """
    rel = real.relative_to(base.resolve()).as_posix()
    if digest := table.get(rel):
        return f'"{digest}"'
    stat = real.stat()
    return f'W/"{stat.st_mtime_ns:x}-{stat.st_size:x}"'


def matches(header: str | None, tag: str) -> bool:
    """Whether an If-None-Match header covers `tag`.

    Returns:
        True when the header lists `tag` (strong or weak form) or `*`; False for an absent header.

    """
    if not header:
        return False
    wanted = [t.strip() for t in header.split(",")]
    return "*" in wanted or tag in wanted or tag.removeprefix("W/") in wanted


BACKLOG = 128  # above a browser's six parallel connects; socketserver's default is 5 (nemik:W846)


class PageServer(ThreadingHTTPServer):
    """A ThreadingHTTPServer whose listen backlog outlasts a browser's parallel connects."""

    request_queue_size = BACKLOG


class _Writer(BaseHTTPRequestHandler):
    """The static handler's writers: a whole reply, a file's headers and a file's body."""

    def reply(self, code: int, ctype: str, body: bytes, tag: str | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        if tag:
            self.send_header("ETag", tag)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def head_of(self, size: int, ctype: str, tag: str) -> None:
        """Send a 200 for a file of `size` bytes: its type, no caching and its ETag."""
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(size))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("ETag", tag)
        self.end_headers()

    def send(self, real: Path, ctype: str, tag: str) -> None:
        """Send a file's head and, but for HEAD, its body in 64 KiB chunks."""
        with real.open("rb") as f:
            self.head_of(os.fstat(f.fileno()).st_size, ctype, tag)
            if self.command != "HEAD":
                # nemik:W1938: shutil is a Codon wall; the copy is a read and write loop
                chunk = f.read(CHUNK)
                while chunk:
                    self.wfile.write(chunk)
                    chunk = f.read(CHUNK)

    def stream(self, real: Path, ctype: str, tag: str) -> None:
        """Stream a file in 64 KiB chunks: memory does not grow with its size or other reads."""
        try:
            self.send(real, ctype, tag)
        except (BrokenPipeError, ConnectionResetError):
            return  # the client went away mid-body


def handler(root: Path) -> type[BaseHTTPRequestHandler]:
    """Build the static server's request handler class over one publish root.

    Each request resolves its path in the current snapshot, answers 304 when the ETag matches,
    and otherwise streams the file. /healthz answers apart from any snapshot, and /metrics
    answers 503 until a build has written one.

    Args:
        root: the publish root, or one build.

    Returns:
        The handler class, for ThreadingHTTPServer to instantiate per request.

    """
    hashes = Hashes()

    class H(_Writer):
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
            self.stream(real, TYPES.get(real.suffix, UNKNOWN_TYPE), tag)

        def do_GET(self) -> None:
            self.serve()

        def do_HEAD(self) -> None:
            self.serve()

        def log_message(self, *_: object) -> None:
            pass

    return H


VALUED = ["--root", "--bind", "--port"]
DEFAULT_BIND = "127.0.0.1"
DEFAULT_PORT = 8750
BAD_USAGE = 2  # argparse's exit status for a command line it could not read
USAGE = "usage: nemik-static --root ROOT [--bind BIND] [--port PORT]"


class Options:
    """The parsed command line of nemik-static (nemik:W1187, W1936: read with nemik.flags)."""

    root: Path
    bind: str
    port: int
    errors: list[str]

    def __init__(self, root: Path, bind: str, port: int, errors: list[str]) -> None:
        """Hold the three options and what was wrong with the command line, if anything."""
        self.root = root
        self.bind = bind
        self.port = port
        self.errors = errors


def read_options(argv: list[str] | None = None) -> Options:
    """Read the command line, apart from main so a deployment manifest can be checked against it.

    nemik:W1936: argparse is a Codon wall, so the three flags are read with nemik.flags. A missing
    --root, an unrecognized word and a port that is not a whole number are named in `errors`, as
    argparse refused them; main prints them and exits 2.

    Args:
        argv: the command line, or None for sys.argv.

    Returns:
        The options: --root, --bind (default 127.0.0.1), --port (default 8750), and the errors.

    """
    words = command_line() if argv is None else argv
    flags = parse_flags(words, VALUED, [])
    errors = list(flags.errors)
    errors.extend(f"unrecognized arguments: {word}" for word in flags.rest)
    root = flags.first("--root", "")
    if not root:
        errors.append("the following arguments are required: --root")
    port = DEFAULT_PORT
    given = flags.first("--port", "")
    if given:
        try:
            port = int(given)
        except ValueError:
            errors.append(f"argument --port: invalid int value: {given!r}")
    return Options(Path(root), flags.first("--bind", DEFAULT_BIND), port, errors)


def main(argv: list[str] | None = None) -> None:
    """Serve a published snapshot as files until the process is stopped.

    Args:
        argv: the command line, or None for sys.argv.

    Raises:
        SystemExit: 2 when the command line could not be read.

    """
    args = read_options(argv)
    if args.errors:
        warn(USAGE)
        warn("nemik-static: error: " + "; ".join(args.errors))
        raise SystemExit(BAD_USAGE)
    PageServer((args.bind, args.port), handler(args.root)).serve_forever()


if __name__ == "__main__":
    main()
