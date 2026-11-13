# Weather, incidents and follow-up: the A/W/R card model

Filed 2026-11-13 at github-cb's request (their letter of that date). The model is a graph and ranking
model over every queue, and its semantics are read and enforced in nemik (nemik:W2166).

| File | What it is |
|---|---|
| [outline.md](outline.md) | The host's outline, skeleton only (github-cb, 2026-11-13) |
| [architecture-review.md](architecture-review.md) | An external architecture review of the outline, supplied by the operator; it surveyed nemik main at e496230 |
| [second-review.pdf](second-review.pdf) | A second external review (a PDF, 2026-11-13), a critique and framework cross-reference of the outline and of the first review |

Owners: the writer side is mtools:W2410, the producer is luthen-observability:W2609, the reader, rank,
witness and operator view are nemik:W2166.

## Resolved: the A-card is the occurrence, weather is a role (the review's 8.1)

The review held that an A-card (an occurrence) and the existing weather card (blocked work) are
different resources, while an earlier operator ruling folded weather into A. The operator has since
ruled, superseding that (relayed by github-cb on 2026-11-13; not checked here against the operator's
transcript):

- A<n> is the OCCURRENCE.
- Weather is a ROLE: a W-card blocked on `<repo>:A<n>`.
- Weather detection keys off that edge.
- A-cards stay out of ready-work ranking.
- The witness closes the A (the occurrence), which unblocks the waiting W-cards.

The outline predates this ruling: where it says "A for weather" (its 4.1 and 4.2), read it through
the ruling above. The hold on the A semantics in nemik:W2166 is lifted.

## Resolved: declaration, and proactive umbrellas

Two more operator rulings, relayed by github-cb on 2026-11-13 (not checked here against the operator's
transcript):

- Declaration (the review's declaration conflict): every A is declared internally on mint, with no
  declaration gate. The operator is an escalation point only, reached through the existing needs-you
  asks (`operator: decide|act`), never by routine alert paging. nemik-operator shows A-cards only when
  one carries an operator ask or a commander is past span of control.
- Proactive umbrellas (the second review's last open question): a forecast may mint a condition
  umbrella W with no prior A, and later As attach to it. Rank treats a proactive umbrella like any
  follow-up umbrella.

The outline's declaration gate (its 7) and its one-umbrella-per-declared-incident rule (its 4.3) are
read through these rulings.

## Resolved: a ratchet impasse is weather only across repos

Another operator ruling, relayed by github-cb on 2026-11-13 (not checked here against the operator's
transcript). A repo painted into a corner by ratchets is weather:

- Repo-local: no incident. It is the ratchet's intended forcing function, and it justifies design or
  heavy work.
- Cross-repo: the repo is truly stuck because another repo has not finished a paydown asked of it.
  That is an incident: an A-card for the occurrence, the stuck work blocked on it, and the upstream
  paydown card cited.

Detection, still to design (nemik:W2177): the forecast's explicit impasse (nemik:W1665) combined with
the blocked_on graph. An impasse whose clearing cards all belong to another repo mints or proposes
the A-card.

## Points of the second review that are nemik's

Relayed by github-cb; each is the review's claim, not yet checked against this tree. Design only:
nothing new is built yet for these points.

- Follow-up precedence comes from nemik-rank's band and floor rules plus `--weights-from`, with cycle
  and inversion tests; it is not weightless topology (the first review assumed topology).
- `prov:wasInformedBy` is used loosely for "what caused a waypoint": typed causal predicates mean
  cleaning that up.
- A-cards carry compact immutable evidence digests at each transition, so an R audit survives
  telemetry retention.
- Area Command (several concurrent incidents contending for one resource) is distinct from Unified
  Command.
- Proactive umbrella Ws from forecasts without any outage: resolved above.

## Findings of the first review that are nemik's

- 8.4, retro ingestion: no module under src/nemik reads real retro records into nemik:Retro; the
  shapes run on fixtures only (confirmed in this tree; carried by nemik:W982).
- 8.4, the G4 doc and shape disagreed: docs/retro-audit.md said G4 has no shape, and
  src/nemik/data/shapes.ttl has one (W983). Fixed in docs/retro-audit.md (nemik:W2169).
- 8.2, 8.3, 9.3 and 16: A kept out of ready-work ranking, typed edges, rank-inversion and no-cycle
  checks: recorded on nemik:W2166 (the hold on them is lifted with the ruling above).
