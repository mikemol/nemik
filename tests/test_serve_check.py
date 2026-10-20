# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W792: /check.json says what nemik-check says, from the same wording."""

from pathlib import Path

from nemik.check import survey_lines
from nemik.serve import Model

FLEET = Path(__file__).parent / "fixtures" / "fleet"


def _served() -> dict[str, object]:
    """Build the model over the fixture fleet and take its check document.

    Returns:
        Model.check_doc() after one refresh.

    """
    model = Model(FLEET)
    model.refresh()
    return model.check_doc()


def test_the_served_lines_are_the_clis_lines() -> None:
    """Same survey, same wording: the lines and the failure count match nemik-check's."""
    lines, failed, _ = survey_lines(FLEET, digest=False)
    served = _served()
    assert served["lines"] == lines
    assert served["failed"] == failed


def test_the_served_digest_is_the_clis_digest() -> None:
    """nemik-check --digest's lines are served beside the full ones."""
    lines, _, _ = survey_lines(FLEET, digest=True)
    assert _served()["digest"] == lines
