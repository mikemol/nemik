# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""atomize_walls: card the Codon walls so the graph ranks the levers (nemik:W1678, W1411).

One wall card per blocker kind found in any baseline module's import closure, one row card per
baseline module blocked on the wall cards of its closure (tools/codon_closure.py). The graph's
downstream weight then ranks each wall by the rows under it, so no table has to be read by hand.

Idempotent by title: a card whose exact title already exists is reused and its manifest and blockers
are written again, so a partial run is finished by running it again. Without `--apply` it prints the
plan and writes nothing; with it, everything goes through the paths-forward writer, never the file.

Run from the repo root: `python3 tools/atomize_walls.py [--apply]`.
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import NamedTuple

from codon_closure import Row, closure, own_row
from mikemol.procrun.proc import capture

STATE = ".claude/paths-forward.json"
MERGE = {"@dataclass": "dataclass", "dataclasses": "dataclass"}
WHAT = {
    "mikemol": "the mikemol libraries",
    "typing.TYPE_CHECKING": "TYPE_CHECKING blocks",
    "collections.abc": "collections.abc imports",
    "importlib": "importlib.resources and importlib.metadata",
    "dataclass": "the dataclass decorator and import",
    "datetime.UTC": "datetime.UTC",
    "http": "http.client",
    "xml": "xml.etree",
    "google": "the protobuf message import",
}
SMALL, MEDIUM = 3, 12
QUEUE_LINE = re.compile(r"^\s*\d+\.\s+(W\d+)\s+\S+\s+(.*?)(?:\s+—\s.*)?$")


class Spec(NamedTuple):
    """One card to write: its title, manifest and size, and the wall kinds it waits on."""

    title: str
    manifest: tuple[str, ...]
    size: str
    waits_on: tuple[str, ...]


def kind_of(raw: str) -> str:
    """Name a blocker kind, the decorator and the import of dataclasses being one.

    Returns:
        The merged kind name.

    """
    return MERGE.get(raw, raw)


def wall_title(kind: str) -> str:
    """Give a wall card its title.

    Returns:
        The title, stable across runs so a card is found again by it.

    """
    return f"Codon wall: make the modules that use {WHAT.get(kind, kind)} compile without it"


def row_title(name: str) -> str:
    """Give a row card its title.

    Returns:
        The title, stable across runs.

    """
    return (
        f"Codon row {name}: nemik.{name} compiles under the pinned Codon in both modes"
    )


def size_of(count: int) -> str:
    """Size a wall card by how many modules carry the blocker themselves.

    Returns:
        small, medium or large.

    """
    if count <= SMALL:
        return "small"
    return "medium" if count <= MEDIUM else "large"


def sites_of(rows: dict[str, Row]) -> dict[str, list[str]]:
    """Map each blocker kind to the modules that carry it in their own source.

    Returns:
        {kind: sorted module names}, each module once.

    """
    sites: dict[str, set[str]] = {}
    for name, (own, _deps) in rows.items():
        for raw in own:
            sites.setdefault(kind_of(raw), set()).add(name)
    return {kind: sorted(names) for kind, names in sites.items()}


def needs_of(rows: dict[str, Row], listed: list[str]) -> dict[str, list[str]]:
    """Map each listed module to the blocker kinds anywhere in its closure.

    Returns:
        {module: sorted kinds}.

    """
    return {name: sorted({kind_of(k) for k in closure(rows, name)}) for name in listed}


def plan(rows: dict[str, Row], listed: list[str]) -> tuple[list[Spec], list[Spec]]:
    """Build the wall cards and the row cards.

    Returns:
        (the wall specs, the row specs); a wall waits on nothing, a row on its closure's walls.

    """
    needs = needs_of(rows, listed)
    sites = sites_of(rows)
    kinds = sorted({kind for found in needs.values() for kind in found})
    walls = []
    for kind in kinds:
        files = tuple(f"src/nemik/{m}.py" for m in sites.get(kind, []))
        walls.append(
            Spec(
                wall_title(kind),
                files or ("docs/codon-walls.md",),
                size_of(len(files)),
                (),
            )
        )
    rows_out = [Spec(row_title(name), (), "", tuple(needs[name])) for name in listed]
    return walls, rows_out


