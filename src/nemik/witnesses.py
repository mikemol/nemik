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
from datetime import UTC, datetime
from pathlib import Path

# input.<observer>["<key>"], the only fact shape a witness may reference.
_REF = re.compile(r'input\.(\w+)\["([^"]+)"\]')


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


# `input.now` (RFC 3339, UTC) is always present, so a time witness needs no observer:
# `time.parse_rfc3339_ns(input.now) >= time.parse_rfc3339_ns("2026-10-01T00:00:00Z")`.
OBSERVERS = {"pid": _pid, "file": _file, "git_ref": _git_ref}


def facts(query: str, now: datetime | None = None) -> tuple[dict, list[str]]:
    """(input document, unobservable refs) for exactly the facts `query` references."""
    doc: dict = {"now": (now or datetime.now(UTC)).isoformat()}
    missing = []
    for obs, key in _REF.findall(query):
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
        ["opa", "eval", "--format", "json", "--stdin-input", query],
        input=json.dumps(doc), capture_output=True, text=True, check=False,
    )
    if out.returncode != 0:
        return "undefined"
    result = json.loads(out.stdout).get("result") or []
    return "true" if result and all(e["value"] is not False for e in result[0]["expressions"]) else "false"


def witness(query: str, now: datetime | None = None) -> tuple[str, dict, list[str]]:
    doc, missing = facts(query, now)
    return evaluate(query, doc, missing), doc, missing
