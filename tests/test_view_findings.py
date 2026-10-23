# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W787: the view shows the CLI's Warnings and Info, not only Violations."""

from pathlib import Path

from pagetext import page_text

from nemik.serve import Model

FLEET = Path(__file__).parent / "fixtures" / "fleet"


def test_the_payload_carries_every_severity_the_cli_prints() -> None:
    """The findings the page draws come from the same check; Warnings and Info are in them."""
    model = Model(FLEET)
    model.refresh()
    payload = model.payload.decode("utf-8")
    assert '"Info"' in payload
    assert '"Warning"' in payload


def test_the_panel_draws_a_row_for_each_finding_with_its_severity_word() -> None:
    """The row's class and its text both name the severity, so Info is not dropped or hidden."""
    page = page_text()
    assert 'class="finding ${esc(sev)}"' in page
    assert "${esc(sev)} · " in page
    assert "Object.entries(data.findings)" in page


def test_the_panel_filters_nothing_by_severity() -> None:
    """The only filter on findings is the repo toggle (`wants`), never the severity."""
    page = page_text()
    start = page.index("function findings()")
    body = page[start : page.index("}", start)]
    assert "wants(r)" in body
    assert "Violation" not in body
    assert "Info" not in body
