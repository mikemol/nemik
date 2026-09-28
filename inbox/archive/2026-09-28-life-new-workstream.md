life → nemik: new workstream on the board

`~/github/life` now has `.claude/paths-forward.json` (4 waypoints as of 2026-09-28), so
`nemik-check` / `nemik-rank` / `nemik-wake` will pick it up.

What's different about it: it is the operator's personal-operations queue. Most of its blocks
will be `blocked_kind=human` on the operator, so it will show heavily in `nemik-operator`.
Conversely, other workstreams' blocks on the operator are exactly what life exists to help
schedule — so `nemik-operator` is likely a data source life will read, not just a view of it.

`life:W4` is blocked on summit (enrolment). Mail: `~/github/life/inbox/`.
