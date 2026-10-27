# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""parity: which read-only CLI commands the web view answers, and which not (nemik:W782, W781).

Operator goal 2026-10-20 (nemik:W781): read-only feature parity between the CLI tools and the web
UI, without spawning processes through the UI. Parity is a test, not a promise: every nemik-*
console script is in exactly one of three lists here, and tests/test_parity.py fails on a script in
none, on a routed row whose route or function the server does not carry, and on a pending list
that grows.

- ROUTED: (command, route, function): the server answers `route` by calling the same `function`
  the command calls, so there is one implementation.
- PENDING: (command, card): read-only and not yet served; `card` is the open card that adds the
  route. A row may name one mode of a routed command ("nemik-check --integrity"). The list only
  shrinks.
- EXCLUDED: (command, reason): not served on purpose, by a declared reason, never silently: a
  writer, a spawner, the server itself, or host-private.
"""

ROUTED = [
    ("nemik-wake", "/wake", "roster"),
    ("nemik-operator", "/operator", "operator_asks"),
    ("nemik-inbound", "/inbound", "inbound"),
    ("nemik-metrics", "/metrics", "metrics"),
    ("nemik-rank", "/goals/", "goals"),
    ("nemik-check", "/check.json", "finding_lines"),
    ("nemik-check --ready-neither", "/check/", "ready_neither_text"),
    ("nemik-check --unmanifested", "/check/", "unmanifested_text"),
    ("nemik-check --integrity", "/check/", "integrity_text"),
    ("nemik-check --letters", "/check/", "letters_report"),
    ("nemik-check --fold", "/check/", "letters_report"),
    ("nemik-critical", "/critical.json", "critical_doc"),
    ("nemik-starved", "/starved.json", "starved_fleet"),
    ("nemik-overlaps", "/overlaps.json", "overlaps"),
    ("nemik-pacing", "/pacing.json", "paces"),
    ("nemik-floor-asks", "/floor-asks.json", "unresolved"),
    ("nemik-collapse", "/collapse.json", "collapse_lines"),
    # nemik:W785: --oldest reads only files and is served directly; the five modes that read git
    # are published by the host (nemik-history --publish) and served from /history/<mode>.json.
    ("nemik-history", "/history/", "history_response"),
    ("nemik-history --oldest", "/oldest.json", "oldest_rows"),
]

PENDING: list[tuple[str, str]] = []

EXCLUDED = [
    ("nemik-serve", "is the server"),
    ("nemik-static", "builds the static view, a writer"),
    ("nemik-days", "host-private: reads the operator's calendars"),
    ("nemik-ics", "host-private: reads the operator's calendars"),
    ("nemik-tasks", "host-private: reads the operator's tasks"),
    ("nemik-calendar-write", "a writer: writes the operator's calendars"),
    ("nemik-work", "spawns the committer and the writer"),
    ("nemik-pins", "spawns git and kubectl to measure how far behind a pin is"),
    ("nemik-witnesses", "spawns the pinned opa and reads the metrics backends"),
    (
        "nemik-check --realizability",
        "spawns the pinned opa to judge every waypoint (W860)",
    ),
    (
        "nemik-check --committed",
        "runs git to see whether each queue is committed (W861)",
    ),
    ("nemik-stackable", "runs git for the staged, cited and tracked files of a repo"),
    ("nemik-replica", "spawns the image build"),
    ("nemik-ask", "a writer: files an ask in a peer's inbox"),
    ("nemik-export", "a writer: writes a project file format"),
    ("nemik-import", "a writer: reads a project file format into a queue"),
    ("nemik-exports", "a writer: publishes the per-repo exports"),
    ("nemik-hostroot", "a writer: writes the host-root document on the host"),
    (
        "nemik-stale",
        "host-private: compares the host's installed venv with a source tree (W730)",
    ),
]
