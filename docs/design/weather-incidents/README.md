# Weather, incidents and follow-up: the A/W/R card model

Filed 2026-11-13 at github-cb's request (their letter of that date). The model is a graph and ranking
model over every queue, and its semantics are read and enforced in nemik (nemik:W2166).

| File | What it is |
|---|---|
| [outline.md](outline.md) | The host's outline, skeleton only (github-cb, 2026-11-13) |
| [architecture-review.md](architecture-review.md) | An external architecture review of the outline, supplied by the operator; it surveyed nemik main at e496230 |

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

## Findings of the review that are nemik's

- 8.4, retro ingestion: no module under src/nemik reads real retro records into nemik:Retro; the
  shapes run on fixtures only (nemik:W2170).
- 8.4, the G4 doc and shape disagree: docs/retro-audit.md says G4 has no shape, and
  src/nemik/data/shapes.ttl has one (nemik:W2169).
- 8.2, 8.3, 9.3 and 16: A kept out of ready-work ranking, typed edges, rank-inversion and no-cycle
  checks: recorded on nemik:W2166 (the hold on them is lifted with the ruling above).
