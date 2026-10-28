# The typed document boundary

nemik reads JSON and TOML documents it does not write (a queue, the published pieces, the pace and
round files) and most of its mypy debt is the `Any` those reads leave behind: of the 4,372 findings
counted when this was written, about 4,000 were "expression has type Any". A parameter-bundle
tool (gabion, `docs/gabion-audit.md`) cannot see these shapes. The user's ruling (nemik's own
session, line 138830, uuid 31bdf58f-b473-4b05-a566-1295693efbe7, answering "cannot see the json
and tomllib document shapes": "This is what ABC and JSON SCHEMA are for", W1176): declare each
document's shape once, as a JSON Schema, and read it through an abstract base class. This note
records the plan and what is built.

The ABC half is a plain interface class in `src/nemik`, not the `abc` module: the pinned Codon has
neither `abc` nor `typing.Protocol` (probed), every `src/nemik` module is in the Codon census, and a
module that fails it adds a baseline entry. The real `abc.ABC` check lives in `tests/`, outside the
census.

## The plan

1. **One schema per document**, under `src/nemik/data/*.schema.json`. The precedent is
   `run-row.schema.json` (W556), validated by `runrows.py`.
2. **One abstract base class per document**, with typed accessors. `nemik.tracker`'s flat `Tree`
   stays the Codon-safe core; the ABC is what consumers type against.
3. **The schema is the source** for both the runtime check (jsonschema, in a boundary module that is
   not under the Codon census, since jsonschema does not compile there) and the accessor list, so a
   field is declared once and a test fails when the two drift.
4. **Migrate consumers one document at a time**, each stack paying down mypy as the `json.loads`
   sites go.

## Built: the queue's waypoint (the first slice)

`src/nemik/data/waypoint.schema.json` declares a waypoint twice, measured against the fleet:

- **The core** (the root): `symbol`, `title`, `status`, `enables`, `blocked_on`, the five keys that
  every card in every fleet queue fixture carries. `blocked_kind` is typed but not required, because
  three cards in older queues lack it; the schema found that, the first draft required it.
- **`$defs/full`**: the 14 keys the writer's own state file stamps on every card. All 1,183 cards of
  this repo's queue pass it with no refusal (checked when it was written, not by a test: a bazel
  test cannot read the live queue).
- The other keys the writer sets on some cards (`completed`, `manifest`, `size_class`, `weight`,
  `warrants`, `vector`, `witness`, `deploys`, `withheld`, `attachments`, `landed_at`, ...) are declared
  with their types, so a declared key with the wrong type is refused. A key the schema does not
  declare is allowed.

`tests/test_waypoint_schema.py` checks the schema is valid, that every card of the 19 fleet queue
fixtures passes the core, that a clean full card passes both forms, that each missing core key is
named, that the export's six keys fail the full form, and that a wrong status, `blocked_kind`,
count or symbol is refused.

## Built: the waypoint accessors

`src/nemik/waypoint.py` is the second half. `Waypoint` is the interface consumers type against (a
plain class; each method raises `NotImplementedError`); `TreeWaypoint` reads one card from
`nemik.tracker`'s flat `Tree` by handle; `waypoints_of(text)` reads a whole queue document. A member
that is absent or null reads as `""`, `[]` or `0`. It compiles under the pinned Codon (probed in the
stage tree), so it adds no baseline entry. `FIELDS` names the core keys the accessors cover.

`tests/test_waypoint.py` holds it to the data and the schema: every card of the 19 fixture queues
reads the same through the accessors as through `json.loads` (the oracle); the accessor list is a
subset of the schema's declared keys and covers its required ones (step 3, the drift test); a real
`abc.ABC` with one abstract method per field is concrete under `TreeWaypoint`, so a field the
accessors lose or the schema gains shows there; and the plain interface refuses to answer.

## Built: the weights TOML schema (the TOML half, first document)

`src/nemik/data/rank-weights.schema.json` declares `rank-weights.toml` as read through `tomllib`:
every table the file declares is required and typed, and a key the schema does not name is allowed.
`tests/test_rank_weights_schema.py` (6 tests) validates the shipped file, names each missing table,
refuses a wrong type or value, and states the two rules a schema cannot (a repo is in one burn-down
tier; a health pair is `[amber, red]` with red no lower). Writing it found a misreading: the file's
`weight = "flow"` follows `[order]`, so TOML scopes it to that table, though the comment above it
reads as if it were top-level; the schema puts it under `order`, as `rank.py` reads it. Owed for
this document: an accessor (`health.py` first), then `bands.toml`, `connectors.toml`, `workflows.toml`.

## Not built yet

- Any consumer migrated (step 4). The first would be `wake.py`, whose bare `dict` annotations
  cascade into most of its 245 mypy findings; retyping them as `dict[str, object]` alone raised 30
  new findings, because callers index the dicts as if their values were typed (probed and
  reverted), which is the work an accessor does once.
- Schemas for the other documents: the ledger, `graph.json`, `wake.json`, the pace and round files,
  the landing file, the published pieces, and the weights and bands TOML.
