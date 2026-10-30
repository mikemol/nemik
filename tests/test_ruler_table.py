# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W418: graph.json ships the ruler patterns from mtools' generator, enough for every line."""

from pathlib import Path
from typing import TYPE_CHECKING

from mikemol.rulerseq import morse_motif

from nemik.serve import Model, ruler_table

if TYPE_CHECKING:
    from nemik.blocks import AskRow


def test_the_table_is_mtools_generator_and_decodes_by_length() -> None:
    """The table is mtools generator and decodes by length."""
    edges = [{"source": f"s{i}", "target": "t", "kind": "waits"} for i in range(5)] + [
        {"source": "x", "target": "t", "kind": "enables"}
    ]
    asks: list[AskRow] = [{"category": "needs-you", "ref": "r:W1"}] * 7
    table = ruler_table(edges, asks)
    assert table["motif"] == [morse_motif(k) for k in range(4)]
    assert len(table["f"]) == 8  # the 7 asks in one chip outnumber the 5 lines into t
    assert [len(p) for p in table["f"]] == list(
        range(8)
    )  # F(n) has length n: it decodes
    assert len(set(table["f"])) == 8  # injective


def test_the_fixture_graph_covers_every_line_it_draws() -> None:
    """The fixture graph covers every line it draws."""
    model = Model(Path(__file__).parent / "fixtures" / "fleet")
    model.refresh()
    doc = model.doc
    waits = [e for e in doc["edges"] if e["kind"] == "waits"]
    widest = max(
        (
            sum(1 for e in waits if e["target"] == t)
            for t in {e["target"] for e in waits}
        ),
        default=0,
    )
    assert len(doc["ruler"]["f"]) > widest
