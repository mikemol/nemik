# Specs survey (R1, 2026-09-25)

Legend: **V** = verified from the URL given in this session; **U** = unverified (memory or secondary source; check before relying on it).

## 1. OSLC

| Claim | Status |
|---|---|
| CM 3.0 is an OASIS Standard, 26 May 2021; ns `http://open-services.net/ns/cm#` | V https://docs.oasis-open-projects.org/oslc-op/cm/v3.0/os/change-mgt-vocab.html |
| `oslc_cm:ChangeRequest`, subclasses Defect, Enhancement, Task, ReviewTask | V (same) |
| Links: `tracksRequirement`, `affectsPlanItem`, `parent`, `relatedChangeRequest` (+ test/changeset links) | V (same) |
| **No dependsOn/blocks relation in CM 3.0.** Only `parent`/`relatedChangeRequest`, and neither is typed as "blocks". | V by absence in the fetched vocab summary; the full-text check is still U |
| State: booleans `closed`, `inProgress`, `fixed`, `approved`, `reviewed`, `verified`; `oslc_cm:state` with standard enumerations extensible via `skos:narrower` | V (same) |
| TRS 3.0 ns `http://open-services.net/ns/core/trs#`; classes TrackedResourceSet, Base, ChangeLog, Creation, Modification, Deletion; props `trs:base`, `trs:changeLog`, `trs:change`, `trs:changed`, `trs:order`, `trs:previous`, `trs:cutoffEvent` | V https://oslc-op.github.io/oslc-specs/specs/trs/tracked-resource-set.html |
| TRS 3.0 has OASIS Standard status | U (the page is labelled "Part 1: Specification") |
| Automation 2.1 vocab ns `http://open-services.net/ns/auto#` (prefix `oslc_auto`; the page shows `oslc_am`) | V https://oslc-op.github.io/oslc-specs/specs/auto/automation-vocab.html |
| Auto classes AutomationPlan/Request/Result; props `executesAutomationPlan`, `producedByAutomationRequest`, `reportsOnAutomationPlan`, `state`, `verdict`, `contribution`; states `new/queued/inProgress/canceling/canceled/complete`; verdicts `unavailable/passed/warning/failed/error` | U (the fetch returned only prose; recalled from Auto 2.0) |
| Automation 3.0 exists as a draft | U |
| Estimation & Measurement (EMS 1.0) exists only on the archive wiki; ns `http://open-services.net/ns/ems/metric#` for metrics; `ems:Measure`, `ems:Service`. **Dormant**: not taken forward to OASIS OSLC-OP | V (archive) https://archive.open-services.net/uploads/wiki/ems_metric.html; the dormancy judgement is U |
| ResourceShape to SHACL: **no official mapping.** Core 3.0 Part 6 only says domains "may use ... W3C SHACL or JSONSchema" in addition to or instead of shapes | V https://oslc-op.github.io/oslc-specs/specs/core/resource-shape.html |
| OSLC Core 3.0 is an OASIS Standard (2021) | U |

Recommendation: write the taskboard shapes directly in SHACL (pyshacl) and skip ResourceShapes. Publishing a ResourceShape would be a derived output we would have to write ourselves. No converter was found.

## 2. ForgeFed

| Claim | Status |
|---|---|
| The spec is under construction; the snapshot is dated 2025-06-18 | V https://forgefed.org/spec/ |
| ns `https://forgefed.org/ns` | V (same) |
| Actors: Repository, TicketTracker, PatchTracker, Project, Team, Organization, created through Factory actors. All have inbox/outbox (ActivityPub) | V (same) |
| Ticket open: Offer{object: Ticket, target: tracker}, then Accept{object: Offer, result: ticket URI} or Reject | V (same) |
| Close: Resolve{object: ticket}, then Accept | V (same) |
| Ticket props `isResolved`, `resolvedBy`, `resolved` | V (same) |
| Access control through Grant with roles visit/report/triage/write/admin | V (same) |
| `TicketDependency` class plus `dependsOn`/`dependants` props: the current spec's section 8.2.7 references dependencies, but the fetch could not confirm that TicketDependency is a current term. It may be legacy | **U** |
| Vervis is the reference implementation, pre-alpha | V https://codeberg.org/ForgeFed/Vervis (via search) |
| Forgejo federation is experimental; star federation shipped in 2025; issues and PRs are not yet federated | V (search) https://forgejo.org/faq/ , https://codeberg.org/forgejo/discussions/issues/208; the v14/v15 detail is a secondary source, U |

