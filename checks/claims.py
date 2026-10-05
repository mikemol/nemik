#!/usr/bin/env python3
"""Per-claim discriminating witnesses -- the `claim:` check type (registered in
paper.toml as `[checks.claim] cmd = "python3 checks/claims.py {target}"`).

Each function asserts the SPECIFIC proposition its claim makes about nemik's source, so a claim
that goes false as the code changes fails its own check rather than a shared one standing in for
several claims. Run from the repo root (paperkit's `root = "."` in paper.toml puts cwd there):

    python3 checks/claims.py <claim-key>      # exit 0 = claim holds
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "nemik"
sys.path.insert(0, str(ROOT / "src"))


def _src(name: str) -> str:
    return (SRC / name).read_text()


def _modules() -> dict[str, str]:
    return {p.stem: p.read_text() for p in SRC.glob("*.py") if p.stem != "__init__"}


def _imports_nemik(text: str) -> set[str]:
    return {
        m.group(1)
        for m in re.finditer(r"^from nemik\.(\w+) import", text, re.MULTILINE)
    }


# -- guarantees ---------------------------------------------------------------------------------


def single_writer_boundary():
    # adapter.py is the ONE module that parses the state file (through mtools' store.load); no
    # other module re-implements that parse.
    mods = _modules()
    readers = [
        name
        for name, text in mods.items()
        if "store.load(" in text or "store.load (" in text
    ]
    assert readers == ["adapter"], f"store.load() called outside adapter.py: {readers}"


def exit_code_is_the_verdict():
    text = _src("check.py")
    assert "sys.exit(1 if failed else 0)" in text, (
        "nemik-check's exit code is no longer 1-iff-Violation"
    )


def provenance_lines_are_stable():
    text = _src("check.py")
    assert 'f"provenance: nemik {sha' in text, "the nemik provenance line prefix moved"
    assert 'f"provenance: queue {repo}' in text, (
        "the per-queue provenance line prefix moved"
    )


def unclaimed_is_a_literal_other_repos_grep():
    text = _src("blocks_cli.py")
    assert '"UNCLAIMED"' in text, (
        "the UNCLAIMED literal other repos' tick loops grep for is gone"
    )


def symbol_pattern_is_enforced():
    shapes = (SRC / "data" / "shapes.ttl").read_text()
    assert 'sh:pattern "^W[0-9]+$"' in shapes, (
        "the W<n> symbol pattern shape changed or was removed"
    )


def hermetic_vendoring():
    pyproject = (ROOT / "pyproject.toml").read_text()
    m = re.search(r"mikemol-pathsforward\s*=\s*\{\s*path\s*=", pyproject)
    assert m, (
        "mikemol-pathsforward is no longer pinned to a local vendored path (H1 hermeticity)"
    )


def cross_repo_citation_form():
    from nemik.adapter import reference_uri

    got = str(reference_uri("alpha", "beta:W3"))
    assert got == "urn:nemik:beta/W3", f"foreign-symbol resolution changed shape: {got}"
    got = str(reference_uri("alpha", "W7"))
    assert got == "urn:nemik:alpha/W7", f"local-symbol resolution changed shape: {got}"


# -- standards ------------------------------------------------------------------------------------


def oslc_cm_state_vocabulary():
    # oslc_cm:state is the OSLC CM property; its four values are nemik's own vocabulary (mtools'
    # status strings have no OSLC CM state URIs of their own to map onto).
    from nemik.adapter import NEMIK, OSLC_CM, STATE

    assert set(STATE) == {"ready", "working", "blocked", "done"}, (
        f"STATE keys drifted: {set(STATE)}"
    )
    assert all(str(v).startswith(str(NEMIK)) for v in STATE.values()), (
        "a STATE value left nemik's own namespace"
    )
    adapter_src = _src("adapter.py")
    assert "g.add((node, OSLC_CM.state, STATE.get(status" in adapter_src, (
        "queue_graph() no longer asserts state through the oslc_cm:state property"
    )
    assert OSLC_CM  # imported and actually referenced above, not vestigial


def prov_activity_shape():
    text = _src("adapter.py")
    for term in ("PROV.Activity", "PROV.startedAtTime", "PROV.used"):
        assert term in text, f"ledger_graph() dropped {term}"


def prometheus_label_format():
    from nemik.metrics import label

    got = label(repo="alpha", state="ready")
    assert got == '{repo="alpha",state="ready"}', (
        f"Prometheus label format changed: {got}"
    )


def shacl_is_the_one_validator():
    mods = _modules()
    users = [
        name
        for name, text in mods.items()
        if re.search(r"^from pyshacl import|^import pyshacl", text, re.MULTILINE)
    ]
    assert users == ["check"], f"pyshacl imported outside check.py: {users}"


# -- modularity -----------------------------------------------------------------------------------


def adapter_is_the_foundation_layer():
    assert not _imports_nemik(_src("adapter.py")), (
        "adapter.py now depends on another nemik module"
    )


def adoption_has_no_internal_coupling():
    assert not _imports_nemik(_src("adoption.py")), (
        "adoption.py picked up a dependency on another nemik module"
    )


def hub_modules_depend_on_everything_below():
    mods = _modules()
    for hub in ("metrics", "serve"):
        deps = _imports_nemik(mods[hub])
        assert deps == {"adapter", "blocks", "wake", "check"}, (
            f"{hub}.py's dependency set changed: {deps}"
        )


def import_graph_is_acyclic():
    mods = _modules()
    graph = {name: _imports_nemik(text) for name, text in mods.items()}

    def reaches(a, b, seen=frozenset()):
        if a in seen:
            return False
        return b in graph[a] or any(reaches(dep, b, seen | {a}) for dep in graph[a])

    for name in graph:
        assert not reaches(name, name), f"a cycle passes through {name}.py"


def rdf_is_not_centralized_behind_adapter():
    # The honest modularity gap: rdflib is a shared foundation library every module reaches for
    # directly, not a dependency adapter.py alone encapsulates.
    mods = _modules()
    direct_importers = [
        name
        for name, text in mods.items()
        if name != "adapter"
        and re.search(r"^from rdflib|^import rdflib", text, re.MULTILINE)
    ]
    assert len(direct_importers) >= 2, (
        f"rdflib turned out to be centralized after all: {direct_importers}"
    )


def no_versioned_schema():
    # The claim is an absence: no version negotiation between shapes.ttl and its consumers.
    # Falsifiable both ways -- this fails the moment someone adds one, which is the point.
    shapes = (SRC / "data" / "shapes.ttl").read_text()
    for marker in (
        "owl:versionInfo",
        "schemaVersion",
        "shapesVersion",
        "sh:severity sh:Info",
    ):
        assert marker not in shapes, (
            f"{marker} found in shapes.ttl -- update this claim, it may no longer hold"
        )


def nemik_never_writes_a_queue():
    # mikemol.pathsforward.store exposes save()/write_atomic() alongside load(); nemik's own
    # source never calls either, so this package is read-only with respect to the fleet's state.
    for name, text in _modules().items():
        for writer in ("store.save(", "store.write_atomic(", "ledger.write("):
            assert writer not in text, (
                f"{name}.py calls {writer} -- nemik is no longer read-only"
            )


def check_py_bypasses_the_adapter_boundary():
    # The honest exception to single_writer_boundary()'s isolation claim: check.py imports an
    # mtools exception TYPE directly, rather than through a re-export adapter.py provides.
    text = _src("check.py")
    assert "from mikemol.pathsforward.store import UnreadableStateError" in text, (
        "check.py no longer bypasses adapter.py for this import -- update the claim, don't just delete it"
    )
    assert "import UnreadableStateError" not in _src("adapter.py"), (
        "adapter.py now re-exports this exception -- the leak this claim documents may be closed"
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
    if len(argv) != 1 or argv[0] not in CLAIMS:
        print(f"usage: claims.py <{'|'.join(CLAIMS)}>", file=sys.stderr)
        return 2
    try:
        CLAIMS[argv[0]]()
    except AssertionError as exc:
        print(f"claims.py: {argv[0]}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
