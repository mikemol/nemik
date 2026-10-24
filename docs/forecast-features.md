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

## Out of sample, second attempt (2026-10-24): no worse than climatology, not shown better

The issue appended on 2026-10-23 (stamped 12:41Z, the only one made with trials 1 and 2) has matured
at +1d. Scored alone (its rows copied to a scratch file, since `--score` has no per-issue mode): n
541, Brier 0.021, against persistence 0.022 (skill +0.05) and climatology 0.022 (skill +0.03). By
bin, 540 cards were given about 0.00 and 2 in 100 of them finished; one card was given 0.27 and
finished. The whole stored shingle scores differently (n 2167, skill -6.30 against persistence and
-6.47 against climatology) because it still holds the old model's issues; the 0.94 bin (n 318) is
unchanged, which is the sign that those rows are old.

What this shows, and what it does not. It shows the forecast is now close to the base rate and the
out-of-sample number agrees with the in-sample one (-0.02 for trial 2): the 0.99-for-a-busy-repo error
is gone. It does not show skill. About eleven cards finished among the 541, so a Brier difference of
0.001 is well inside the noise a single issue has, and 540 of 541 forecasts being the same number
means the model says "no" for nearly every card, which is climatology under another name. Brier on a
rare event cannot separate that from a forecast that picks out which cards finish; for that the
score needs the ranking of the finishers (did the cards that finished get higher chances than the
ones that did not), which `--score` does not print.

So the bar W933 set stands unmet: a predicted start time is shown only for a forecast with verified
skill over climatology, and this one has none shown. Trial 3 (gate duration, blocker depth) is
worth trying, judged on a score that can see discrimination, not on Brier alone.

## The measure, and what it says of the second attempt (2026-10-24)

`nemik-history --score` now prints a discrimination per lead (W965): the chance that a card which
finished was given a higher forecast than one which did not, ties counting half, so 0.5 is a forecast
that ranks nothing and 1.0 one that puts every finisher first. On the 2026-10-23 issue alone (+1d, n
541, about eleven finishers) it is 0.66. With so few finishers the standard error is about 0.09
(Hanley and McNeil's estimate), so 0.66 is about 1.8 standard errors above 0.5: suggestive, not
shown. Nearly all of it comes from the one card given 0.27 that finished. One issue cannot settle it;
the score of each matured issue is kept here beside its standard error.

## Trial 3, designed before it is built: status, not gate duration (nemik:W966)

The plan above named gate duration. Reading `forecastshingle` and `history.forecast_rows` first shows
a better first feature. A card's chance is its lead-time chance scaled by `min(1, rate * horizon /
(ahead + 1))`, where `ahead` is how many cards of its repo are older than it, and the oldest-first
order counts **every open card, blocked ones included**. Two things in that are wrong about how work
is taken. A blocked card does not take a slot in the line: nobody can work it until what it waits for
lands. And the line is not worked oldest first but in rank order among the cards that can start. So a
repo with forty old blocked cards makes every younger ready card look forty places back, and a blocked
card at the front of the line looks about to be reached.

Gate duration would only change the finishing rate, which `finish_rates` already measures from what
the repo really closed, gate included; it adds nothing the rate does not already carry.

So trial 3 changes two things and scores them on discrimination: `ahead` counts only the cards that can
start (ready or working) older than this one; and a blocked card's chance is capped by the share of
blocked stints that ended within the horizon (`climate.waits_of`, which already measures them), since
that, not the repo's rate, is what a blocked card waits on. Trial 4 (blocker depth, W967) refines the
second: how long a blocked card waits depends on how deep its chain of blockers is.

What is needed that is not there yet: a card's status at the moment the forecast is issued
(`open_ages` gives ages, not states; the events hold the transitions, so it can be rebuilt as
`levels_at` does for counts), and an as-of replay to score the feature on issues already matured,
which does not exist. Without a replay the test is forward again: issue with the feature, wait a day,
score on discrimination beside the 2026-10-23 issue's 0.66 and 0.09.
