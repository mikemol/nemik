<!-- DERIVED from the state file by mikemol-paths-forward --render. NEVER EDIT. -->
# paths-forward — /home/mikemol/github/nemik/.claude/paths-forward.json

counter 43 · heartbeat 2026-09-27T14:38:36Z · job `c499900c` · hash `v2:d440a64263c7e63f`

| # | symbol | status | title | blocked on | next bounded step |
|---|---|---|---|---|---|
| 1 | W17 | ready | Follow up nemik:W4: re-run nemik-operator; nudge any repo whose unstated blocks remain when that repo is next awake | — | Watch aeternum/gabion/sre-troubleshooting for wake |
| 2 | W22 | ready | Trial: SHACL Warning when a waypoint title exceeds 150 chars (decomposition signal, operator request re el-openglo:W45). Fires 256 times across ~/github today (commit f235c4f). Watch whether repos act on it or just accumulate the warning; 150 is a first guess, not measured | — | After it's been live a while, check whether any repo actually decomposed a waypoint because of it |
| 3 | W42 | ready | Witness: every summit ask carrying a waypoint field names a waypoint that exists in its owner's queue and is not dropped (first real case is the first post-W105 ask) | — | Script over summit/floor/*.bib: parse waypoint=<repo>:W<n>, resolve against the merged graph (ChangeRequest or Dropped); report unresolved/dropped; wire as a nemik-check Warning or a nemik-operator column; fixture test |
| 4 | W4 | done | N2: send each repo its blocks on the operator with no ask stated, and the 'operator: decide/act' form | — | — |
| 5 | W15 | done | Gate tests: nemik has no test suite; write pytest coverage for nemik-check exit/provenance lines, nemik-inbound UNCLAIMED column, blocks/operator categories, over a fixture ~/github tree | — | — |
| 6 | W34 | done | nemik-rank: cross-repo transitive downstream weight per ready item, peer edges weighted by declared data, plus drift witness | — | — |
| 7 | W35 | done | Declare peer-edge weight as data (src/nemik/data/rank-weights.toml: local=1, peer=N) | — | — |
| 8 | W36 | done | Compute transitive downstream weight for one waypoint IRI over merged fleet graph (enables closure + peer blocked_on) | — | — |
| 9 | W37 | done | nemik-rank <repo> CLI: list ready items with weight, sorted | — | — |
| 10 | W38 | done | Validate nemik-rank on luthen queue: W120-W127 chains outrank W91/W65 | — | — |
| 11 | W39 | done | Drift witness: fail when a queue's top ready item is outranked on cross-repo weight | — | — |
| 12 | W41 | done | Witness: flag a peer blocked_on/waitsFor edge that lands on an umbrella (a waypoint that its own repo's children enable, or whose next_bounded_step starts with COMPOSITE) instead of the child step | — | — |
| 13 | W43 | done | Ask mtools: stored per-waypoint 'weight' field (set via $PF --update --weight N, sole writer) that model.ordered() keys on (status, -weight, -leverage, file order); loop copies nemik-rank --json into it; drift check then measures staleness of stored weight | — | — |
| 14 | W1 | done | S6: check that every OPEN summit ask's waypoint appears in nemik-inbound for its owner | — | — |
| 15 | W2 | done | U2: say 'waiting on you, claim with --enables <ref>' in nemik-inbound and the Wake panel instead of bare 'unclaimed' (substrate-d9 read it as other repos' business) | — | — |
| 16 | W3 | done | U1: make unclaimed '?' placeholders visible: larger, labelled with the blocked card, counted on the blocker's box | — | — |
| 17 | W5 | done | N3: tell rosettapkg (W13, W14) and substrate (W37) their blocked cards name no resolvable party | — | — |
| 18 | W6 | done | H1: vendor the mikemol-pathsforward wheel so the image build is hermetic (luthen: a network fetch is where a cache miss hides) | — | — |
| 19 | W7 | done | E2: ask luthen to carry each repo's commit state in the export, so the pod can report provenance, not untracked-source | — | — |
| 20 | W8 | done | W2: alert when something waits on an asleep repo for more than N hours (nemik_waiting_on{state=asleep}); rule and panel through luthen's panels/rego | — | — |
| 21 | W9 | done | Move this session to ~/github/nemik: it runs from ~/github/taskboard, so liveness and the hook spool record it as 'taskboard' and nemik reads as asleep | — | — |
| 22 | W10 | done | M2: mtools gaps found bootstrapping this queue: no create mode, no way to clear enables (W4->W2 is backwards), '--' unpassable as ledger symbol | — | — |
| 23 | W12 | done | Copy taskboard's tools-installed-per-repo memory into nemik's project memory dir | — | — |
| 24 | W13 | done | Loop durability: the 15m cron is session-only and expires 2026-10-03; re-arm on session restart or expiry | — | — |
| 25 | W14 | done | Adopter guide: one page (docs/adopting.md, cited from paths-forward-loop skill) on writing a queue nemik reads: writer install, --ledger grammar, kind classes, minted_during, cross-repo refs | — | — |
| 26 | W16 | done | Containerfile test stage: run the gate tests in a stage the final stage depends on, so the image build is nemik's gate (luthen ships on push) | — | — |
| 27 | W18 | done | should_nudge() library function (+ maybe --nudge on nemik-wake): owns the staleness threshold + backoff/dedup decision that luthen's checks/waker.py currently reinvents per-repo (loop_liveness verdict + last_tick -> nudge now yes/no); luthen keeps the SendMessage act, nemik owns the decision. luthen W117 | — | — |
| 28 | W19 | done | nemik-serve wedge: pod stayed k8s state=running but stopped accepting connections for 10+min (readiness timeout -> flat connection refused, 40 failed probes); one BrokenPipeError at serve.py:215 (self.wfile.write) in a request thread, ThreadingHTTPServer so shouldn't take down the accept loop on its own. luthen deleted the pod rather than diagnose further; root cause open. Add a k8s liveness probe (luthen's manifest) so this self-heals regardless of cause; separately look at whether serve.py leaks fds/sockets on a broken pipe | — | — |
| 29 | W20 | done | mikemol-pathsforward's rank_reason is read (render.py) but never written; ordered() only sorts by status bucket at file order, no leverage computation over enables/blocked_on (substrate-c6 found this; confirmed against our vendored copy). Relayed to mtools (mtools/inbox/2026-09-26-substrate-rank-reason-unwritten.md), not nemik's to fix. Every tick's §3 judgment is currently done by hand in the turn because of this -- exactly the failure mode the operator called out on this queue | — | — |
| 30 | W23 | done | W22 trial has ~50% false-positive rate on sampled titles: raw length flags verbose-but-atomic sentences same as genuinely bundled steps | — | — |
| 31 | W24 | done | Dash UI: load() had no error handling (unlike wake()) -- a transient server miss silently blanked the page | — | n/a |
| 32 | W25 | done | CLI ergonomics: --root and --json had no help text on 3 of 5 CLIs while newer flags (--liveness, --all, --nudge) did -- inconsistent --help output | — | n/a |
| 33 | W26 | done | Dash UI: the 60s poll redraw destroyed and rebuilt the cytoscape graph without re-selecting the user's previously-focused node | — | n/a |
| 34 | W27 | done | operator_category's free-text fallback contradicted docs/adopting.md: docs said any decide/act-verb-less text lands unstated; code actually reads >=3-word free text as needs-you regardless | — | n/a |
| 35 | W28 | done | metrics.py review: nemik_prompts_total's docstring didn't document the 'unknown' class fallback (a source string not in CLASS), even though the code can emit it | — | n/a |
| 36 | W29 | done | Dash UI FR (operator, direct): repo boxes should be color-coded by liveliness state | — | n/a |
| 37 | W30 | done | adapter.py review: queue_graph()'s residue-translation loop was duplicated verbatim (dead code, harmless since RDF triples dedupe, but confusing on read) | — | — |
| 38 | W31 | done | check.py deep read: verified survey()'s focus-node-to-repo attribution (by_repo.setdefault) can never actually see an unknown repo given current shapes.ttl targets and adapter.py's URI minting -- defensive but dead code, not a live bug | — | — |
| 39 | W32 | done | Operator direct ask: build a paperkit project documenting nemik's guarantees, modularity (and its gaps), and the standards it's derived from | — | — |
| 40 | W33 | done | ARCHITECTURE.md gate went red on its first maintenance run: paper.toml's claim witness ran bare python3 (/usr/bin, no rdflib), so the 3 witnesses importing nemik failed -- verdict depended on the ambient interpreter | — | — |
| 41 | W40 | done | Ask mtools: pathsforward flags a ready item that stays top of queue across ticks (from ledger) as ATOMIZE | — | — |

## residue

- **W11** (2026-09-26T18:57:05Z) Ship to luthen: send luthen-observability-1b the full pushed sha carrying W2 (and W3 if landed) so nemik-http rebuilds; live is c9a1cca: Superseded by operator ruling 2026-09-26: luthen follows nemik origin/main (images.json nemik.follow) and ships on push; 21251d0 is an ancestor of b05c79f, now shipping. Push = deploy; never send shas. inbox/2026-09-26-luthen-ships-on-push.md
- **W21** (2026-09-26T22:03:08Z) Trial: SHACL Warning when a waypoint title exceeds 150 chars (decomposition signal, operator request re el-openglo:W45). Fires 256 times across ~/github today. Watch: is this useful signal or noise at that threshold; revisit if repos start complaining or ignoring it: duplicate of W22: my first --add call actually succeeded despite a trailing invalid --enables (no symbols given), which I mistook for a full failure and re-ran. W22 is the live one, correctly worded and evidenced
