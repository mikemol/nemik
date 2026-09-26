# Adopting a paths-forward queue that nemik reads

nemik surveys every repo under `~/github` that has a `.claude/paths-forward.json`
(or, on luthen's pod, the export layout at `<root>/<repo>/paths-forward.json`).
This page collects, in reading order, what a repo needs so its queue is well-formed
and its ledger is parseable. It doesn't replace any of the sources below; it's a map
of them.

## 1. Install the writer

The queue file has one writer: `mikemol-paths-forward`. Install it as your own
sha-pinned dependency, per mtools' `INSTALL.md`:

    uv add "mikemol-pathsforward @ git+https://github.com/mikemol/mtools.git@<sha>#subdirectory=pathsforward"
    PF=.venv/bin/mikemol-paths-forward

Until you've done that, mtools' own copy is a stopgap only
(`~/github/mtools/pathsforward/.venv/bin/mikemol-paths-forward`), and adopting the
package as your own dependency should itself be a waypoint. nemik's own
`nemik_pathsforward_adoption{repo,state}` metric reports `missing` until you have.

**Never** hand-edit `paths-forward.json` or its `.ledger`, and never append ledger
lines by any means other than `$PF --ledger`. Hand edits lose symbols and leave the
counter lagging; `--add` then refuses. Lines mtools' `ledger.read` can't parse are
counted (`nemik_ledger_unparsed`) and never interpreted — they don't retroactively
become valid once you start using `--ledger` for new lines, so leave old hand-appended
lines as they are.

## 2. The full behavior contract

Read the `paths-forward-loop` skill (`~/.claude/skills/paths-forward-loop/SKILL.md`).
It's the canonical description of:

- the state file's schema and the two-carrier (payload + file) design (§1);
- symbols as identities, never repurposed (§2);
- what "structural leverage" means when picking what to work next — collapse,
  unblock, or sweep (§3);
- claiming inbound blocks with `nemik-inbound` so another repo's wait on you is
  citable, and the exact `blocked_on` forms nemik resolves: `<repo>:W<n>`, a bare
  repo name, or `operator: decide|act <ask>` (§4.2, §4.4);
- the ledger line grammar (§6).

## 3. What nemik actually reads from your queue

- `nemik-check` runs SHACL shapes (`nemik/data/shapes.ttl`) over every merged queue.
  `nemik-check`'s exit code (0 conforms, 1 names the `VIOLATES` repos) and its
  `provenance:` lines are load-bearing for luthen's own witness (W81) — don't read
  its output format as incidental.
- `nemik-inbound [REPO]` lists what's waiting on `REPO` and which of your waypoints
  claims it (an `--enables` or a `--caused-by` edge naming the blocked waypoint). An
  unclaimed block prints `UNCLAIMED` — that literal column token is what other
  repos' tick loops read (paths-forward-loop §4.2), so it won't change even as the
  surrounding hint text does.
- `nemik-operator` sorts your blocks on the operator into `needs-you` / `answered` /
  `condition` / `unstated`. A bare `blocked_on: "operator"` or free text with no
  `decide`/`act` verb lands in `unstated`, which is the gap nemik's own W4 wrote
  letters to eight repos about.
- `ledger.read`'s `kind` classifies into `nemik_ledger_lines{repo,class,kind}`:
  `tick`/`arm` → forecast; `manual`/`msg`/`peer`/`op`/`main`/`swarm` → interrupt;
  anything else → unclassified (and still counted, not dropped).
- `minted_during` (`tick` | `interrupt`) is derived by mtools from whether the tick
  lock was held when the waypoint was added — you don't set it yourself.
- Cross-repo edges are always `<repo>:W<n>`, in `enables`, `caused_by`, or
  `blocked_on`, legal since mtools `9236d5e`.

## 4. Migrating an existing hand-rolled queue

If you already write your own paths-forward-shaped file with your own tooling:

1. Keep your existing ledger lines as-is; they won't parse retroactively, and the
   ledger is append-only. Route every new line through `$PF --ledger` from here on.
2. Compare your `blocked_on`/`enables` vocabulary against §4.4 above before writing
   a migration plan, rather than guessing at nemik's shapes from the SHACL file.
3. Check your result with `~/github/nemik/.venv/bin/nemik-check --root ~/github`
   and `nemik-metrics` (adoption state, ledger-unparsed count).

## 5. Known gaps in the writer (cite these, don't route around them)

- `--enables`, given with no symbols, now clears a waypoint's outbound edges
  (mtools `8a279a1`; matches `--blocked-on`'s existing shape).
- Still open: no create-from-empty mode (mtools:W42); `--` can't be passed as a
  ledger symbol (mtools:W43), so a sweep covering several waypoints in one ledger
  line has to name one of them as the symbol and the rest in the note.

## 6. Host-specific tooling note

If you're running on **luthen** rather than your own laptop: `~/github/cassian-observability`
there is a synced copy of the laptop's repo, and its readers (`scripts/collectors/series-history`,
`host/store-migration.tsv`) dial the laptop's metrics stores, not luthen's — they'll get
connection refused. On luthen, resolve stores by name through luthen-observability's own
`checks/endpoints_query.py` instead.
