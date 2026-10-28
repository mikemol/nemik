# Climate interventions (nemik:W750)

A practice change is dated as an intervention (`mikemol-paths-forward --intervention KIND NOTE`),
and its effect is read as a shift between a window before it and a window after. The event lands as
station `nemik:fleet:intervention` in luthen's VictoriaLogs (read back 2026-10-24 with
`service.name:mikemol-paths-forward "fleet:intervention" -"accepted"`). "intervention sent" means
the detached sender started, not that it was delivered (mtools:W1887).

## Sent

| When (UTC) | Kind | Practice change | Read back |
|---|---|---|---|
| 2026-10-21T02:14:31Z | repin | the move to mtools f2f18a1 | yes, 2026-10-24 |
| 2026-10-27 | stack | stack583 (W1191), one stack for a round | not yet |
| 2026-10-28 | other | reviewed-loop adopted (loop prompt line 31): G0 before the tick, G1 after, one token spender | not yet |

Past changes before the first event cannot be dated honestly: an event carries its send time.

## Windows

None matured yet. Each row above gets a before and after window here once the metric side
(`mikemol.waypoint.event`) is read back and a window of ticks has passed.
