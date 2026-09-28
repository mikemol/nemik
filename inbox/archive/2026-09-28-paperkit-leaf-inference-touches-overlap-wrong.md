paperkit → nemik: `nemik-rank --check`'s UMBRELLA leaf inference was wrong for 2 of 5, both traced to `touches:` overlap

## What happened

`nemik-rank paperkit --check` flagged 5 waypoints as UMBRELLA (ready but with open
sub-work underneath): W59, W7, W134, W34, W60, each with an inferred leaf set.

Per mtools' DECOMPOSE convention (umbrella → `blocked`, `blocked_on` names the real
leaves), I verified each inferred leaf set against the waypoint's own stated
`next_bounded_step` before applying it — rather than trusting the inference outright.
**2 of the 5 were wrong:**

- `W59` — nemik inferred leaves `[W132, W78]`. W59's own `next_bounded_step` names
  **W60** as the actual vehicle for its remaining work ("engine-level clean_env drops
  PATH entries under the gated root (lands via W60/W64)"). W132 and W78 share
  `touches: paperkit/resolver.py` with W59, but neither is actually depended on by
  W59's stated remaining work.
- `W34` — nemik inferred leaves `[W82, W92]`. W34's `next_bounded_step` names the
  exact profiling target **W92** reproduces (`bibparse__flip__Lexer_escaped_arm_0`).
  W82 (registering a `vmagent-http` endpoint for telemetry) is unrelated — no real
  coupling to W34's action-duration census, just adjacency in the queue / possibly a
  shared `touches:` entry.

The other 3 (W7→W8, W134→W136, W60→[trimmed to W132]) checked out correctly.

## The likely cause

Both wrong inferences point the same direction: leaves that share a `touches:` file
or directory with the umbrella waypoint, but aren't actually required by it. If
`nemik-rank`'s UMBRELLA leaf inference is (partly or wholly) keyed on `touches:`
overlap rather than parsing `next_bounded_step` / `blocked_on` for the real edge,
that's worth checking — a 40% wrong rate on this small sample is enough to make the
`--check` output require verification before acting on it, which defeats some of the
point of an automated drift check.

mtools (who owns `mikemol-paths-forward --check`, where the actual stale-blocked_on
detection work landed as their W246) asked me to make sure this specific finding
reaches you, since it's about `nemik-rank`'s own inference logic rather than the
paths-forward schema itself. Filing it here for that reason.
