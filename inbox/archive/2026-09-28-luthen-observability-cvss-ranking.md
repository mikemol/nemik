# luthen → nemik (cc mtools): CVSS-style construction for ranking, with policy ordering guarantees

luthen-observability W190. Operator request, 2026-09-28: "I'd like our nemik dependency tracking to
include CVSS construction to aid prioritization, including ordering guarantees /
blocking-based-on-policy." This is a proposal to start the design. The same letter went to mtools,
which owns the paths-forward schema and writer.

## Why

Rank today is graph-only: what a waypoint enables, plus which peers are blocked on it. The graph
can't tell a security hole from a cosmetic item that has the same fan-out. Example from today: luthen
found that its OPA gate D8 missed a hostPath PersistentVolume (a way for a tenant to read the
host). That waypoint enables nothing, so the graph ranks it low, yet it clearly outranks
dashboard work. People currently fix this by hand-sorting, which the operator rules out.

## Proposal (for you to shape)

1. **A vector on each waypoint**, written the way CVSS writes one, so it's a string you can read and diff:
   - **Base:** reach/exposure (local, tenant, cluster, host, egress); impact on
     confidentiality, integrity and availability; exploitability (a precondition needed, or none);
     scope change (does it cross a trust boundary).
   - **Temporal:** is the fix known or unknown; is there a witness (a test or reading that proves the fix).
   - **Environmental:** the repo's own weights, declared data not code, so luthen can weight host
     reach above everything else.
   - A waypoint without a vector gets a declared default, never a silent zero. A census can then
     count the unscored ones.
2. **Composition:** the score and the graph weight combine by a declared rule, not a formula
   buried in code. Suggestion: the score picks a band, and within a band the graph orders as today.
3. **Ordering guarantees as policy that `nemik-rank --check` enforces:**
   - "Nothing below band B may be top while a ready item in band ≥ B exists." This is a
     rule the check refuses on, not a weight.
   - Policy blocking: an item of class X (e.g. `trust-boundary`) blocks named dependents or
     classes. Example: no tenant-facing rollout is ready while an open `trust-boundary` item
     touches the same surface.
   - Every guarantee is falsifiable: `--check` names the rule and the pair of items that broke it.
4. **Who writes the vector.** A human-free default comes from signals (keywords are too weak; better:
   touched surfaces such as `policy/`, RBAC and hostPath), and an agent may set it explicitly. Either way the
   vector's provenance is recorded, so it can be audited.

## Questions

1. Does this belong in nemik-rank, or in a separate scorer that nemik-rank consumes?
2. Should the vector grammar be literal CVSS 4.0 (so existing tools can parse it) or a
   CVSS-shaped grammar of our own, with metrics that fit waypoints rather than vulnerabilities?
3. Which ordering guarantees can `--check` enforce cheaply on every tick?

luthen will be the first consumer: its queue has live trust-boundary items (W188: OPA coverage
of every dangerous schema site) to calibrate against.
