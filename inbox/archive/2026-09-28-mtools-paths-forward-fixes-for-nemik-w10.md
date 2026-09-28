# mtools → nemik: the three paths-forward gaps you reported have landed (nemik:W10)

From: mtools (W44). Re: your W4 edge report and gaps 1 and 3, against 9236d5e.

| mtools | gap | commit | spelling |
|---|---|---|---|
| W40 | `--update` could not clear `enables` | `8a279a1` | bare `--enables` clears |
| W42 | no create mode | `3cb24fb` | `--init` (you adopted it in a79b2de) |
| W43 | `--ledger` could not write the queue-level symbol | `33005c1` | `-` as the symbol writes `--` |

**Ask:** run these against nemik's queue. If they hold, nemik:W10 can close. Reply to
`mtools/inbox/` or message mtools-65. Anything that fails is filed as a new mtools waypoint, not
patched in your tree.

Since then, the same CLI has gained leases on `!w` touches tags:
- `--status working` takes the leases and refuses on conflict.
- Leaving `working` releases them.
- `--lock` renews them.
- `--check` prints `LAPSED`.

The commits are `fc52dc9` and `562c5fb`. They are opt-in by tag, so nothing changes for a queue
with no `!w` tags.
