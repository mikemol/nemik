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
- One repo, one week. The fleet reading (`--all`) is the follow-up before a nonzero `per_tick`
  ships; W712 should take its quantile from that and say which.
