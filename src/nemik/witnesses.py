# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
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

from mikemol.pathsforward.opa_eval import OpaUnavailableError, resolve

from nemik import edgeletters
from nemik.delivery import owed, stamp
from nemik.work import run_writer
from nemik.workrows import edges_of

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
    if (
        not sep
        or not re.fullmatch(r"[\w.-]+", repo)
        or repo in {".", ".."}
        or rev.startswith("-")
        or not (path / ".git").exists()
    ):
        return None
    out = subprocess.run(
        [
            "git",
            "-C",
            str(path),
            "rev-parse",
            "--verify",
            "--quiet",
            f"{rev}^{{commit}}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
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
    m = re.fullmatch(r"(\w+)(?:\{(.*)\})?", key)
    body = _get("NEMIK_VMALERT_URL", "/api/v1/alerts", {}) if m else None
    if m is None or body is None:
        return None
    want = dict(re.findall(r'(\w+)="([^"]*)"', m.group(2) or ""))
    states = [
        a["state"]
        for a in body["data"]["alerts"]
        if a["name"] == m.group(1)
        and all(a["labels"].get(k) == v for k, v in want.items())
    ]
    return {
        "state": "firing" if "firing" in states else "pending" if states else "inactive"
    }


def _promql(key: str) -> dict | None:
    """An instant query: its sample values, and whether the result is empty."""
    body = _get("NEMIK_VM_URL", "/api/v1/query", {"query": key})
    if body is None:
        return None
    values = [float(r["value"][1]) for r in body["data"]["result"]]
    return {"values": values, "empty": not values}


def _apply(key: str) -> dict | None:
    """A row id of luthen's host-apply export: whether its live file matches the declared source.

    nemik:W233. `applied` is true only for a fresh, well-formed export that carries an applied
    mark for the row; a row the export does not hold, or an export that cannot be read, is
    undefined (never counted as done).
    """
    from nemik.check import default_root
    from nemik.hostapply import fact, load

    try:
        export = load(default_root())
    except ValueError:
        return None
    seen = fact(export, key, datetime.now(UTC).isoformat()) if export else None
    # nemik:W259: a row the exporter could not read is unknown, not "not yet": undefined.
    return None if seen is None or seen["unobservable"] else seen


# `input.now` (RFC 3339, UTC) is always present, so a time witness needs no observer:
# `time.parse_rfc3339_ns(input.now) >= time.parse_rfc3339_ns("2026-10-01T00:00:00Z")`.
OBSERVERS = {
    "pid": _pid,
    "file": _file,
    "git_ref": _git_ref,
    "alert": _alert,
    "promql": _promql,
    "apply": _apply,
}


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


def opa_json(query: str, doc: object, data: list[str]) -> object:
    """Run `opa eval` once, the one place nemik starts the pinned opa (nemik:W646).

    Args:
        query: The Rego query.
        doc: The input document, given on stdin.
        data: Policy files to load with --data.

    Returns:
        opa's parsed JSON answer, or None when opa is unavailable or exits non-zero.

    """
    # nemik:W535: the one pinned-opa resolution, shared with pathsforward; NEMIK_OPA names it.
    named = {"OPA_BIN": os.environ.get("NEMIK_OPA") or os.environ.get("OPA_BIN", "")}
    try:
        opa = resolve({k: v for k, v in named.items() if v})
    except OpaUnavailableError:
        return None
    argv = [opa, "eval", "--format", "json"]
    for path in data:
        argv += ["--data", path]
    out = subprocess.run(
        [*argv, "--stdin-input", query],
        input=json.dumps(doc),
        capture_output=True,
        text=True,
        check=False,
    )
    return None if out.returncode != 0 else json.loads(out.stdout)


def evaluate(query: str, doc: dict, missing: list[str]) -> str:
    """'true' | 'false' | 'undefined'."""
    if missing:
        return "undefined"
    parsed = opa_json(query, doc, [])
    if not isinstance(parsed, dict):
        return "undefined"
    result = parsed.get("result") or []
    return (
        "true"
        if result and all(e["value"] is not False for e in result[0]["expressions"])
        else "false"
    )


def is_rego(query: str, lang: str = "") -> bool:
    """Whether `query` is a Rego witness.

    nemik:W539: a waypoint declares its language (`--witness-lang rego|promql`, the card's
    `witness_lang`), and that is read first. Only a witness without the field is sniffed: it is
    Rego when it reads `input` (an observer fact, or `input.now`), since a PromQL expression cannot
    name `input.` (a metric name has no dot), and anything else is PromQL.
    """
    if lang in {"rego", "promql"}:
        return lang == "rego"
    return re.search(r"\binput\.", query) is not None


def witness(
    query: str, now: datetime | None = None, lang: str = ""
) -> tuple[str, dict, list[str]]:
    """'true' | 'false' | 'undefined' for a waypoint's witness, with the facts that decided it.

    nemik:W501: a witness that is a bare PromQL expression holds while its instant query returns a
    sample, the PromQL meaning of a comparison (`x > y` returns the series only while it is true) and
    what `--wait` has always done with one; luthen-observability:W1054 stores its executor-load witness
    that way, and no Rego wrapper (and its escaped quotes) needs writing by hand.
    """
    if not is_rego(query, lang):
        stamp = (now or datetime.now(UTC)).isoformat()
        fact = _promql(query)
        if fact is None:
            return "undefined", {"now": stamp}, [f'promql["{query}"]']
        verdict = "false" if fact["empty"] else "true"
        return verdict, {"now": stamp, "promql": {query: fact}}, []
    doc, missing = facts(query, now)
    return evaluate(query, doc, missing), doc, missing


def open_witnesses(root: Path) -> list[tuple[str, Path, str, str, str]]:
    """(repo, queue path, symbol, query, lang) for every witnessed waypoint not yet done.

    `lang` is the card's declared witness_lang, or "" when it declares none (nemik:W539).
    """
    from nemik.check import QUEUE, workstream_files

    out: list[tuple[str, Path, str, str, str]] = []
    for repo, path in workstream_files(root, QUEUE):
        try:
            data: dict[str, list[dict[str, str]]] = json.loads(
                path.read_text(encoding="utf-8")
            )
        except (OSError, ValueError):
            continue
        for w in data.get("waypoints", []):
            if w.get("witness") and w.get("status") != "done":
                lang = w.get("witness_lang") or ""
                out.append((repo, path, w["symbol"], w["witness"], lang))
    return out


def queue_texts(root: Path) -> dict[str, str]:
    """Read every workstream's queue under a fleet root (nemik:W851).

    Args:
        root: The fleet root, holding each repo's directory.

    Returns:
        {repo: the text of its paths-forward.json}; an unreadable queue is left out.

    """
    from nemik.check import QUEUE, workstream_files

    out: dict[str, str] = {}
    for other, path in workstream_files(root, QUEUE):
        try:
            out[other] = path.read_text(encoding="utf-8")
        except OSError:
            continue
    return out


def waiters(root: Path, repo: str, sym: str) -> dict[str, list[str]]:
    """{repo: [W<n>, ...]} for every open waypoint blocked on repo:sym (or on sym within repo)."""
    out: dict[str, list[str]] = {}
    for other, text in queue_texts(root).items():
        try:
            data = json.loads(text)
        except ValueError:
            continue
        for w in data.get("waypoints", []):
            on = w.get("blocked_on") or []
            if w.get("status") == "blocked" and (
                f"{repo}:{sym}" in on or (other == repo and sym in on)
            ):
                out.setdefault(other, []).append(w["symbol"])
    return out


def wake(root: Path, repo: str, sym: str, query: str, now: str) -> list[Path]:
    """nemik:W61, W851: a letter in each waiting repo's inbox (the nemik:W4 channel). A letter
    reaches a dormant repo at no token cost until someone wakes it. A live loop reads it on its
    next tick, where --prune-landed (local) or the named foreign blocker shows the work is now free.

    Within the card's own repo the waiting cards get one letter that carries the witness query.
    Across repos every edge of the card (blocked_on, caused_by, enables; workrows.edges_of) gets
    its own letter through the delivery record (deliver, W850), so a rerun, or a letter its reader
    deleted, sends nothing again. Waiters were the only edge kind this once saw.
    """
    written: list[Path] = []
    syms = waiters(root, repo, sym).get(repo, [])
    inbox = root / repo / "inbox"
    if syms and inbox.is_dir():
        letter = inbox / f"{now[:10]}-nemik-witness-{repo}-{sym}.md"
        letter.write_text(
            f"# nemik → {repo}: {repo}:{sym} is done (its witness held)\n\n"
            f"`nemik-witnesses --apply` observed at {now}:\n\n    {query}\n\n"
            f"Waiting on it here: {', '.join(syms)}. Each is blocked on `{sym}`, which is now done.\n"
            "`mikemol-paths-forward --prune-landed --root <fleet root>` prunes it.\n",
            encoding="utf-8",
        )
        written.append(letter)
    written += deliver(root, queue_texts(root), (repo, sym), "done", now[:10])
    return written


# nemik:W850: the delivery record (nemik.delivery) is a dotfile in the fleet root, so no tool
# mistakes it for a repo directory and a letter its reader deleted is still recorded as sent.
RECORD = ".nemik-delivered"


def deliver(
    root: Path, queues: dict[str, str], card: tuple[str, str], outcome: str, day: str
) -> list[Path]:
    """nemik:W850 (W547): one inbox letter per cross-repo edge of a done or dropped card, once.

    Walks the card's edges (workrows.edges_of), keeps those the record does not show as sent
    (delivery.owed), writes a letter into the other repo's inbox for each, and stamps the record
    only for a letter it wrote. A repo with no inbox is skipped and stays owed, so a later run
    delivers it once the inbox exists.

    Args:
        root: The fleet root, holding each repo's directory.
        queues: Each repo's name and the text of its paths-forward.json.
        card: The finished card as (repo, symbol), the symbol `W<n>`.
        outcome: `done` or `dropped`.
        day: Today's date, `YYYY-MM-DD`.

    Returns:
        The letters written this run.

    """
    repo, sym = card
    record = root / RECORD
    try:
        seen = record.read_text(encoding="utf-8")
    except OSError:
        seen = ""
    written: list[Path] = []
    for edge in owed(seen, repo, sym, edges_of(queues, repo, sym)):
        inbox = root / edge[1] / "inbox"
        if not inbox.is_dir():
            continue
        letter = inbox / edgeletters.name(day, repo, sym, edge)
        letter.write_text(
            edgeletters.text(repo, sym, edge, outcome, day), encoding="utf-8"
        )
        with record.open("a", encoding="utf-8") as fh:
            fh.write(stamp(repo, sym, edge, day))
        written.append(letter)
    return written


def main(argv: list[str] | None = None) -> None:
    import argparse

    from nemik.check import default_root

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--root",
        type=Path,
        default=default_root(),
        help="~/github, or the export layout root",
    )
    ap.add_argument(
        "--apply",
        action="store_true",
        help="mark waypoints whose witness holds as done",
    )
    ap.add_argument(
        "--wait",
        metavar="QUERY",
        help="block until QUERY holds (a PromQL expression, or a Rego query over the observers): "
        "exit 0 held, 1 timed out, 2 cannot be evaluated (nemik:W258)",
    )
    ap.add_argument(
        "--lang",
        choices=["rego", "promql"],
        default="",
        help="with --wait: the query's language, instead of guessing it from its text (nemik:W539)",
    )
    ap.add_argument(
        "--timeout",
        default="12h",
        help="with --wait: give up after this long (90s, 30m, 12h, 1d)",
    )
    ap.add_argument(
        "--every",
        default="30s",
        help="with --wait: poll this often (90s, 30m, 12h, 1d)",
    )
    args = ap.parse_args(argv)
    if args.wait:
        from nemik.witwait import poller, seconds, wait

        try:
            limit, step = seconds(args.timeout), seconds(args.every)
        except ValueError as err:
            print(f"nemik-witnesses: {err}", file=sys.stderr)
            raise SystemExit(2) from err
        code, line = wait(poller(args.wait, args.lang), limit, step)
        print(line)
        raise SystemExit(code)
    # nemik:W97: the queue's one writer is the installed mikemol-paths-forward, beside this interpreter
    # in the same .venv (host, or bazel's //:.venv). Missing is a failure, reported, never a skip.
    pf = Path(sys.executable).parent / "mikemol-paths-forward"
    for repo, path, sym, query, lang in open_witnesses(args.root):
        verdict, doc, missing = witness(query, lang=lang)
        note = f"  cannot observe {','.join(missing)}" if missing else ""
        # nemik:W539: a witness with no declared language is sniffed; say so, so the count can fall to 0
        sniffed = "  language sniffed (no witness_lang)" if not lang else ""
        print(f"WITNESS {repo}:{sym} {verdict}{note}{sniffed}")
        if args.apply and verdict == "true":
            observed = {k: v for k, v in doc.items() if k != "now"}
            if not pf.exists():
                print(
                    f"APPLY FAILED {repo}:{sym} ({pf} is not installed)",
                    file=sys.stderr,
                )
                continue
            code, said = run_writer(
                [
                    "--state",
                    str(path),
                    "--update",
                    sym,
                    "--status",
                    "done",
                    "--evidence-append",
                    f"witness held at {doc['now']}: {json.dumps(observed, sort_keys=True)}",
                ]
            )
            if code:
                # the writer's own refusal line, so a loop that fails every five minutes says why
                print(
                    f"APPLY FAILED {repo}:{sym} (mikemol-paths-forward exit {code}): "
                    f"{(said.splitlines() or ['no output'])[-1]}",
                    file=sys.stderr,
                )
                continue
            for letter in wake(args.root, repo, sym, query, doc["now"]):
                print(f"WOKE {letter}")
