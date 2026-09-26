<!-- DERIVED from the state file by mikemol-paths-forward --render. NEVER EDIT. -->
# paths-forward — /home/mikemol/github/nemik/.claude/paths-forward.json

counter 14 · heartbeat 2026-09-26T18:38:45Z · job `476d5581` · hash `v2:e981304b3eb2d5b4`

| # | symbol | status | title | blocked on | next bounded step |
|---|---|---|---|---|---|
| 1 | W4 | ready | N2: send each repo its blocks on the operator with no ask stated, and the 'operator: decide/act' form | — | — |
| 2 | W5 | ready | N3: tell rosettapkg (W13, W14) and substrate (W37) their blocked cards name no resolvable party | — | — |
| 3 | W6 | ready | H1: vendor the mikemol-pathsforward wheel so the image build is hermetic (luthen: a network fetch is where a cache miss hides) | — | — |
| 4 | W7 | ready | E2: ask luthen to carry each repo's commit state in the export, so the pod can report provenance, not untracked-source | — | — |
| 5 | W8 | ready | W2: alert when something waits on an asleep repo for more than N hours (nemik_waiting_on{state=asleep}); rule and panel through luthen's panels/rego | — | — |
| 6 | W11 | ready | Ship to luthen: send luthen-observability-1b the full pushed sha carrying W2 (and W3 if landed) so nemik-http rebuilds; live is c9a1cca | — | Send luthen-observability-1b sha 21251d0522db3efe2f2464d01b87b32823fa2972 (carries W2 f054c4a + W3); they rebuild nemik-http at it |
| 7 | W12 | ready | Copy taskboard's tools-installed-per-repo memory into nemik's project memory dir | — | cp ~/.claude/projects/-home-mikemol-github-taskboard/memory/tools-installed-per-repo.md into nemik memory + MEMORY.md pointer |
| 8 | W13 | ready | Loop durability: the 15m cron is session-only and expires 2026-10-03; re-arm on session restart or expiry | — | On restart/expiry: --payload, CronCreate, --armed <id> |
| 9 | W14 | ready | Adopter guide: one page (docs/adopting.md, cited from paths-forward-loop skill) on writing a queue nemik reads: writer install, --ledger grammar, kind classes, minted_during, cross-repo refs | — | Draft docs/adopting.md from the reply sent to el-openglo-8c; ask operator before editing the global skill to cite it |
| 10 | W1 | blocked | S6: check that every OPEN summit ask's waypoint appears in nemik-inbound for its owner | summit:W105 | — |
| 11 | W10 | blocked | M2: mtools gaps found bootstrapping this queue: no create mode, no way to clear enables (W4->W2 is backwards), '--' unpassable as ledger symbol | mtools:W40, mtools:W42, mtools:W43 | — |
| 12 | W2 | done | U2: say 'waiting on you, claim with --enables <ref>' in nemik-inbound and the Wake panel instead of bare 'unclaimed' (substrate-d9 read it as other repos' business) | — | — |
| 13 | W3 | done | U1: make unclaimed '?' placeholders visible: larger, labelled with the blocked card, counted on the blocker's box | — | — |
| 14 | W9 | done | Move this session to ~/github/nemik: it runs from ~/github/taskboard, so liveness and the hook spool record it as 'taskboard' and nemik reads as asleep | — | — |

## residue

- (none)