def parse_queue(text: str) -> dict[str, str]:
    """Read the writer's --queue listing into {exact title: symbol}.

    Returns:
        The title of each listed card and its symbol; lines of another shape are skipped.

    """
    found: dict[str, str] = {}
    for line in text.splitlines():
        match = QUEUE_LINE.match(line)
        if match:
            found[str(match.group(2)).strip()] = str(match.group(1))
    return found


def minted(said: str) -> str:
    """Read the new symbol from the writer's `W<n> added` answer.

    Returns:
        The symbol, or an empty string when the answer is not that shape.

    """
    match = re.match(r"(W\d+) added", said)
    return str(match.group(1)) if match else ""


def writer(*args: str) -> str:
    """Run the paths-forward writer from this venv and return its output.

    Returns:
        Its stdout; exits the process on a nonzero status.

    """
    done = capture(
        [
            str(Path(sys.executable).parent / "mikemol-paths-forward"),
            "--state",
            STATE,
            *args,
        ]
    )
    if done.returncode:
        sys.exit(
            f"atomize_walls: writer {args[:3]}: rc {done.returncode}: {done.stdout}{done.stderr}"
        )
    return done.stdout


def ensure(title: str, existing: dict[str, str]) -> str:
    """Find the card with this exact title, minting it when there is none.

    Returns:
        The card's symbol.

    """
    if title in existing:
        return existing[title]
    symbol = minted(writer("--add", title))
    if not symbol:
        sys.exit(f"atomize_walls: the writer minted no card for {title!r}")
    existing[title] = symbol
    return symbol


def apply(walls: list[Spec], rows_out: list[Spec], kinds: list[str]) -> None:
    """Write the cards through the writer, reusing any whose title exists.

    Args:
        walls: The wall specs, in the order of `kinds`.
        rows_out: The row specs.
        kinds: The kind name of each wall spec.

    """
    existing = parse_queue(writer("--queue"))
    made = len(existing)
    symbol: dict[str, str] = {}
    for kind, spec in zip(kinds, walls, strict=True):
        symbol[kind] = ensure(spec.title, existing)
        writer(
            "--update", symbol[kind], "--manifest", *spec.manifest, "--size", spec.size
        )
    for spec in rows_out:
        sym = ensure(spec.title, existing)
        blockers = [symbol[k] for k in spec.waits_on]
        writer(
            "--update",
            sym,
            "--status",
            "blocked",
            "--blocked-on",
            *blockers,
            "--blocked-kind",
            "agent",
        )
    sys.stdout.write(f"cards created: {len(existing) - made}\n")


def main() -> int:
    """Print the plan, and with --apply write it.

    Returns:
        0, or 2 when run outside the repo root.

    """
    src, baseline = Path("src/nemik"), Path("codon-baseline.json")
    if not src.is_dir() or not baseline.is_file():
        sys.stderr.write("atomize_walls: run from the repo root\n")
        return 2
    rows = {
        p.stem: own_row(p.read_text(encoding="utf-8"))
        for p in src.glob("*.py")
        if p.stem != "__init__"
    }
    parsed: object = json.loads(baseline.read_text(encoding="utf-8"))
    listed = sorted(str(name) for name in parsed) if isinstance(parsed, dict) else []
    walls, rows_out = plan(rows, listed)
    needs = needs_of(rows, listed)
    kinds = sorted({kind for found in needs.values() for kind in found})
    under = Counter(kind for found in needs.values() for kind in found)
    sys.stdout.write(
        f"{len(walls)} wall cards, {len(rows_out)} row cards, {sum(under.values())} edges\n"
    )
    for kind, count in under.most_common():
        sys.stdout.write(f"  {kind}: under {count} rows\n")
    if "--apply" in sys.argv:
        apply(walls, rows_out, kinds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
