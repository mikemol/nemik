# nemik data model

This document describes what nemik implements as of this commit and what remains design.
Namespaces:

| Prefix | IRI |
|---|---|
| `oslc_cm` | `http://open-services.net/ns/cm#` |
| `prov` | `http://www.w3.org/ns/prov#` |
| `dcterms` | `http://purl.org/dc/terms/` |
| `nemik` | `https://github.com/mikemol/nemik/ns#` (extension vocabulary, `src/nemik/data/nemik.ttl`) |

Node IRIs are `urn:nemik:<repo>` for a workstream, `urn:nemik:<repo>/W<n>` for a waypoint,
`urn:nemik:<repo>/ledger/<line>` for a ledger activity, and `urn:nemik:operator` for the operator.

## Layers

| Layer | Standard | Status |
|---|---|---|
| Each workstream's published state | OSLC CM 3.0 | implemented |
| Derivation: what an activity used, what caused a waypoint | W3C PROV | implemented |
| Rules a queue must satisfy | SHACL | implemented (`nemik-check`) |
| Effort over time | Prometheus text, scraped into VictoriaMetrics | implemented (`nemik-metrics`, `/metrics`) |
| Change feed per workstream | OSLC Tracked Resource Set | designed, not implemented |
| Messages between workstreams | ForgeFed / ActivityStreams | designed, not implemented |

## Waypoint: a queued item

| Queue field (mtools) | RDF |
|---|---|
| waypoint | `a oslc_cm:ChangeRequest` |
| repo | `nemik:workstream <urn:nemik:repo>` |
| `symbol` | `nemik:symbol "W<n>"` |
| `title` | `dcterms:title` |
| `status` ready / working / blocked / done | `oslc_cm:state nemik:Ready`, `nemik:Working`, `nemik:Blocked`, `nemik:Done`: SKOS concepts in `nemik:WaypointStates`. Any other value is kept as a literal and flagged. |
| done | also `oslc_cm:closed true` |
| `enables` | `nemik:enables` a waypoint: local `W<n>`, or `repo:W<n>` in another workstream (mtools 9236d5e) |
| `blocked_on` (free text) | `nemik:blockedOn "text"`, plus `nemik:waitsFor` when unambiguous (see below) |
| `blocked_kind` | `nemik:blockedKind "agent" \| "human"` |
| `touches` | `nemik:touches "tag"` |
| `issued_at` | `dcterms:created` |
| `minted_during` (mtools 2e21902+) | `nemik:mintedDuring "tick" \| "interrupt"`, derived by mtools from the tick lock |
| `caused_by` (mtools 2e21902+) | `prov:wasInformedBy` a waypoint when the value is `W<n>` or `repo:W<n>`, otherwise a literal |
| residue entry | `a nemik:Dropped`, with the same symbol and title |

### Resolving `blocked_on`

`blocked_on` is free text. `adapter.resolve_blocker` reads only the shapes agents were measured
writing (2026-09-25), and leaves everything else as a literal:

| Written | Edge |
|---|---|
| `W<n>` | to that waypoint in the same workstream |
| `repo:W<n>` | to that waypoint in another workstream |
| `repo`, or a session name `repo-<2 hex>` | to that workstream |
| `operator`, `user`, `mikemol`, `human` | to `urn:nemik:operator` |

On first measurement, 52 of 79 values resolved.

### Cross-workstream blocks, from both sides

A block that names only another workstream (a repo or session) gives neither agent a symbol to
cite. `nemik.blocks` looks for a waypoint in the blocker's workstream that CLAIMS the block: one
that `nemik:enables` the blocked waypoint (`--enables <repo>:W<n>`) or was `caused_by` it. A
block written as `<repo>:W<n>` is claimed by that waypoint.

- An unclaimed block gets `nemik:unclaimedBlockOn` and a Warning from `UnclaimedBlockShape`.
- In the view, the block's edge ends at the claiming waypoint, or at a dashed "?" inside the
  blocker's box.
- The blocker's agent reads what is waiting on it with `nemik-inbound <repo>` or
  `GET /inbound/<repo>`. Each entry gives the blocked waypoint's citable `<repo>:W<n>` and the
  claiming waypoints, or none.
- `nemik_blocks_inbound{repo,claimed}` counts them.

To claim a block, the blocker adds or updates a waypoint with
`--enables <blocked-repo>:W<n>`, or mints it with `--caused-by <blocked-repo>:W<n>`. Both are
already legal in mtools, so claiming needs no new vocabulary.

## Ledger line: effort

Each line that `ledger.read` parses becomes one activity:

| Column | RDF |
|---|---|
| stamp | `prov:startedAtTime` (`xsd:dateTime`; mtools validates it from 2293751) |
| kind | `nemik:kind` (raw) and `nemik:effortClass` |
| symbol | `prov:used` the waypoint (local or `repo:W<n>`), unless the symbol is `--` |
| outcome, mechanism | `nemik:outcome`, `nemik:mechanism` |
| note | `rdfs:comment` |

`effortClass` comes from `adapter.KIND_CLASS`, a stated reading of observed use. Only `tick` has
an upstream definition.

| kind | class |
|---|---|
| `tick`, `arm` | forecast |
| `manual`, `msg`, `peer`, `op`, `main`, `swarm` | interrupt |
| anything else | unclassified |

Lines that `ledger.read` returns unparsed are counted (`nemik_ledger_unparsed`) and not
interpreted.

Prompts carry a second, independent effort signal from the hook spool:

| source | class |
|---|---|
| `tick`, `operator-tick` | forecast |
| `operator`, `peer` | interrupt |
| `subagent`, `background` | internal |

## Shapes

In `src/nemik/data/shapes.ttl`:

| Shape | Checks | Severity |
|---|---|---|
| `WaypointShape` | one workstream, one symbol matching `W<n>`, one title | Violation |
| `WaypointShape` | `enables` resolves to a waypoint or a residue entry | Violation |
| `WaypointShape` | state is one of the four | Warning |
| `WaypointShape` | `blockedKind` is agent or human | Warning |
| `BlockedShape` | a blocked waypoint has `blockedOn` and `blockedKind` | Warning |
| `EdgeIntoDroppedShape` | an `enables` edge into residue (stale) | Warning |
| `ListFieldShape` | a list field is stored as a bare string | Warning |

Validation runs once over the merged graph of every workstream, so a cross-workstream edge
resolves, and a finding is attributed to the workstream of its focus node. Only a Violation
fails `nemik-check`. Vocabulary divergence is reported to summit's floor rather
than enforced: `friction-the-queue-vocabulary-has-one-owner-and-six-dialects` and
`friction-a-lenient-reader-hides-a-writer-bug`.

## Designed, not implemented

- **ForgeFed between workstreams.** Each repo's agent is an Actor, `<repo>/inbox/` is its inbox,
  and summit is the hub. A waypoint is a Ticket, and `enables` is a TicketDependency (unverified
  as still current in the ForgeFed draft). A summit ask is an Offer of a Ticket, with Accept,
  Reject and Resolve. An interrupt is an incoming Activity that the waypoint's
  `prov:wasInformedBy` cites.
- **Tracked Resource Set.** The ledger is already append-only. Publishing it as a `trs:ChangeLog`
  per workstream would let other consumers sync incrementally.

## Known residue

- `effortClass` for ledger kinds is nemik's reading. It becomes definitional only if mtools
  closes the `kind` vocabulary.
- About 1,000 legacy ledger lines are unparsed and stay unclassified.
