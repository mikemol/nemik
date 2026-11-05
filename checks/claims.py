#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""Per-claim discriminating witnesses, the `claim:` check type.

It is registered in paper.toml as `[checks.claim] cmd = "python3 checks/claims.py {target}"`.

Each function asserts the SPECIFIC proposition its claim makes about nemik's source, so a claim
that goes false as the code changes fails its own check rather than a shared one standing in for
several claims. Run from the repo root (paperkit's `root = "."` in paper.toml puts cwd there):

    python3 checks/claims.py <claim-key>      # exit 0 = claim holds
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from nemik.adapter import NEMIK, OSLC_CM, STATE, reference_uri
from nemik.metrics import label

ROOT = Path(__file__).resolve().parents[1]
MIN_DIRECT_RDFLIB_IMPORTERS = (
    2  # the claim is a gap: rdflib is not behind adapter alone
)
SRC = ROOT / "src" / "nemik"


def _src(name: str) -> str:
    return (SRC / name).read_text()


def _modules() -> dict[str, str]:
    return {p.stem: p.read_text() for p in SRC.glob("*.py") if p.stem != "__init__"}


def _imports_nemik(text: str) -> set[str]:
    return {
        m.group(1)
        for m in re.finditer(r"^from nemik\.(\w+) import", text, re.MULTILINE)
    }


def _require(condition: object, message: str) -> None:
    """Fail the running claim with `message` unless `condition` holds.

    Args:
        condition: The proposition the claim asserts.
        message: What to report when it does not hold.

    Raises:
        AssertionError: the condition is falsy; main reports it and exits 1.

    """
    if not condition:
        raise AssertionError(message)


# -- guarantees ---------------------------------------------------------------------------------


def single_writer_boundary() -> None:
    """Only adapter.py parses the state file, through mtools' store.load."""
    # adapter.py is the ONE module that parses the state file (through mtools' store.load); no
    # other module re-implements that parse.
    mods = _modules()
    # The module `store`, not any name ending in it: nemik.cachestore (W518) has its own load().
    call = re.compile(r"(?<![A-Za-z0-9_])store\.load\s?\(")
    readers = [name for name, text in mods.items() if call.search(text)]
    _require(
        readers == ["adapter"], f"store.load() called outside adapter.py: {readers}"
    )


def exit_code_is_the_verdict() -> None:
    """nemik-check exits 1 exactly when a Violation is found, 0 otherwise."""
    text = _src("check.py")
    _require(
        "sys.exit(1 if failed else 0)" in text,
        "nemik-check's exit code is no longer 1-iff-Violation",
    )


def provenance_lines_are_stable() -> None:
    """Keep the provenance line prefixes of nemik-check where they are."""
    text = _src("check.py")
    _require(
        'f"provenance: nemik {sha' in text, "the nemik provenance line prefix moved"
    )
    _require(
        'f"provenance: queue {repo}' in text,
        "the per-queue provenance line prefix moved",
    )


def unclaimed_is_a_literal_other_repos_grep() -> None:
    """Keep the UNCLAIMED literal that other repos' tick loops grep for."""
    text = _src("blocks_cli.py")
    _require(
        '"UNCLAIMED"' in text,
        "the UNCLAIMED literal other repos' tick loops grep for is gone",
    )


def symbol_pattern_is_enforced() -> None:
    """shapes.ttl still enforces the W<n> symbol pattern."""
    shapes = (SRC / "data" / "shapes.ttl").read_text()
    _require(
        'sh:pattern "^W[0-9]+$"' in shapes,
        "the W<n> symbol pattern shape changed or was removed",
    )


def hermetic_vendoring() -> None:
    """pyproject.toml pins mikemol-pathsforward to a local vendored path."""
    pyproject = (ROOT / "pyproject.toml").read_text()
    m = re.search(r"mikemol-pathsforward\s*=\s*\{\s*path\s*=", pyproject)
    _require(
        m,
        "mikemol-pathsforward is no longer pinned to a local vendored path (H1 hermeticity)",
    )


def cross_repo_citation_form() -> None:
    """Citations resolve to urn:nemik:<repo>/W<n>, foreign ones to their own repo."""
    got = str(reference_uri("alpha", "beta:W3"))
    _require(
        got == "urn:nemik:beta/W3", f"foreign-symbol resolution changed shape: {got}"
    )
    got = str(reference_uri("alpha", "W7"))
    _require(
        got == "urn:nemik:alpha/W7", f"local-symbol resolution changed shape: {got}"
    )


# -- standards ------------------------------------------------------------------------------------


def oslc_cm_state_vocabulary() -> None:
    """oslc_cm:state holds nemik's five-value vocabulary, set by queue_graph()."""
    # oslc_cm:state is the OSLC CM property; its five values are nemik's own vocabulary (mtools'
    # status strings have no OSLC CM state URIs of their own to map onto).

    _require(
        set(STATE) == {"ready", "working", "blocked", "landed", "done"},
        f"STATE keys drifted: {set(STATE)}",
    )
    _require(
        all(str(v).startswith(str(NEMIK)) for v in STATE.values()),
        "a STATE value left nemik's own namespace",
    )
    adapter_src = _src("adapter.py")
    _require(
        "g.add((node, OSLC_CM.state, STATE.get(status" in adapter_src,
        "queue_graph() no longer asserts state through the oslc_cm:state property",
    )
    _require(
        OSLC_CM,
        "the OSLC_CM namespace is gone or empty: the state vocabulary has nothing to hang on",
    )


def prov_activity_shape() -> None:
    """ledger_graph() models each tick as a PROV Activity (started, used)."""
    text = _src("adapter.py")
    for term in ("PROV.Activity", "PROV.startedAtTime", "PROV.used"):
        _require(term in text, f"ledger_graph() dropped {term}")


def prometheus_label_format() -> None:
    """metrics.label renders labels as {repo="alpha",state="ready"}."""
    got = label(repo="alpha", state="ready")
    _require(
        got == '{repo="alpha",state="ready"}', f"Prometheus label format changed: {got}"
    )


def shacl_is_the_one_validator() -> None:
    """Only shaclinc.py imports pyshacl; check.py calls it."""
    mods = _modules()
    users = [
        name
        for name, text in mods.items()
        if re.search(r"^from pyshacl import|^import pyshacl", text, re.MULTILINE)
    ]
    # nemik:W400: the one importer is shaclinc.py (incremental validation); check.py calls it.
    _require(users == ["shaclinc"], f"pyshacl imported outside shaclinc.py: {users}")


# -- modularity -----------------------------------------------------------------------------------


def adapter_is_the_foundation_layer() -> None:
    """adapter.py imports no other nemik module."""
    _require(
        not _imports_nemik(_src("adapter.py")),
        "adapter.py now depends on another nemik module",
    )


def adoption_has_no_internal_coupling() -> None:
    """adoption.py imports no other nemik module."""
    _require(
        not _imports_nemik(_src("adoption.py")),
        "adoption.py picked up a dependency on another nemik module",
    )


def hub_modules_depend_on_everything_below() -> None:
    """Hold metrics and serve to exactly their declared set of nemik modules."""
    mods = _modules()
    lower = {"adapter", "blocks", "wake", "check"}
    # nemik:W232: nemik-metrics also reads the realizability verdicts, through realize.py, which
    # itself rests on adapter alone; serve does not.
    # nemik:W354: serve also publishes the outbox, a renderer that rests on adapter alone.
    # nemik:W634: and applies the per-repo exports' withholding, through exportwire, which rests on
    # check and exportv2 (a leaf that reads one JSON file).
    # nemik:W670: and serves luthen's series snapshot as a board, through luthenseries, a leaf that
    # reads one JSON file.
    # nemik:W485: and counts the ledger ticks by the kind of card worked, through workrows, a leaf
    # that imports only json.
    # nemik:W780: and serves the host-root frontier nemik-hostroot writes, through hostroot, a leaf
    # that reads that one document (its only nemik import is climate's stamp reader).
    # nemik:W751: and serves the commit landings nemik-hostroot --landings writes, through
    # landings, a leaf that rests on hostroot's flat-JSON reader alone.
    # nemik:W786: and answers /critical.json with critical_doc, as nemik-critical --json does.
    # nemik:W853: and answers /oldest.json with history.oldest_rows, the function nemik-history
    # --oldest calls (it reads queue files and a liveness record and starts no process).
    # nemik:W854: and answers /history/<mode>.json from the documents nemik-history --publish
    # writes, through histdocs, a leaf of plain text that reads no file.
    # nemik:W862: and answers /check/letters.json and /check/fold.json with letters.report, the
    # function nemik-check --letters and --fold print (a leaf of stdlib file reads).
    # nemik:W864: and answers /collapse.json with collapse.lines, as nemik-collapse prints it (a
    # leaf of pure functions over the blocked rows).
    # nemik:W931: and answers /queue.json with queuerows.fleet_queues: each repo's ready cards in
    # rank's order, with their wait and the newer cards ranked ahead of them.
    # nemik:W990: and publishes the ratchet pace board and gauges, through pacepublish, a leaf that
    # rests on hostroot's flat-JSON reader alone.
    # nemik:W1025: and publishes the round gauges, through roundgauges (a reader of the round file
    # over pacepublish's timestamp, roundfile's gauge lines and roundof's drift), and names the file
    # by roundfile's ROUND_FILE.
    # nemik:W1138: and publishes one series per open card, through cardseries, a leaf that rests on
    # pacepublish's timestamp reader alone.
    # nemik:W1167: and names each repo's round binding term, through roundcli.bindings_of (the
    # round's width over the supply and the landed stacks) and stackable's manifest reader.
    # nemik:W1179: and reads each repo's burn-down tier from rank.TIERS, since tiers.py no longer
    # reads the file itself (rank.load_tiers does, so tiers compiles on Codon); rank rests on
    # adapter and the lower stack.
    # nemik:W1335: and gathers the fleet's recorded gaps for nemik-rank --flow --residue, through
    # residue.by_card (a pure function of the judged verdicts, so it compiles under Codon).
    # nemik:W1323: and counts each repo's stackable ready cards for the nemik_stackable gauge,
    # through stackable.stackable_count (the function nemik-stackable's report uses).
    # nemik:W1384: and both write their command output through say, a leaf that imports only sys.
    # nemik:W1561: the function-local imports of both hubs moved to module level (PLC0415), so the
    # set also names what they imported inside functions: health and stackable_cli for metrics.
    expected = {
        "metrics": lower
        | {
            "realize",
            "runlogs",
            "workrows",
            "rank",
            "stackable",
            "say",
            "health",
            "stackable_cli",
            "score",
        },
        "serve": lower
        | {
            "outbox",
            "exportwire",
            "runlogs",
            "withheldage",
            "luthenseries",
            "hostroot",
            "landings",
            "critical",
            "starved",
            "queuerows",
            "overlaps",
            "pacing",
            "floorasks",
            "history",
            "histdocs",
            "letters",
            "collapse",
            "pacepublish",
            "roundcli",
            "roundfile",
            "roundgauges",
            "buildcost",
            "cardseries",
            "stackable",
            "say",
            "apischema",
            "catalog",
            "health",
            "index",
            "pieces",
            "rank",
            "salience",
            "score",
            "trs",
            "withheld",
        },
    }
    for hub, want in expected.items():
        deps = _imports_nemik(mods[hub])
        _require(deps == want, f"{hub}.py's dependency set changed: {deps}")


def import_graph_is_acyclic() -> None:
    """No nemik module reaches itself through the import graph."""
    mods = _modules()
    graph = {name: _imports_nemik(text) for name, text in mods.items()}

    def reaches(a: str, b: str, seen: frozenset[str] = frozenset()) -> bool:
        if a in seen:
            return False
        return b in graph[a] or any(reaches(dep, b, seen | {a}) for dep in graph[a])

    for name in graph:
        _require(not reaches(name, name), f"a cycle passes through {name}.py")


def rdf_is_not_centralized_behind_adapter() -> None:
    """Two or more modules besides adapter.py import rdflib: the declared gap."""
    # The honest modularity gap: rdflib is a shared foundation library every module reaches for
    # directly, not a dependency adapter.py alone encapsulates.
    mods = _modules()
    direct_importers = [
        name
        for name, text in mods.items()
        if name != "adapter"
        and re.search(r"^from rdflib|^import rdflib", text, re.MULTILINE)
    ]
    _require(
        len(direct_importers) >= MIN_DIRECT_RDFLIB_IMPORTERS,
        f"rdflib turned out to be centralized after all: {direct_importers}",
    )


def no_versioned_schema() -> None:
    """shapes.ttl carries no version marker: no version is negotiated."""
    # The claim is an absence: no version negotiation between shapes.ttl and its consumers.
    # Falsifiable both ways -- this fails the moment someone adds one, which is the point.
    # nemik:W465: staging one shape at sh:Info is nemik's own per-shape choice, not a version a
    # workstream can pin, so it no longer counts against the claim (the claim's text says so).
    shapes = (SRC / "data" / "shapes.ttl").read_text()
    for marker in ("owl:versionInfo", "schemaVersion", "shapesVersion"):
        _require(
            marker not in shapes,
            f"{marker} found in shapes.ttl -- update this claim, it may no longer hold",
        )


def nemik_never_writes_a_queue() -> None:
    """No nemik module calls the writer's store.save, write_atomic or ledger.write."""
    # mikemol.pathsforward.store exposes save()/write_atomic() alongside load(); nemik's own
    # source never calls either, so this package is read-only with respect to the fleet's state.
    # Word-bounded: nemik.cachestore.save() (W518) writes the build's own caches, never a queue.
    for name, text in _modules().items():
        for writer in ("store.save(", "store.write_atomic(", "ledger.write("):
            call = re.compile(r"(?<![A-Za-z0-9_])" + re.escape(writer))
            _require(
                not call.search(text),
                f"{name}.py calls {writer} -- nemik is no longer read-only",
            )


def check_py_bypasses_the_adapter_boundary() -> None:
    """check.py imports UnreadableStateError directly; adapter.py does not re-export."""
    # The honest exception to single_writer_boundary()'s isolation claim: check.py imports an
    # mtools exception TYPE directly, rather than through a re-export adapter.py provides.
    text = _src("check.py")
    _require(
        "from mikemol.pathsforward.store import UnreadableStateError" in text,
        "check.py no longer bypasses adapter.py for this import "
        "-- update the claim, don't just delete it",
    )
    _require(
        "import UnreadableStateError" not in _src("adapter.py"),
        "adapter.py now re-exports this exception -- the leak this claim documents may be closed",
    )


CLAIMS = {
    "single-writer-boundary": single_writer_boundary,
    "exit-code-is-the-verdict": exit_code_is_the_verdict,
    "provenance-lines-are-stable": provenance_lines_are_stable,
    "unclaimed-is-a-literal": unclaimed_is_a_literal_other_repos_grep,
    "symbol-pattern-is-enforced": symbol_pattern_is_enforced,
    "hermetic-vendoring": hermetic_vendoring,
    "cross-repo-citation-form": cross_repo_citation_form,
    "oslc-cm-state-vocabulary": oslc_cm_state_vocabulary,
    "prov-activity-shape": prov_activity_shape,
    "prometheus-label-format": prometheus_label_format,
    "shacl-is-the-one-validator": shacl_is_the_one_validator,
    "adapter-is-the-foundation-layer": adapter_is_the_foundation_layer,
    "adoption-has-no-internal-coupling": adoption_has_no_internal_coupling,
    "hub-modules-depend-on-everything-below": hub_modules_depend_on_everything_below,
    "import-graph-is-acyclic": import_graph_is_acyclic,
    "rdf-is-not-centralized-behind-adapter": rdf_is_not_centralized_behind_adapter,
    "check-py-bypasses-the-adapter-boundary": check_py_bypasses_the_adapter_boundary,
    "nemik-never-writes-a-queue": nemik_never_writes_a_queue,
    "no-versioned-schema": no_versioned_schema,
}


def main(argv: list[str]) -> int:
    """Run one claim check by key.

    Args:
        argv: The command line after the program name: exactly one claim key.

    Returns:
        0 when the claim holds, 1 when it fails, 2 for a missing or unknown key.

    """
    if len(argv) != 1 or argv[0] not in CLAIMS:
        sys.stderr.write(f"usage: claims.py <{'|'.join(CLAIMS)}>\n")
        return 2
    try:
        CLAIMS[argv[0]]()
    except AssertionError as exc:
        sys.stderr.write(f"claims.py: {argv[0]}: {exc}\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