## 3. Beads (steveyegge/beads)

| Claim | Status |
|---|---|
| Storage is now Dolt (embedded or server), with hash IDs `bd-xxxx` | V https://github.com/steveyegge/beads |
| DependencyType includes **`discovered-from`** (DepDiscoveredFrom), plus blocks, parent-child, conditional-blocks, waits-for, related, replies-to, relates-to, duplicates, supersedes, authored-by, assigned-to, approved-by, attests, tracks, until, caused-by, validates, delegated-from | V https://raw.githubusercontent.com/steveyegge/beads/main/internal/types/types.go |
| Status: open, in_progress, blocked, deferred, closed, pinned, hooked | V (same) |
| Issue fields include EstimatedMinutes, StartedAt/ClosedAt/CloseReason/ClosedBySession, Lease*, AwaitType/AwaitID (gates), EventKind/Actor/Target/Payload, SourceRepo | V (same) |

Beads' `waits-for`/gates, `caused-by`, `discovered-from` and `delegated-from` cover the ground where OSLC CM has nothing. Use them as vocabulary inspiration for the taskboard extension namespace (`nemik:` (was `tb:`)).

## 4. Python tooling

| Claim | Status |
|---|---|
| cslab/pyoslc: Flask server SDK on rdflib, 22 stars, BSD-3. It is a provider framework, not a consumer. Last commit date not obtained | V https://github.com/cslab/pyoslc (the date is U) |
| No maintained Python OSLC consumer library was found (oslc-client on PyPI is old) | U |
| No ResourceShape-to-SHACL converter in any language was found | V by search absence (weak) |
| ActivityPub Python: `bovine`, `fedify` (TS, not Python), `activitypub` (PyPI) | U (not checked this session) |

Conclusion: rdflib + pyshacl plus our own ~100-line namespace module is the right size. No OSLC library is needed for a read-only publisher.

## 5. Prior art (OSLC with ActivityPub, or with AI agents)
None found: a web search for "OSLC ActivityPub / AI agents / LLM agent" returned nothing (absence only; weak). The agent protocols in the literature are MCP, A2A, ANP and ACP (arXiv 2603.22862), and none of them uses OSLC or ForgeFed. The closest domain prior art is Beads, which is agent-oriented but not linked data.

## 6. Mapping table

Prefixes: `oslc_cm:` CM 3.0, `oslc_auto:` Auto, `trs:`, `ff:` ForgeFed, `as:` ActivityStreams, `prov:`, `dcterms:`, `ems:`, `otel` (span attributes), **`nemik:` (was `tb:`) = taskboard extension (gap)**.

### Waypoint (one waypoint = one `oslc_cm:ChangeRequest` and one `ff:Ticket`, same IRI `<repo>/wp/W<n>`)

