# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W365: cards as MS Project XML (MSPDI), read by MS Project, ProjectLibre and GanttProject.

A serializer over nemik.projection (W413), nothing more: each Task becomes a <Task>, each predecessor
a <PredecessorLink> of Type 1 (finish-to-start, Microsoft's schema reference: 0 FF, 1 FS, 2 SF, 3 SS).
A predecessor inside the file is named by its PredecessorUID; one outside it (another repo, when one
repo is exported) is a cross-project link, CrossProject 1 with CrossProjectName its repo, and its cite
in the link's own text is kept so `read` gives back exactly what was written.

nemik has no durations or dates, so none are invented: a task carries only its UID, ID, name, the cite
(as a text field), and PercentComplete 100 when the card is done.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from nemik.projection import Link, Task

NS = "http://schemas.microsoft.com/project"
FS = "1"  # PredecessorLink Type: finish-to-start
# Text1, the task field the cite rides in: "the FieldID 188743731 matches the pjCustomTaskText1 value"
# (Microsoft Learn, FieldID Element, fetched 2026-10-12).
CITE_FIELD = "188743731"


def _sub(parent: ET.Element, tag: str, text: str) -> ET.Element:
    el = ET.SubElement(parent, f"{{{NS}}}{tag}")
    el.text = text
    return el


def write(tasks: list[Task], name: str = "nemik") -> str:
    """The MSPDI document for `tasks`."""
    ET.register_namespace("", NS)
    project = ET.Element(f"{{{NS}}}Project")
    _sub(project, "Name", name)
    attrs = ET.SubElement(project, f"{{{NS}}}ExtendedAttributes")
    attr = ET.SubElement(attrs, f"{{{NS}}}ExtendedAttribute")
    _sub(attr, "FieldID", CITE_FIELD)
    _sub(attr, "FieldName", "Text1")
    _sub(attr, "Alias", "nemik cite")
    uid = {t.cite: t.uid for t in tasks}
    root = ET.SubElement(project, f"{{{NS}}}Tasks")
    for t in tasks:
        task = ET.SubElement(root, f"{{{NS}}}Task")
        _sub(task, "UID", str(t.uid))
        _sub(task, "ID", str(t.uid))
        _sub(task, "Name", t.name)
        _sub(task, "PercentComplete", "100" if t.done else "0")
        for link in t.preds:
            pl = ET.SubElement(task, f"{{{NS}}}PredecessorLink")
            if link.cite in uid:
                _sub(pl, "PredecessorUID", str(uid[link.cite]))
            else:
                _sub(pl, "CrossProject", "1")
                _sub(
                    pl,
                    "CrossProjectName",
                    f"{link.cite.partition(':')[0]}\\{link.cite}",
                )
            _sub(pl, "Type", FS)
        ext = ET.SubElement(task, f"{{{NS}}}ExtendedAttribute")
        _sub(ext, "FieldID", CITE_FIELD)
        _sub(ext, "Value", t.cite)
    ET.indent(project)
    return ET.tostring(project, encoding="unicode", xml_declaration=True)


def main(argv: list[str] | None = None) -> None:
    """nemik-export: the fleet's cards (or one repo's) as MSPDI on stdout, read-only."""
    import argparse
    import sys
    from pathlib import Path

    from rdflib import Graph

    from nemik.adapter import queue_graph
    from nemik.blocks import annotate
    from nemik.check import QUEUE, default_root, workstream_files
    from nemik.projection import project

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
    args = ap.parse_args(argv)
    queues = workstream_files(args.root, QUEUE)
    known = frozenset(r for r, _ in queues)
    g = Graph()
    for repo, path in queues:
        g += queue_graph(repo, path, known)
    annotate(g)
    tasks = project(g, set(args.repo) if args.repo else None)
    if args.format == "issues":
        from nemik import issues

        sys.stdout.write(issues.write(tasks))
        return
    sys.stdout.write(write(tasks, ",".join(args.repo) if args.repo else "nemik"))


def read(text: str) -> list[Task]:
    """The tasks an MSPDI document written by `write` holds (for the round-trip test)."""
    q = {"p": NS}
    project = ET.fromstring(text)
    rows = project.findall("p:Tasks/p:Task", q)
    cite_of = {
        r.findtext("p:UID", "", q): r.findtext("p:ExtendedAttribute/p:Value", "", q)
        for r in rows
    }
    tasks = []
    for r in rows:
        cite = r.findtext("p:ExtendedAttribute/p:Value", "", q)
        links = []
        for pl in r.findall("p:PredecessorLink", q):
            if pl.findtext("p:CrossProject", "0", q) == "1":
                other = pl.findtext("p:CrossProjectName", "", q).partition("\\")[2]
                links.append(Link(other, True))
            else:
                other = cite_of[pl.findtext("p:PredecessorUID", "", q)]
                links.append(
                    Link(other, other.partition(":")[0] != cite.partition(":")[0])
                )
        tasks.append(
            Task(
                uid=int(r.findtext("p:UID", "0", q)),
                cite=cite,
                name=r.findtext("p:Name", "", q),
                done=r.findtext("p:PercentComplete", "0", q) == "100",
                preds=tuple(links),
            )
        )
    return tasks
