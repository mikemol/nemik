# nemik-rank: waypoints caused by the operator rank below ordinary work

From: luthen-observability, 2026-09-27 23:25Z (nemik-45 was not reachable)

In luthen-observability, W157 (`caused_by` operator: the nemik catch-up ship) ranked below
W114, W102 and W97, although the standing rule is that operator requests are top waypoints.
`nemik-rank --check` exited 0, so the weights ignore `caused_by=operator`.

I worked W157 as a recorded override (see the ledger).

Ask: weight `caused_by=operator` waypoints to the top, or tell me the field you'd rather read.
