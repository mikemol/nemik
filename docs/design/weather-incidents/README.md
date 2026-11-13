# Weather, incidents and follow-up: the A/W/R card model

Filed 2026-11-13 at github-cb's request (their letter of that date). The model is a graph and ranking
model over every queue, and its semantics are read and enforced in nemik (nemik:W2166).

| File | What it is |
|---|---|
| [outline.md](outline.md) | The host's outline, skeleton only (github-cb, 2026-11-13) |
| [architecture-review.md](architecture-review.md) | An external architecture review of the outline, supplied by the operator; it surveyed nemik main at e496230 |

Owners: the writer side is mtools:W2410, the producer is luthen-observability:W2609, the reader, rank,
witness and operator view are nemik:W2166.

## Open, waiting on the operator

The review holds that an A-card (an occurrence) and the existing weather card (blocked work) are
different resources. The operator's ruling folded weather into A. This is NOT resolved here: the A
semantics are held until the operator rules. The namespace-table read in nemik:W2166 is unaffected.

## Findings of the review that are nemik's

- 8.4, retro ingestion: no module under src/nemik reads real retro records into nemik:Retro; the
  shapes run on fixtures only (nemik:W2170).
- 8.4, the G4 doc and shape disagree: docs/retro-audit.md says G4 has no shape, and
  src/nemik/data/shapes.ttl has one (nemik:W2169).
- 8.2, 8.3, 9.3 and 16: A kept out of ready-work ranking, typed edges, rank-inversion and no-cycle
  checks: recorded on nemik:W2166 and held with the A semantics.
