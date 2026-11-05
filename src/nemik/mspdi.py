# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W365: cards as MS Project XML (MSPDI), read by MS Project, ProjectLibre and GanttProject.

A serializer over nemik.projection (W413), nothing more: each Task becomes a <Task>, each
predecessor a <PredecessorLink> of Type 1 (finish-to-start, Microsoft's schema reference: 0 FF, 1
FS, 2 SF, 3 SS). A predecessor inside the file is named by its PredecessorUID; one outside it
(another repo, when one repo is exported) is a cross-project link, CrossProject 1 with
CrossProjectName its repo, and its cite in the link's own text is kept so `read` gives back exactly
what was written.

nemik has no durations or dates, so none are invented: a task carries only its UID, ID, name, the
cite (as a text field), and PercentComplete 100 when the card is done.

nemik:W1633: the XML is read with `xml.parsers.expat` and written as text, through a small tree of
its own (`Node`), not ElementTree: the standard wrappers are the parsers ruff's S rules name as
unsafe on untrusted input. A document with a DOCTYPE is refused outright, so no entity can be
declared and none can expand, whatever expat the interpreter links.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from xml.parsers import expat

from rdflib import Graph

from nemik import issues
from nemik.adapter import queue_graph
from nemik.blocks import annotate
from nemik.check import QUEUE, default_root, workstream_files
from nemik.projection import Link, Task, project

NS = "http://schemas.microsoft.com/project"
FS = "1"  # PredecessorLink Type: finish-to-start
# Text1, the task field the cite rides in: "the FieldID 188743731 matches the pjCustomTaskText1
# value" (Microsoft Learn, FieldID Element, fetched 2026-10-12).
CITE_FIELD = "188743731"
DECLARATION = "<?xml version='1.0' encoding='utf-8'?>"
INDENT = "  "
WHOLE_DOCUMENT = True  # expat's isfinal: the text given is all there is


class Node:
    """One element of an MSPDI document: its local tag, its text and its child elements."""

    def __init__(self, tag: str, text: str = "") -> None:
        """Make an element with no children."""
        self.tag = tag
        self.text = text
        self.kids: list[Node] = []

    def add(self, tag: str, text: str = "") -> Node:
        """Append a child element.

        Returns:
            The new child.

        """
        kid = Node(tag, text)
        self.kids.append(kid)
        return kid

    def under(self, path: str) -> list[Node]:
        """Find the elements a slash-separated path of local tags reaches from here.

        Returns:
            Every element at the end of the path, in document order; none when it breaks off.

        """
        found = [self]
        for tag in path.split("/"):
            found = [kid for node in found for kid in node.kids if kid.tag == tag]
        return found

    def text_at(self, path: str, default: str = "") -> str:
        """Give the text of the first element a path reaches.

        Returns:
            Its text, or `default` when the path reaches nothing.

        """
        found = self.under(path)
        return found[0].text if found else default

    def descendants(self, tag: str) -> list[Node]:
        """Find every element below this one, at any depth, with a local tag.

        Returns:
            The matches in document order.

        """
        return [
            match
            for kid in self.kids
            for match in ([kid] if kid.tag == tag else []) + kid.descendants(tag)
        ]


def _no_doctype(*_declaration: object) -> None:
    # a DOCTYPE is where an entity is declared; refusing it leaves nothing to expand
    message = "an MSPDI document with a DOCTYPE is refused"
    raise ValueError(message)


def parse(text: str) -> Node:
    """Read an XML document into a tree of `Node`, namespaces dropped to their local names.

    A malformed document raises expat's own error, and one with a DOCTYPE raises ValueError.

    Returns:
        The document's root element.

    """
    stack = [Node("")]

    def start(name: str, _attrs: dict[str, str]) -> None:
        stack.append(stack[-1].add(name.rpartition("}")[2]))

    def characters(data: str) -> None:
        stack[-1].text += data

    def end(_name: str) -> None:
        stack.pop()

    parser = expat.ParserCreate(namespace_separator="}")
    parser.StartDoctypeDeclHandler = _no_doctype
    parser.StartElementHandler = start
    parser.CharacterDataHandler = characters
    parser.EndElementHandler = end
    parser.Parse(text, WHOLE_DOCUMENT)
    return stack[0].kids[0]


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _render(node: Node, depth: int, attributes: str = "") -> list[str]:
    pad = INDENT * depth
    head = f"{node.tag}{attributes}"
    if node.kids:
        lines = [f"{pad}<{head}>"]
        for kid in node.kids:
            lines += _render(kid, depth + 1)
        return [*lines, f"{pad}</{node.tag}>"]
    if node.text:
        return [f"{pad}<{head}>{_escape(node.text)}</{node.tag}>"]
    return [f"{pad}<{head} />"]


