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
]

PENDING = [
    ("nemik-check --realizability", "W793"),
    ("nemik-check --committed", "W793"),
    ("nemik-check --letters", "W793"),
    ("nemik-check --fold", "W793"),
    ("nemik-collapse", "W793"),
    ("nemik-history", "W785"),
    ("nemik-critical", "W786"),
    ("nemik-pins", "W786"),
    ("nemik-starved", "W786"),
    ("nemik-pacing", "W786"),
    ("nemik-stackable", "W786"),
    ("nemik-floor-asks", "W786"),
    ("nemik-overlaps", "W786"),
    ("nemik-witnesses", "W786"),
]

EXCLUDED = [
    ("nemik-serve", "is the server"),
    ("nemik-static", "builds the static view, a writer"),
    ("nemik-days", "host-private: reads the operator's calendars"),
    ("nemik-ics", "host-private: reads the operator's calendars"),
    ("nemik-tasks", "host-private: reads the operator's tasks"),
    ("nemik-calendar-write", "a writer: writes the operator's calendars"),
    ("nemik-work", "spawns the committer and the writer"),
    ("nemik-replica", "spawns the image build"),
    ("nemik-ask", "a writer: files an ask in a peer's inbox"),
    ("nemik-export", "a writer: writes a project file format"),
    ("nemik-import", "a writer: reads a project file format into a queue"),
    ("nemik-exports", "a writer: publishes the per-repo exports"),
    ("nemik-hostroot", "a writer: writes the host-root document on the host"),
]
