# The wait weight's measured basis (nemik:W753)

W712 turns the wait weight on in the ranking. Its `per_tick` is meant to come from how long cards
actually wait, not from a typed number. W485 measured where working time goes, not waits, so this
is the measurement W712 was missing.

## The command

```
nemik-history nemik --waits --from 2026-10-12
```

For each repo and status it prints how many stints in that status finished, and their median and
ninetieth-percentile length in days. A stint runs from a card's status event to its next status
event (`climate.waits_of`, built on the events of nemik:W744). A stint still running has no length
yet and is left out, so a card that has waited a long time and not yet moved does not count: the
numbers are a floor on the waits, biased low by exactly the longest ones.

## The reading, nemik alone, 2026-10-12 to 2026-10-19

| status  | stints | median  | p90     |
|---------|--------|---------|---------|
| ready   | 57     | 0.04 d  | 0.56 d  |
| blocked | 22     | 0.04 d  | 0.12 d  |
| working | 74     | 0.02 d  | 0.04 d  |

## What it can and cannot say

- The history is commit-grain (docs/weather-questions.md): a stint is as long as the gap between
  two commits that saw it, so stints shorter than the gap between queue commits read as 0 or as
  the gap. A median of 0.04 d (about an hour) is at that floor; it is not evidence that cards wait
  an hour.
- The p90 of `ready` (0.56 d, about 13 hours) is above the floor and is the figure to use. It is
  about 27 loop ticks of 30 minutes.
- One repo, one week. The fleet reading below is the follow-up (nemik:W756).

## The fleet reading, 2026-10-12 to 2026-10-20 (nemik:W756)

`nemik-history --all --waits --from 2026-10-12`, run under `systemd-run --user` with a 4 G memory
cap and no swap (peak 342 M, 7 s). Median and p90 of finished stints, in days:

| repo                 | ready n | ready med | ready p90 | blocked n | blocked p90 |
|----------------------|---------|-----------|-----------|-----------|-------------|
| amr-skills           | 27      | 0.10      | 0.78      | 11        | 0.86        |
| el-openglo           | 81      | 0.26      | 2.87      | 9         | 1.17        |
| gcalculus            | 10      | 0.02      | 3.45      | 3         | 3.42        |
| life                 | 4       | 5.73      | 5.73      | 1         | 5.73        |
| linux-sources        | 18      | 0.08      | 0.19      | 6         | 3.19        |
| luthen-observability | 160     | 2.09      | 4.18      | 55        | 2.01        |
| mtools               | 114     | 0.09      | 1.08      | 34        | 1.87        |
| nemik                | 57      | 0.04      | 0.56      | 22        | 0.12        |
| summit               | 22      | 0.17      | 0.48      | 6         | 0.76        |

The repos differ by an order of magnitude (a ready card waits a median 0.04 d in nemik and 2.09 d
in luthen-observability), so one fleet number hides the spread. The median of the nine repos' ready
p90s is 1.08 d (about 52 loop ticks of 30 minutes); the interquartile range of those p90s is
0.56 to 3.45 d. W712 should either take 1.08 d as a single `per_tick` basis and say that it is the
median repo's p90, or carry a per-repo value; a pooled p90 over all stints needs the stints
themselves, which `--waits` does not print yet.
