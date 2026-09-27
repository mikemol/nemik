# nemik

A read-only project-management view over many independent workstreams. Each workstream is a
repository with its own AI agent and its own work queue. nemik shows who is working on what, how
the work depends on other work, and how much effort goes to planned work versus interrupts, with
interrupts tracked in the same dependency graph as the planned work.

nemik builds on existing standards rather than inventing a tracker:

- **OSLC Change Management 3.0.** Each queued item is an `oslc_cm:ChangeRequest`.
- **W3C PROV.** Each ledger entry is a `prov:Activity` that used a waypoint. What caused a
  waypoint is `prov:wasInformedBy`.
- **SHACL.** The rules a queue must satisfy are SHACL shapes, checked by `nemik-check`.
- **Prometheus / OpenTelemetry-style metrics** for effort over time.

ForgeFed/ActivityPub is the intended model for the messages *between* workstreams: letters,
asks and interrupts as Activities. It is designed but not yet implemented; see
[docs/model.md](docs/model.md).

## Sources

nemik never parses queue files itself. It reads them through
[`mikemol-pathsforward`](https://github.com/mikemol/mtools/tree/main/pathsforward), the one owner
of the format:

| Source | Read through | Becomes |
|---|---|---|
| `<repo>/.claude/paths-forward.json` | `store.load` | waypoints, `enables` edges, blockers |
| `<repo>/.claude/paths-forward.ledger` | `ledger.read` | PROV activities, effort class |
| `~/.local/state/nemik/events.jsonl` | the global hook in `hooks/` | prompts by source |

## Commands

| Command | What it does |
|---|---|
| `nemik-check` | Validates every queue against `src/nemik/data/shapes.ttl`. Exits 1 on a `sh:Violation` (a dangling edge, a duplicated symbol, or an unreadable queue). Warnings, such as vocabulary divergence, are printed and do not fail. |
| `nemik-metrics` | Prints Prometheus text: waypoints by state, findings, prompts and ledger lines by effort class. |
| `nemik-inbound [repo]` | What in other workstreams is blocked on `repo`, each blocked waypoint as a citable `<repo>:W<n>`, and which of `repo`'s waypoints claims it, or `UNCLAIMED`. |
| `nemik-operator` | Blocks on the operator, sorted into needs-you, answered, condition and unstated, with duplicate asks grouped. |
| `nemik-wake` | The wake roster: each workstream something is waiting on, with whether it has a live session (asleep / idle / awake), what waits on it, and how many blocks need you. Liveness comes from luthen-observability's `loop_liveness`. |
| `nemik-rank repo` | Ready items by cross-repo downstream weight; `--check` exits 1 when the queue's next item is outweighed, `--json` feeds `mikemol-paths-forward --weights-from`. |
| `nemik-floor-asks` | Exits 1 when a `summit/floor/*.bib` ask's `waypoint` field names a missing or dropped waypoint. |
| `nemik-serve` | The web view: `/` (dependency graph), `/graph.json`, `/graph.ttl`, `/inbound/<repo>`, `/operator`, `/wake`, `/metrics`. |

The root defaults to `~/github` and can be set with `$NEMIK_ROOT` or `--root`. It accepts
`<root>/<repo>/.claude/paths-forward.*` or a flat export, `<root>/<repo>/paths-forward.*`.

```console
$ uv sync --no-editable   # a package, not the working tree; nemik warns otherwise (W94)
$ .venv/bin/nemik-check
$ .venv/bin/nemik-serve --port 8750
```

### Depending on nemik from another repo

nemik pins `mikemol-pathsforward` to its vendored wheel, and uv carries that pin into any project
that depends on nemik by path. A project that pins pathsforward itself will then fail to lock,
because uv refuses two sources for one package. The consumer's own pin should win, so declare it
as an override as well as a dependency (nemik:W51):

```toml
[project]
dependencies = ["nemik", "mikemol-pathsforward @ git+https://github.com/mikemol/mtools.git@<sha>#subdirectory=pathsforward"]

[tool.uv.sources]
nemik = { path = "../nemik" }

[tool.uv]
override-dependencies = ["mikemol-pathsforward @ git+https://github.com/mikemol/mtools.git@<sha>#subdirectory=pathsforward ; python_full_version >= '3.13'"]
```

Keep the marker if your project supports Python below 3.13. Overrides apply to every
Python version your project resolves for, and pathsforward itself requires 3.13 or later, so
without the marker the lock fails for the older versions (summit 3abbe17).

Checked with summit's pin, fc74848, which is older than nemik's: `uv lock` resolves, and
`nemik-check` and `nemik-floor-asks` both run.

## The event hook

`hooks/record_event.py` is meant to run as a global Claude Code hook on `UserPromptSubmit`,
`Stop` and `SessionStart`. For each event it appends one line to a local spool: the time,
session, cgroup scope, repo, event, and where a prompt came from (a scheduled tick, an
operator-typed tick, the operator, a peer session, a subagent, or a background notice). It never
stores prompt text, never uses the network, and always exits 0.

## Hosting

`Containerfile` builds the web view. Mount only the flat queue export read-only at `/export`,
not a whole source tree.
