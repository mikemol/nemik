# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W795: the served ready-neither and unmanifested reports are the CLI's own text."""

from pathlib import Path

import pytest

from nemik.check import ready_neither_report, unmanifested_report
from nemik.serve import Model, check_report

FLEET = Path(__file__).parent / "fixtures" / "fleet"


def _model() -> Model:
    """Build the model over the fixture fleet.

    Returns:
        The model, refreshed once.

    """
    model = Model(FLEET)
    model.refresh()
    return model


def test_the_served_ready_neither_report_is_the_clis(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Same function, same words: nemik-check --ready-neither prints what the route serves."""
    ready_neither_report(FLEET, None)
    printed = capsys.readouterr().out
    assert check_report("ready-neither", _model().graph, FLEET) == printed


def test_the_served_unmanifested_report_is_the_clis(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """nemik-check --unmanifested prints what the route serves."""
    unmanifested_report(FLEET)
    printed = capsys.readouterr().out
    assert check_report("unmanifested", _model().graph, FLEET) == printed


def test_a_name_that_is_no_report_is_none() -> None:
    """The route answers 404 for it."""
    assert check_report("nonsense", _model().graph, FLEET) is None
