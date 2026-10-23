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

## Trial 2: the service rate counts only cards that stood in line (nemik:W832), kept

The rates trial 1 used were large (mtools 37 a day, luthen-observability 43, nemik 36) because the
count included every card minted and closed within the hour: sweeps and auto-minted repin cards that
never stood in the line. A repo that closes forty of those a day does not clear forty cards of its
queue. `climate.finish_rates` now counts only cards that waited more than `SERVICE_FLOOR_DAYS` (one
day, the shortest horizon). The same two issues, regenerated:

| Floor on the wait counted | +1d Brier | Skill over climatology |
|---|---|---|
| none (trial 1) | 0.036 | -0.51 |
| 1 hour | 0.031 | -0.32 |
| 6 hours | 0.026 | -0.09 |
| one day (kept) | 0.0245 | -0.02 |

(The regenerated trial 1 scores 0.036 here against 0.058 above because this run measured the rate
over the days since 2026-10-12, not since the first event seen; the order of the rows is the same.)
Skill rose from -1.45 to -0.02: the forecast now scores the same as saying the base rate for every
card. That is in-sample, on 538 cards and two issues, and the floor was chosen on them. The test
that matters is the issue of 2026-10-22, which matures on 2026-10-23: it was issued before either
trial, so it is regenerated with both and scored out of sample. Until then the forecast is known to
be no worse than climatology, and not yet known to be better.

## Out of sample, first attempt (2026-10-23)

Scoring the stored shingle (`nemik-history --all --score ~/.cache/nemik/shingle.tsv`) gives +1d n
1626, Brier 0.204 against climatology 0.021, skill -8.69; the 0.94 bin (n 318) happened 0.01 of the
time. That number is the old model's, not the new one's: the shingle stores each row as it was
issued, so the issues of 2026-10-20 to 22 stay what the old model said, and `--forecast` only issues
now. Regenerating the 2026-10-22 issue with trials 1 and 2, as planned above, is not possible without
an as-of mode that replays the queue at a past date; there is none. So the honest out-of-sample test
is forward: an issue with both trials was appended on 2026-10-23 (1623 rows, same `--from
2026-10-12`), and its +1d horizon matures on 2026-10-24. Score again after that, and compare its
skill with -8.69 (the old model) and 0 (climatology). Only if it is not yet above zero is the next
feature (gate duration, blocker depth) worth trying.
