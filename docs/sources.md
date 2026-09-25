# Taskboard — ledger sources (working state)

## From luthen-observability (2026-09-25)
- Addresses: never copy. Resolve by name: `python -m checks.endpoints_query --side host|pod <name>` in ~/github/luthen-observability (endpoints.json).
- VictoriaMetrics: query `vmsingle-http` (Prom API); push `vmagent-http`. Series: luthen_check_state{check}, luthen_check_timestamp_seconds, ALERTS, node_*/container_* PSI.
- VictoriaLogs: `victorialogs-http` (LogsQL /select/logsql/query): host journal + pod logs.
- No trace store on luthen.
- Cluster: k3s single node `luthen`, namespace `buildbuddy`, cluster DNS names, no ingress. Managed hosting: luthen deploys (terraform + policy gate); we hand over image, ports, storage, pg tenant.
- Dependency graph: per-repo `.claude/paths-forward.json` (symbol, status, blocked_on, blocked_kind, `enables` edges).
- Activity ledger: `.claude/paths-forward.ledger`, `<ISO-UTC> <kind> <symbol> <verb> <mechanism> "summary"`. kind=tick → forecast; kind=manual → interrupt. Formats drifted before today: parse tolerantly.
- Liveness: `python -m checks.loop_liveness` (per-repo JSON).
- Sessions: systemd user units `claude-<repo>-p<pid>.scope` → cgroup CPU/mem/PSI.
- Cross-repo: summit (`~/github/summit/scripts/summit`), `inbox/` letters per repo.
- Obligation: register taskboard in summit once it offers a capability.

