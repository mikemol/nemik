<!-- DERIVED from the state file by mikemol-paths-forward --render. NEVER EDIT. -->
# paths-forward — /home/mikemol/github/nemik/.claude/paths-forward.json

counter 20 · heartbeat 2026-09-26T21:55:42Z · job `1f3a0b3d` · hash `v2:a4804f2c22a53009`

| # | symbol | status | title | blocked on | next bounded step |
|---|---|---|---|---|---|
| 1 | W17 | ready | Follow up nemik:W4: re-run nemik-operator; nudge any repo whose unstated blocks remain when that repo is next awake | — | Watch aeternum/gabion/sre-troubleshooting for wake |
| 2 | W20 | ready | mikemol-pathsforward's rank_reason is read (render.py) but never written; ordered() only sorts by status bucket at file order, no leverage computation over enables/blocked_on (substrate-c6 found this; confirmed against our vendored copy). Relayed to mtools (mtools/inbox/2026-09-26-substrate-rank-reason-unwritten.md), not nemik's to fix. Every tick's §3 judgment is currently done by hand in the turn because of this -- exactly the failure mode the operator called out on this queue | — | Watch mtools/summit for a response; when rank_reason is populated upstream, bump the vendored wheel and stop hand-deriving §3 each tick |
| 3 | W1 | blocked | S6: check that every OPEN summit ask's waypoint appears in nemik-inbound for its owner | summit:W105 | — |
| 4 | W8 | blocked | W2: alert when something waits on an asleep repo for more than N hours (nemik_waiting_on{state=asleep}); rule and panel through luthen's panels/rego | luthen-observability | When luthen adds the rule (or pushes back on severity/threshold), verify it fires against a synthetic asleep+waiting series if possible, else confirm the declaration matches what was proposed |
| 5 | W10 | blocked | M2: mtools gaps found bootstrapping this queue: no create mode, no way to clear enables (W4->W2 is backwards), '--' unpassable as ledger symbol | mtools:W43 | — |
| 6 | W2 | done | U2: say 'waiting on you, claim with --enables <ref>' in nemik-inbound and the Wake panel instead of bare 'unclaimed' (substrate-d9 read it as other repos' business) | — | — |
| 7 | W3 | done | U1: make unclaimed '?' placeholders visible: larger, labelled with the blocked card, counted on the blocker's box | — | — |
| 8 | W4 | done | N2: send each repo its blocks on the operator with no ask stated, and the 'operator: decide/act' form | — | — |
| 9 | W5 | done | N3: tell rosettapkg (W13, W14) and substrate (W37) their blocked cards name no resolvable party | — | — |
| 10 | W6 | done | H1: vendor the mikemol-pathsforward wheel so the image build is hermetic (luthen: a network fetch is where a cache miss hides) | — | — |
| 11 | W7 | done | E2: ask luthen to carry each repo's commit state in the export, so the pod can report provenance, not untracked-source | — | — |
| 12 | W9 | done | Move this session to ~/github/nemik: it runs from ~/github/taskboard, so liveness and the hook spool record it as 'taskboard' and nemik reads as asleep | — | — |
| 13 | W12 | done | Copy taskboard's tools-installed-per-repo memory into nemik's project memory dir | — | — |
| 14 | W13 | done | Loop durability: the 15m cron is session-only and expires 2026-10-03; re-arm on session restart or expiry | — | — |
| 15 | W14 | done | Adopter guide: one page (docs/adopting.md, cited from paths-forward-loop skill) on writing a queue nemik reads: writer install, --ledger grammar, kind classes, minted_during, cross-repo refs | — | — |
| 16 | W15 | done | Gate tests: nemik has no test suite; write pytest coverage for nemik-check exit/provenance lines, nemik-inbound UNCLAIMED column, blocks/operator categories, over a fixture ~/github tree | — | — |
| 17 | W16 | done | Containerfile test stage: run the gate tests in a stage the final stage depends on, so the image build is nemik's gate (luthen ships on push) | — | — |
| 18 | W18 | done | should_nudge() library function (+ maybe --nudge on nemik-wake): owns the staleness threshold + backoff/dedup decision that luthen's checks/waker.py currently reinvents per-repo (loop_liveness verdict + last_tick -> nudge now yes/no); luthen keeps the SendMessage act, nemik owns the decision. luthen W117 | — | — |
| 19 | W19 | done | nemik-serve wedge: pod stayed k8s state=running but stopped accepting connections for 10+min (readiness timeout -> flat connection refused, 40 failed probes); one BrokenPipeError at serve.py:215 (self.wfile.write) in a request thread, ThreadingHTTPServer so shouldn't take down the accept loop on its own. luthen deleted the pod rather than diagnose further; root cause open. Add a k8s liveness probe (luthen's manifest) so this self-heals regardless of cause; separately look at whether serve.py leaks fds/sockets on a broken pipe | — | — |

## residue

- **W11** (2026-09-26T18:57:05Z) Ship to luthen: send luthen-observability-1b the full pushed sha carrying W2 (and W3 if landed) so nemik-http rebuilds; live is c9a1cca: Superseded by operator ruling 2026-09-26: luthen follows nemik origin/main (images.json nemik.follow) and ships on push; 21251d0 is an ancestor of b05c79f, now shipping. Push = deploy; never send shas. inbox/2026-09-26-luthen-ships-on-push.md
