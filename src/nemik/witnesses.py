"""FFI waypoints (nemik:W58 rev 3, W60): a declared Rego witness over facts from a closed set of observers.

Nothing in a queue is executed. A waypoint's `witness` is a Rego query over `input`. nemik's
observers (read-only, fixed here) gather exactly the facts the query references, as
`input.<observer>["<key>"]`, and `opa eval` decides:

- true: the witness holds, so the waypoint is done, with the facts as evidence;
- false: not yet;
- undefined: a referenced fact could not be observed. This is reported and never counted as done.

OPA returns no result for both false and undefined, so undefined comes from the observers: a
key they could not resolve.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

# input.<observer>["<key>"], the only fact shape a witness may reference.
# The key is a Rego string literal, so it may carry escaped quotes (a promql label matcher).
_REF = re.compile(r'input\.(\w+)\["((?:[^"\\]|\\.)*)"\]')


def _pid(key: str) -> dict | None:
    """`localhost/<pid>[@<starttime>]`. Only the local host is observable for now (design, open question)."""
    host, _, rest = key.partition("/")
    if host != "localhost":
        return None
    pid, _, start = rest.partition("@")
    stat = Path(f"/proc/{pid}/stat")
    try:
        fields = stat.read_text().rsplit(")", 1)[1].split()
    except (FileNotFoundError, ProcessLookupError):
        return {"alive": False}
    except (OSError, IndexError, ValueError):
        return None
    # starttime (field 22) guards against PID reuse: a different process with this PID is not ours.
    return {"alive": not start or fields[19] == start, "start": fields[19]}


def _file(key: str) -> dict | None:
    return {"exists": os.path.exists(key)}


def _git_ref(key: str) -> dict | None:
    """`<repo>@<ref>` in the local clone under the nemik root: whether it resolves, and to what."""
    from nemik.check import default_root

    repo, sep, rev = key.partition("@")
    path = default_root() / repo
    # Queue data, not trusted: a plain repo name, and a ref git cannot read as an option.
    if not sep or not re.fullmatch(r"[\w.-]+", repo) or repo in {".", ".."} or rev.startswith("-") \
            or not (path / ".git").exists():
        return None
    out = subprocess.run(["git", "-C", str(path), "rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}"],
                         capture_output=True, text=True, check=False)
    return {"exists": out.returncode == 0, "sha": out.stdout.strip()}


def _get(env: str, path: str, params: dict) -> dict | None:
    """GET <$env><path> as JSON; None when the endpoint is unset or unreachable (cannot observe).

    The address comes from the environment, not from here: on luthen,
    `luthen-observability/checks/endpoints_query --side host vmalert-http|vmsingle-http`.
    """
    import urllib.parse
    import urllib.request

    base = os.environ.get(env)
    if not base:
        return None
    url = f"{base.rstrip('/')}{path}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            body = json.load(r)
    except (OSError, ValueError):
        return None
    return body if body.get("status") == "success" else None


def _alert(key: str) -> dict | None:
    """`<alertname>[{label="v",...}]`: firing | pending | inactive (absent from vmalert's list)."""
    m = re.fullmatch(r'(\w+)(?:\{(.*)\})?', key)
    body = _get("NEMIK_VMALERT_URL", "/api/v1/alerts", {}) if m else None
    if body is None:
        return None
    want = dict(re.findall(r'(\w+)="([^"]*)"', m.group(2) or ""))
    states = [a["state"] for a in body["data"]["alerts"]
              if a["name"] == m.group(1) and all(a["labels"].get(k) == v for k, v in want.items())]
    return {"state": "firing" if "firing" in states else "pending" if states else "inactive"}


def _promql(key: str) -> dict | None:
    """An instant query: its sample values, and whether the result is empty."""
    body = _get("NEMIK_VM_URL", "/api/v1/query", {"query": key})
    if body is None:
        return None
    values = [float(r["value"][1]) for r in body["data"]["result"]]
    return {"values": values, "empty": not values}


# `input.now` (RFC 3339, UTC) is always present, so a time witness needs no observer:
# `time.parse_rfc3339_ns(input.now) >= time.parse_rfc3339_ns("2026-10-01T00:00:00Z")`.
OBSERVERS = {"pid": _pid, "file": _file, "git_ref": _git_ref, "alert": _alert, "promql": _promql}


def facts(query: str, now: datetime | None = None) -> tuple[dict, list[str]]:
    """(input document, unobservable refs) for exactly the facts `query` references."""
    doc: dict = {"now": (now or datetime.now(UTC)).isoformat()}
    missing = []
    for obs, raw in _REF.findall(query):
        key = json.loads(f'"{raw}"')  # Rego and JSON share string escapes
        fn = OBSERVERS.get(obs)
        fact = fn(key) if fn else None
        if fact is None:
            missing.append(f'{obs}["{key}"]')
        else:
            doc.setdefault(obs, {})[key] = fact
    return doc, missing


def evaluate(query: str, doc: dict, missing: list[str]) -> str:
    """'true' | 'false' | 'undefined'."""
    if missing:
        return "undefined"
    out = subprocess.run(
        [os.environ.get("NEMIK_OPA", "opa"), "eval", "--format", "json", "--stdin-input", query],
        input=json.dumps(doc), capture_output=True, text=True, check=False,
    )
    if out.returncode != 0:
        return "undefined"
    result = json.loads(out.stdout).get("result") or []
    return "true" if result and all(e["value"] is not False for e in result[0]["expressions"]) else "false"


def witness(query: str, now: datetime | None = None) -> tuple[str, dict, list[str]]:
    doc, missing = facts(query, now)
    return evaluate(query, doc, missing), doc, missing


def open_witnesses(root: Path) -> list[tuple[str, Path, str, str]]:
    """(repo, queue path, symbol, query) for every witnessed waypoint not yet done, fleet-wide."""
    from nemik.check import QUEUE, workstream_files

    out = []
    for repo, path in workstream_files(root, QUEUE):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for w in data.get("waypoints", []):
            if w.get("witness") and w.get("status") != "done":
                out.append((repo, path, w["symbol"], w["witness"]))
    return out


def waiters(root: Path, repo: str, sym: str) -> dict[str, list[str]]:
    """{repo: [W<n>, ...]} for every open waypoint blocked on repo:sym (or on sym within repo)."""
    from nemik.check import QUEUE, workstream_files

    out: dict[str, list[str]] = {}
    for other, path in workstream_files(root, QUEUE):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for w in data.get("waypoints", []):
            on = w.get("blocked_on") or []
            if w.get("status") == "blocked" and (f"{repo}:{sym}" in on or (other == repo and sym in on)):
                out.setdefault(other, []).append(w["symbol"])
    return out


def wake(root: Path, repo: str, sym: str, query: str, now: str) -> list[Path]:
    """nemik:W61: a letter in each waiting repo's inbox (the nemik:W4 channel). A letter reaches a
    dormant repo at no token cost until someone wakes it. A live loop reads it on its next tick,
    where --bump-blocked (local) or the named foreign blocker shows the work is now free."""
    written = []
    for other, syms in sorted(waiters(root, repo, sym).items()):
        inbox = root / other / "inbox"
        if not inbox.is_dir():
            continue
        letter = inbox / f"{now[:10]}-nemik-witness-{repo}-{sym}.md"
        cite = sym if other == repo else f"{repo}:{sym}"
        letter.write_text(
            f"# nemik → {other}: {repo}:{sym} is done (its witness held)\n\n"
            f"`nemik-witnesses --apply` observed at {now}:\n\n    {query}\n\n"
            f"Waiting on it here: {', '.join(syms)}. Each is blocked on `{cite}`, which is now done.\n"
            + ("A tick's `--bump-blocked` prunes it.\n" if other == repo else
               f"Lift the block: `mikemol-paths-forward --state .claude/paths-forward.json --update <W> ...`.\n"),
            encoding="utf-8",
        )
        written.append(letter)
    return written


def main(argv: list[str] | None = None) -> None:
    import argparse
    import sys

    from nemik.check import default_root

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=default_root(), help="~/github, or the export layout root")
    ap.add_argument("--apply", action="store_true", help="mark waypoints whose witness holds as done")
    args = ap.parse_args(argv)
    # nemik:W97: the queue's one writer is the installed mikemol-paths-forward, beside this interpreter
    # in the same .venv (host, or bazel's //:.venv). Missing is a failure, reported, never a skip.
    pf = Path(sys.executable).parent / "mikemol-paths-forward"
    for repo, path, sym, query in open_witnesses(args.root):
        verdict, doc, missing = witness(query)
        note = f"  cannot observe {','.join(missing)}" if missing else ""
        print(f"WITNESS {repo}:{sym} {verdict}{note}")
        if args.apply and verdict == "true":
            observed = {k: v for k, v in doc.items() if k != "now"}
            if not pf.exists():
                print(f"APPLY FAILED {repo}:{sym} ({pf} is not installed)", file=sys.stderr)
                continue
            rc = subprocess.run([str(pf), "--state", str(path), "--update", sym, "--status", "done",
                                 "--evidence-append",
                                 f"witness held at {doc['now']}: {json.dumps(observed, sort_keys=True)}"],
                                capture_output=True, text=True).returncode
            if rc:
                print(f"APPLY FAILED {repo}:{sym} (mikemol-paths-forward exit {rc})", file=sys.stderr)
                continue
            for letter in wake(args.root, repo, sym, query, doc["now"]):
                print(f"WOKE {letter}")
