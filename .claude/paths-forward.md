<!-- DERIVED from the state file by mikemol-paths-forward --render. NEVER EDIT. -->
# paths-forward — /home/mikemol/github/nemik/.claude/paths-forward.json

counter 18 · heartbeat 2026-09-26T20:51:22Z · job `79b79d50` · hash `v2:7c4c1949f099a969`

| # | symbol | status | title | blocked on | next bounded step |
|---|---|---|---|---|---|
| 1 | W12 | ready | Copy taskboard's tools-installed-per-repo memory into nemik's project memory dir | — | cp ~/.claude/projects/-home-mikemol-github-taskboard/memory/tools-installed-per-repo.md into nemik memory + MEMORY.md pointer |
| 2 | W13 | ready | Loop durability: the 15m cron is session-only and expires 2026-10-03; re-arm on session restart or expiry | — | On restart/expiry: --payload, CronCreate, --armed <id> |
| 3 | W14 | ready | Adopter guide: one page (docs/adopting.md, cited from paths-forward-loop skill) on writing a queue nemik reads: writer install, --ledger grammar, kind classes, minted_during, cross-repo refs | — | Draft docs/adopting.md from the reply sent to el-openglo-8c; ask operator before editing the global skill to cite it |
| 4 | W17 | ready | Follow up nemik:W4: re-run nemik-operator; nudge any repo whose unstated blocks remain when that repo is next awake | — | Next tick after those repos wake: nemik-operator \| unstated section; compare against the 8 refs in W4 evidence |
| 5 | W18 | ready | should_nudge() library function (+ maybe --nudge on nemik-wake): owns the staleness threshold + backoff/dedup decision that luthen's checks/waker.py currently reinvents per-repo (loop_liveness verdict + last_tick -> nudge now yes/no); luthen keeps the SendMessage act, nemik owns the decision. luthen W117 | — | Read luthen checks/waker.py's REWAKE_S=30min + seen-timestamp bookkeeping; port the shape into nemik.wake as should_nudge(repo, verdict, last_tick, now) -> bool, age computed from last_tick |
| 6 | W1 | blocked | S6: check that every OPEN summit ask's waypoint appears in nemik-inbound for its owner | summit:W105 | — |
| 7 | W8 | blocked | W2: alert when something waits on an asleep repo for more than N hours (nemik_waiting_on{state=asleep}); rule and panel through luthen's panels/rego | luthen-observability | When luthen adds the rule (or pushes back on severity/threshold), verify it fires against a synthetic asleep+waiting series if possible, else confirm the declaration matches what was proposed |
| 8 | W10 | blocked | M2: mtools gaps found bootstrapping this queue: no create mode, no way to clear enables (W4->W2 is backwards), '--' unpassable as ledger symbol | mtools:W42, mtools:W43 | — |
| 9 | W2 | done | U2: say 'waiting on you, claim with --enables <ref>' in nemik-inbound and the Wake panel instead of bare 'unclaimed' (substrate-d9 read it as other repos' business) | — | — |
| 10 | W3 | done | U1: make unclaimed '?' placeholders visible: larger, labelled with the blocked card, counted on the blocker's box | — | — |
| 11 | W4 | done | N2: send each repo its blocks on the operator with no ask stated, and the 'operator: decide/act' form | — | — |
| 12 | W5 | done | N3: tell rosettapkg (W13, W14) and substrate (W37) their blocked cards name no resolvable party | — | — |
| 13 | W6 | done | H1: vendor the mikemol-pathsforward wheel so the image build is hermetic (luthen: a network fetch is where a cache miss hides) | — | — |
| 14 | W7 | done | E2: ask luthen to carry each repo's commit state in the export, so the pod can report provenance, not untracked-source | — | — |
| 15 | W9 | done | Move this session to ~/github/nemik: it runs from ~/github/taskboard, so liveness and the hook spool record it as 'taskboard' and nemik reads as asleep | — | — |
| 16 | W15 | done | Gate tests: nemik has no test suite; write pytest coverage for nemik-check exit/provenance lines, nemik-inbound UNCLAIMED column, blocks/operator categories, over a fixture ~/github tree | — | — |
| 17 | W16 | done | Containerfile test stage: run the gate tests in a stage the final stage depends on, so the image build is nemik's gate (luthen ships on push) | — | — |

## residue

- **W11** (2026-09-26T18:57:05Z) Ship to luthen: send luthen-observability-1b the full pushed sha carrying W2 (and W3 if landed) so nemik-http rebuilds; live is c9a1cca: Superseded by operator ruling 2026-09-26: luthen follows nemik origin/main (images.json nemik.follow) and ships on push; 21251d0 is an ancestor of b05c79f, now shipping. Push = deploy; never send shas. inbox/2026-09-26-luthen-ships-on-push.md
