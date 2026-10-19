# Where working time goes, and how long the leaves wait (nemik:W485)

Read 2026-10-19 from `nemik-metrics --family nemik_working_ticks --family nemik_open_leaves
--family nemik_open_leaf_age_seconds` over the fleet root. This is the report W485 owes before
W486's design (age as an edge capacity); it measures, it does not propose.

## What is counted

- **A tick** is a ledger line of kind `tick` that names a card the queue still holds
  (`workrows.working_rows`).
- **Kind**, exclusive and in this order (`workrows.tick_kinds`): *directed* (the card's `caused_by`
  is not a card of the queue: a peer or the operator asked for it), else *leaf* (nothing waits on
  it), else *interior* (it unblocks something).
- **Open leaf**: an open card nothing waits on (`workrows.open_leaf_stamps`); its age runs from
  `issued_at`, median and oldest.

## The reading, for the five repos with the most ticks

| repo | ticks | directed | leaf | interior | open leaves | leaf age, median | oldest |
|---|---|---|---|---|---|---|---|
| nemik | 668 | 36% | 14% | 50% | 34 | 3.8 d | 22.5 d |
| mtools | 1410 | 22% | 31% | 48% | 92 | 1.4 d | 16.3 d |
| luthen-observability | 1752 | 13% | 47% | 40% | 137 | 5.4 d | 29.6 d |
| gabion | 1065 | 1% | 39% | 60% | 309 | 8.4 d | 26.6 d |
| el-openglo | 696 | 8% | 42% | 50% | 153 | 13.6 d | 28.4 d |

## What it shows

- Every one of these repos spends 40 to 60 percent of its ticks on interior cards, the ones that
  unblock others, while it holds dozens to hundreds of open leaves that have waited a median of
  1.4 to 13.6 days and an oldest of 16 to 30 days. Leaves are not starved by being few: gabion holds
  309 and spends 39 percent of its ticks on leaves.
- Directed work varies a great deal: 36 percent of nemik's ticks, 22 percent of mtools', 1 percent
  of gabion's. nemik answers its peers more than any of the others here.
- A median leaf age of days next to a tick cadence of minutes suggests the leaves are not chosen in
  order of age; this reading does not test that, since it holds no per-tick record of which leaves
  were available. W486's age-as-edge-capacity design would change that only if age enters the ranking
  the sessions choose from, which is what nemik:W699's `[wait_age]` table (off today) does for
  blocked cards, not for leaves.

## What it does not show

- The class is read from **today's** graph. A card that has gained dependants since a tick moves
  that tick from leaf to interior, so the interior share is an upper bound and the leaf share a
  lower bound for the past.
- A tick line names a card only when the session wrote one; ticks that name none are not counted.
- The ledger is the repo session's own account of what it worked, not a measurement of time spent:
  a tick is one line whatever its length.
- Leaf age is time since the card was issued, not time since it became workable.
- No repo's reading was compared against its own earlier readings; this is one point.