def write(tasks: list[Task], name: str = "nemik") -> str:
    """Build the MSPDI document for `tasks`.

    Returns:
        The XML text, with a declaration, one Task per task, its predecessor links, and its cite
        in an extended attribute.

    """
    root = Node("Project")
    root.add("Name", name)
    attr = root.add("ExtendedAttributes").add("ExtendedAttribute")
    attr.add("FieldID", CITE_FIELD)
    attr.add("FieldName", "Text1")
    attr.add("Alias", "nemik cite")
    uid = {t.cite: t.uid for t in tasks}
    rows = root.add("Tasks")
    for t in tasks:
        task = rows.add("Task")
        task.add("UID", str(t.uid))
        task.add("ID", str(t.uid))
        task.add("Name", t.name)
        task.add("PercentComplete", "100" if t.done else "0")
        for link in t.preds:
            pl = task.add("PredecessorLink")
            if link.cite in uid:
                pl.add("PredecessorUID", str(uid[link.cite]))
            else:
                pl.add("CrossProject", "1")
                pl.add(
                    "CrossProjectName", f"{link.cite.partition(':')[0]}\\{link.cite}"
                )
            pl.add("Type", FS)
        ext = task.add("ExtendedAttribute")
        ext.add("FieldID", CITE_FIELD)
        ext.add("Value", t.cite)
    return DECLARATION + "\n" + "\n".join(_render(root, 0, f' xmlns="{NS}"'))


def main(argv: list[str] | None = None) -> None:
    """nemik-export: the fleet's cards (or one repo's) as MSPDI on stdout, read-only."""

    class Options(argparse.Namespace):
        """The command line, typed (nemik:W958)."""

        root: Path
        repo: list[str] | None
        format: str
        against: Path | None

    ap = argparse.ArgumentParser(
        prog="nemik-export", description=(__doc__ or "").splitlines()[0]
    )
    ap.add_argument("--root", type=Path, default=default_root())
    ap.add_argument(
        "--repo", action="append", help="export only this repo (repeatable)"
    )
    ap.add_argument(
        "--format",
        choices=("mspdi", "issues"),
        default="mspdi",
        help="mspdi: MS Project XML; issues: issue-tracker JSON (W366)",
    )
    ap.add_argument(
        "--against",
        type=Path,
        default=None,
        help="with --format issues: a tracker's issues as JSON (GitHub or Forgejo); print the "
        "calls a mirror would make against them instead of the issues (W958)",
    )
    args = ap.parse_args(argv, namespace=Options())
    queues = workstream_files(args.root, QUEUE)
    known = frozenset(r for r, _ in queues)
    g = Graph()
    for repo, path in queues:
        g += queue_graph(repo, path, known)
    annotate(g)
    tasks = project(g, set(args.repo) if args.repo else None)
    if args.format == "issues":
        if args.against is not None:
            sys.stdout.write(
                issues.plan_text(tasks, args.against.read_text(encoding="utf-8"))
            )
            return
        sys.stdout.write(issues.write(tasks))
        return
    sys.stdout.write(write(tasks, ",".join(args.repo) if args.repo else "nemik"))


def read(text: str) -> list[Task]:
    """Read the tasks an MSPDI document written by `write` holds (for the round-trip test).

    Returns:
        One Task per Task element: uid, cite, name, done when PercentComplete is 100, and its
        predecessor links, cross-project ones marked as such.

    """
    rows = parse(text).under("Tasks/Task")
    cite_of = {r.text_at("UID"): r.text_at("ExtendedAttribute/Value") for r in rows}
    tasks = []
    for r in rows:
        cite = r.text_at("ExtendedAttribute/Value")
        links = []
        for pl in r.under("PredecessorLink"):
            if pl.text_at("CrossProject", "0") == "1":
                other = pl.text_at("CrossProjectName").partition("\\")[2]
                links.append(Link(other, cross_repo=True))
            else:
                other = cite_of[pl.text_at("PredecessorUID")]
                links.append(
                    Link(other, other.partition(":")[0] != cite.partition(":")[0])
                )
        tasks.append(
            Task(
                uid=int(r.text_at("UID", "0")),
                cite=cite,
                name=r.text_at("Name"),
                done=r.text_at("PercentComplete", "0") == "100",
                preds=tuple(links),
            )
        )
    return tasks