## From summit (2026-09-25)
- Read via tools, never parse files: `~/github/summit/scripts/summit` (no args lists modes).
  - Asks: `summit ask [--for id]`. State is computed (OPEN/CLOSED/UNAVAILABLE/RETIRED), no status field.
  - Reports: `summit floor`. State = corroboration count; edges `of=` (parent) and `rests-on` (claim DAG): a usable hypergraph.
  - Registries: `summit delegate <id>`, `summit capability <x>`. Ledger: ledger/entries/*.md.
- Paths-forward repos: aeternum, amr-skills, cassian-observability, el-openglo, gabion, gcalculus, linux-sources (+ ~/github/.linux-sources-gate-wt), luthen-observability, mat230*, mat260, mtools, paperkit, rosettapkg, sre-troubleshooting*, substrate, summit. (*retiring)
- The one reader: mtools `mikemol-pathsforward` (--show/--queue/--payload/--hash). Use it; schemas differ across repos.
- Waypoints: W<n> never reused; status ready|blocked|working|done; enables, touches, blocked_on, blocked_kind agent|human; residue.
- Interrupt signal: ledger lines whose symbol was minted after armed_at (peer-message-driven), plus kind=manual.
- Prior art: none registered.
- Enrolment: taskboard not enrolled; operator decides. Then file a use-case letter (kind=use-case by=taskboard) in ~/github/summit/floor/inbox/ after reading summit CLAUDE.md "Filing into floor/inbox/".

## Next
- ⚑ Operator: enrol taskboard in summit? · T2 hypergraph model (interrupts attach as nodes with edges into forecast waypoints) · T3 image + hosting request to luthen

## Research survey (2026-09-25): reinvention, rituals, mechanizations
Taskboard = thin federating view; do NOT reimplement:
- Graph read/write: mtools `mikemol-paths-forward` (pathsforward/src/mikemol/pathsforward/cli.py, ledger.py). luthen `checks/paths_forward.py` duplicates it (drift; flag to summit).
- Liveness: luthen `checks/loop_liveness.py`.
- Boards: `summit next|ask|floor|intake|runs|reach`.
- Dashboards: luthen `checks/panels.py` (Grafana, panels must cite scraped metrics); check_producer on 5m timer → VM.
Ledger `kind` drift across all ledgers: tick 2476, msg 136, peer 95, op 82, manual 72, main 62, note 60, swarm 57, -- 38, arm 37.
Hooks that fire without an agent choosing: global SessionStart `claude_session_scope`; per-repo PreToolUse mikemol-hooks; `.githooks` in 18 repos; luthen timers. None touch ledgers.

### Attach points (ranked)
- A1 mtools paths-forward: closed `--kind` vocab + legacy map; `--add` stamps minted_at/minted_during + `--caused-by` edge. (shared machinery → letter to mtools)
- A2 luthen check_producer check: taskboard_effort{repo,class}, taskboard_waypoints{status} → VM → Grafana.
- A3 global UserPromptSubmit/Stop hook: prompt while loop armed ⇒ manual interrupt spool. Catches unrecorded interrupts. (operator's settings; must exit 0)
- A4 shared .githooks commit-msg: `Waypoint: W<n>` trailer from lock holder, else unscheduled.
- A5 inbox letters as interrupt nodes; waypoint caused-by cites letter id.
- A6 cgroup CPU × lock holder (effort measure). A7 OTLP tick spans (rigor-dependent, last).

## A3 installed (2026-09-25, operator approved)
- ~/.claude/settings.json: UserPromptSubmit, Stop, SessionStart → ~/.claude/hooks/taskboard_event.sh (shim) → hooks/record_event.py.
- Spool: ~/.local/state/taskboard/events.jsonl, one raw fact/event: ts, event, session_id, pid, cwd, repo, source (operator|peer|subagent|background) for prompts. No prompt text stored. No classification in hook.
- Backup: ~/.claude/settings.json.bak-taskboard. Sessions load hooks at start; existing sessions won't record until restarted.

## Model direction: ForgeFed / ActivityPub (operator, 2026-09-25)
Operator correction: repos-with-their-own-agent ARE separate federated workstreams, so ForgeFed fits.
Candidate mapping (to verify against ForgeFed spec in R1):
- repo agent → Actor (with inbox/outbox); `<repo>/inbox/` letters ≈ ActivityPub inbox; summit ≈ hub/relay.
- waypoint W<n> → Ticket; enables/blocked_on → TicketDependency; blocked_kind human → dependency on a Person actor (operator).
- summit ask → Offer{Ticket} to the owner's Actor; OPEN/CLOSED → Accept/Reject/Resolve.
- interrupt → an incoming Activity (letter, peer msg, operator prompt) that a waypoint's Create cites (context/inReplyTo). Hook spool events are Activities too.
- PROV stays for derivation edges; OTel for effort.

## Direction set (operator, 2026-09-25)
Taskboard = open-source, standards-first AI project management: well-built standards, new lightweight tooling.
- OSLC (per-repo published state: CM ChangeRequest, ResourceShape≈SHACL, TRS change logs, Automation for ticks, EMS for effort)
- ForgeFed/ActivityPub (between-workstream messages; interrupts as Activities) — complementary, not competing.
- Python: rdflib + pyshacl adapters, read-only, generated from mtools/summit. Agents do nothing manually.
- R1 dispatched → docs/specs-survey.md.

## Renamed: taskboard → nemik (operator, 2026-09-25)
"taskboard" is an existing product. Repo is ~/github/nemik; inbox ~/github/nemik/inbox/; hook shim ~/.claude/hooks/nemik_event.sh; spool ~/.local/state/nemik/events.jsonl. Extension namespace: `nemik:` (survey calls it `tb:`). ~/github/taskboard left as empty git repo (operator to remove).
Hook fixes per luthen: repo from walking up for .git (no subprocess/wall-clock timeout); session join key = cgroup scope `claude-<repo>-p<pid>.scope` from /proc/self/cgroup.

## S3 first slice (2026-09-25)
- src/nemik/data/nemik.ttl (extension vocab), shapes.ttl (WaypointShape, BlockedShape), adapter.py (queue → oslc_cm:ChangeRequest via mikemol.pathsforward.store.load), check.py (`nemik-check`).
- Check: `env -i /home/mikemol/github/nemik/.venv/bin/nemik-check --root /home/mikemol/github` → currently rc=1, correctly.
- First run: 11 conform; 6 violate (aeternum, el-openglo, gcalculus, mtools, rosettapkg, summit).
  statuses outside ready|blocked|working|done: dropped×3, residue×2, open×1; blocked_kind operator/peer; blocked without blockedOn/Kind ×2; comma-joined enables strings (e.g. "W46,W35") ×7.
- Gap: mtools has no ledger *reader* (ledger.py only formats); needed before TRS/interrupt adapter. Add to A1.

## S3 revision per summit review (2026-09-25)
- Residue entries become nemik:Dropped; enables resolves against waypoints OR residue.
- Severity split: Violation (fails check) = dangling edge, duplicated symbol/title. Warning (reported only) = status/kind outside mtools' four/two, blocked without blockedOn/Kind, edge into dropped item.
- Now violating: el-openglo (comma-joined enables ×4), rosettapkg (W6 live+residue). rc=1.
- Filed summit floor/inbox/2026-09-25-nemik-friction-the-queue-vocabulary-has-one-owner-and-six-dialects.bib (kind=friction by=nemik).

## A1 sent (2026-09-25)
mtools inbox/2026-09-25-nemik-pathsforward-provenance-and-ledger-reader.md: ledger reader; --add provenance (minted_at, minted_during, --caused-by); write-time refusals. S4 waits on the ledger reader.
mtools accepted A1 as their W26: order Ask3 (write refusals) → Ask1 (ledger.parse) → Ask2 (--add provenance). One commit per ask, sha to nemik. Compat: new fields optional on read, 6857d33 still loads. After their current pycodemod step.

## 2026-09-25 later
- Public remote: https://github.com/mikemol/nemik (first commit fe72d56).
- mtools Ask3 landed b46475f: add refuses when counter lags a claimed symbol (the rosettapkg W6 path). Comma-joined enables was already refused, so el-openglo entries predate the guard or came from another writer. mtools --check reports them as edges findings.

## A2 slice (2026-09-25)
- Hook now tags source=tick for mtools payload prompts ("[paths-forward tick]") and operator-tick for a bare "tick". Spool lines before this change count scheduled ticks as operator.
- nemik-metrics prints nemik_waypoints{repo,state}, nemik_findings{repo,severity}, nemik_prompts_total{repo,source,class=forecast|interrupt|internal}, nemik_turns_total{repo}. Push is luthen's (policy-admitted names).

## A2 live (2026-09-25)
luthen relay: host/metrics_relays.json runs nemik-metrics every 5m (luthen-metrics-relay.timer, 120 CPU-s, nemik_* only) → vmagent. Keep it idempotent and fast. Sent luthen: nemik-check exit semantics for LOCAL_CHECKS, plus 5 panel specs (effort by class, interrupts by repo, waypoints by state, violations, blocked).

## S4 slice 1 (2026-09-25)
- Pin mtools 1b799bc (ledger.read/parse). adapter.ledger_graph: each parsed line is a prov:Activity, prov:used its waypoint, with nemik:kind and nemik:effortClass (KIND_CLASS: tick/arm forecast; manual/msg/peer/op/main/swarm interrupt; else unclassified).
- Totals across all ledgers: forecast 2320, interrupt 524, unclassified 341, unparsed (legacy) 1158. nemik-metrics adds nemik_ledger_lines{repo,class,kind} and nemik_ledger_unparsed{repo}. Run cost 1.82 s user CPU.
- mtools parse accepted stamp "2026-09-24T" (linux-sources and its gate worktree): kept as nemik:rawStamp. Report to mtools.
- Still missing: what caused each waypoint (Ask 2).

## T3 slice 1 (2026-09-25)
nemik-serve: / (cytoscape+dagre dependency view: repo compounds, state colours, border = interrupt share), /graph.json, /graph.ttl. Rebuilds only on queue/ledger mtime change. 687 nodes, 220 edges, 440 with ledger effort. Containerfile added; hosting ask to luthen.

## T3 per luthen review (W82)
- NEMIK_ROOT (default ~/github); reads either <root>/<repo>/.claude/paths-forward.* or export layout <root>/<repo>/paths-forward.*. Pod mounts luthen host-side export read-only at /export (never all of ~/github: amr-skills corpora, .venvs, inboxes).
- cytoscape/dagre/cytoscape-dagre vendored in src/nemik/web/vendor (SHA256SUMS); page makes no external requests.
- /metrics: nemik_build_info, nemik_graph_{nodes,edges,workstreams}, nemik_graph_rebuilds_total, nemik_graph_rebuild_cpu_seconds (policy D14).

luthen accepted 54c7b88 (W82): export timer (incl. .linux-sources-gate-wt), then image pinned, then Deployment/Service via tofu. They will say when nemik-http answers. Deferred: vendor the mikemol-pathsforward wheel so the image build is hermetic (H1).
