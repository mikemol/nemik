# Which nemik-check rows encode demand, and does the rank already carry it

Asked by the operator (host 695f3e0a line 94798, uuid a9a6013d-f0dd-4832-8314-1e0e88f46759: "that's
precisely what salience supposed to communicate. And more effectively, at that."), resting on three
earlier rulings: line 62579 ("Demand is salience is demand"), line 52675 ("mechanically rise via the
salience mechanism, so that other sessions organically pick them up") and line 70556 ("salience was
supposed to prevent this from happening. Or at least cause prioritization.").

The rule the audit applies: a fact about waiting, staleness or debt belongs in the rank as salience, where
sessions already look and act. A check row is legitimate only as the explanation of a rank position, or
when it names a defect in the graph that stops demand flowing (a missing edge), which the rank cannot say
for itself.

## First measurement (luthen-observability, 2026-10-24, aging tier live in the tool)

Of 26 ready cards past the learned age bound (2.2 days), 15 held salience 0.0, 4 held 0.25 and 5 held 3 or
more; a card not past the bound held 83. Staleness is not demand: lifting the stale cards by age put
demand-less cards above demanding ones. The aging tier (W1005, W1001) was dropped on this. The remedy for a
stale card with nothing waiting on it is to close it, drop it, or link it to the demand it serves.

The card behind a grooming umbrella case (github:W37, finding F9) is different: luthen-observability:W1285
ranked first with salience 1677 for the cards behind it, so the rank already said it. What failed was its
size (121 cards to atomize), which W925's finding names. A separate languish Warning (W992, W1000) was
dropped as a parallel channel.

## The rows

| Row | Encodes | Does the rank carry it? | Disposition |
|---|---|---|---|
| Umbrella Info (W710): N blocked cards wait behind a card | demand behind a card | yes: the flow model gives the card the demand of the cards behind it | restate as the explanation of the rank position, or retire the row |
| Ready-neither (W489, raised to Warning by W1003): ready cards untouched past the bound | staleness, no demand | no, and it should not: staleness carries no demand | stays a cleanup signal; the count becomes a ratchet (W1002); remedy is close, drop or link |
| Blocked on another workstream and no waypoint there claims it (inbound UNCLAIMED) | a peer's demand with no edge to flow along | the flow carries peer weight once the edge exists; this row names the missing edge | legitimate: keep, it names a graph defect |
| Behind-without-paydown (W988) | gate-level demand: a repo behind its ratchet needs a paydown card | not yet: W989's lift is the carrier, waiting on the pace file (W993, W994) | carry as salience when the pace file exists; the row then explains the lift |
| Declared size large: atomize (W925-type) | a card too big to take | no | cleanup signal; the card's size is the fact |
| No working card while items are ready | a session idling | not demand | stays; it is about the session, not the card |
| More than N needs-you operator asks in a repo (W348) | the operator as bottleneck | the ask weight is already a demand source (rank-weights `operator`) | the row restates it; candidate to retire |

## Next

- Turn the umbrella Info and the operator-saturation row into explanations of rank positions (a rank line
  per card that names its demand source), or retire them.
- Carry the paydown requirement as salience once the pace file exists (W989's lift, W993).
- Decide whether the ready-neither Warning stays a Warning or becomes a count on the pace board only
  (W1002).

Not claimed: the table reads the rows by their messages and the rank by one repo's measurement; it did not
run every row against every repo.