| Field | Mapping | Gap? |
|---|---|---|
| symbol | `dcterms:identifier` "W7"; `oslc:shortTitle` | no |
| status=ready | `oslc_cm:state tb:Ready` (skos:narrower of CM's standard state); `oslc_cm:inProgress false`; `oslc_cm:closed false` | the state value is `nemik:` (was `tb:`) |
| status=working | `oslc_cm:inProgress true`; `oslc_cm:state tb:Working` | the value is `nemik:` (was `tb:`) |
| status=blocked | `oslc_cm:state tb:Blocked`. CM has no blocked flag | **gap** |
| status=done | `oslc_cm:closed true`; `ff:isResolved true`; `ff:resolved` = the done-stamp's time | no |
| enables (W_a enables W_b) | `tb:enables`, with inverse `tb:dependsOn`. Align with `ff:dependsOn` if confirmed (U). CM `relatedChangeRequest` is too weak | **gap** |
| blocked_on | `tb:blockedOn` → waypoint, Actor, or `foaf:Person` (operator) | **gap** |
| blocked_kind agent\|human | derived from the rdf:type of the blocked_on object (`as:Application`/`ff:Repository` vs `as:Person`). Also emit `tb:blockedKind` for convenience | partial gap |
| touches | `tb:touches` → file/resource IRIs. `prov:used` for the realized form once done | gap |
| armed_at | on the loop, not the waypoint: `oslc_auto:AutomationPlan` (the loop) with `tb:armedAt` xsd:dateTime; `prov:startedAtTime` of the loop Activity | gap (Auto has no arm time) |
| residue | `tb:residue` (literal or node). Retained-but-rejected material; nothing like it exists in any of these specs | **gap** |
| minted_at / caused-by (A1) | `prov:generatedAtTime`; `prov:wasDerivedFrom` / `prov:wasInformedBy` → the letter/Activity | no |
| repo | `oslc:serviceProvider` and `ff:context`/`as:attributedTo` → repo Actor | no |

### Ledger line (`<stamp> <kind> <symbol> <outcome> <mechanism> "note" evidence`)

| Column | Mapping | Gap? |
|---|---|---|
| (line) | `trs:Modification` (or `trs:Creation` when the symbol is first minted) in the repo's `trs:ChangeLog`, `trs:changed` → waypoint. Also a `prov:Activity` | no |
| stamp | `trs:order` (monotone: the line number or epoch). `prov:endedAtTime` / `as:published` | no |
| kind=tick | `oslc_auto:AutomationRequest` + `AutomationResult` (`oslc_auto:producedByAutomationRequest`, `executesAutomationPlan` → loop plan) | no |
| kind=manual / msg / peer | an `as:Activity` received in the inbox (interrupt). `tb:kind` keeps the raw drifted value | the raw kind is `nemik:` (was `tb:`) |
| symbol | `trs:changed` / `oslc_auto:contribution` → the waypoint IRI | no |
| outcome (verb) | `oslc_auto:verdict` (passed/failed/…) for ticks; for status transitions, `tb:outcome` with values done/blocked/… | partial gap |
| mechanism | `prov:wasAssociatedWith` → `prov:SoftwareAgent` (loop/hook/cli); `tb:mechanism` literal | partial gap |
| note | `dcterms:description` / `as:summary` | no |
| evidence | `prov:used` / `oslc_auto:contribution` → commit/URL IRIs | no |
| effort | OTel span `taskboard.tick` (attributes repo, symbol) → `ems:Measure` (dormant spec; use `tb:effortSeconds` + a QUDT unit instead) | gap (EMS is dormant) |

### Minimum `nemik:` (was `tb:`) namespace
`tb:Ready tb:Working tb:Blocked tb:Done` (as skos:narrower of oslc_cm states), `tb:enables`/`tb:dependsOn`, `tb:blockedOn`, `tb:blockedKind`, `tb:touches`, `tb:residue`, `tb:armedAt`, `tb:kind`, `tb:outcome`, `tb:mechanism`, `tb:effortSeconds`. Declare `tb:dependsOn owl:equivalentProperty ff:dependsOn` only after the ForgeFed term is verified.

## Next
- ⟐S1 Verify the ForgeFed dependency terms from https://forgefed.org/ns (the raw vocab file).
- ⟐S2 Verify the Automation state/verdict individuals from the shapes file in oslc-op/oslc-specs on GitHub.
- ⟐S3 Draft `tb.ttl` + SHACL shapes for Waypoint/LedgerEvent, and test them against `mikemol-pathsforward --payload` output.
