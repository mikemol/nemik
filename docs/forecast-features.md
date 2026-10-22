# Forecast features: one at a time, kept only if skill rises (nemik:W749)

The forecast (`nemik-history --forecast`, nemik:W747) gives each open card the chance it is done
within +1, +3 and +7 days. `nemik-history --score FILE --from DATE` scores a stored shingle against
what happened: the Brier score per lead, against persistence and against climatology, with the
reliability bins. A feature is added one at a time and kept only if the verified skill over
climatology rises. The scores below are over the cards of every repo, `--from 2026-10-12`.

## The base model

A card's chance is the share of its repo's past lead times (mint to first done) that ended within
the horizon, among those longer than its age. It knows how long finished cards took; it does not
know how far back in the line this card stands.

| Shingle | Lead | n | Brier | Climatology | Skill over climatology |
|---|---|---|---|---|---|
| issued 2026-10-20 and 2026-10-21 | +1d | 538 | 0.244 | 0.024 | -9.3 |

The reliability bins say where it fails: the 0.99 bin held 112 cards and one finished; the 0.30 bin
held 89 and none did. The 0.99 bin is old cards of busy repos (66 mtools, 35 luthen-observability,
aged 2.7 to 7 days): a repo that finishes much will not finish this card within a day if forty
others stand ahead of it.

## Trial 1: the card's place in its repo's line (nemik:W831), kept

The repo finishes `rate` cards a day over the history seen (`climate.finish_rates`). Taking the line
oldest first, a card with `ahead` cards before it is reached within a horizon with the chance
`min(1, rate * horizon / (ahead + 1))`, and its lead-time chance is multiplied by that
(`forecastshingle.in_line`). The same two issues, regenerated for their moments:

| Variant | +1d Brier | Skill over climatology |
|---|---|---|
| base model | 0.244 | -9.3 |
| lead-time chance times the reach (kept) | 0.058 | -1.45 |
| the smaller of the two | 0.063 | -1.69 |
| the reach alone | 0.427 | -17.1 |

Skill rose from -9.3 to -1.45, so it stays. It is still below climatology (a forecast that says the
base rate for every card scores 0.024): the remaining error is the 118 fresh cards given 0.33, none
of which finished within a day. Next trial (W832): how many cards the repo finishes a day against
how many stand ahead, as a cap on the rate itself.
