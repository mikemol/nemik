# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1043: nemik-rank reads the graphs and never asks the survey for its findings."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from nemik import check, rank


def test_the_ranking_asks_the_survey_for_graphs_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The SHACL pass was most of a ranking's cost and the ranking never reads its findings."""
    asked: list[bool] = []

    def survey(
        root: Path, *, check: bool = True
    ) -> Iterator[tuple[str, None, list[str]]]:
        """Record whether the findings were asked for, and read no queue.

        Returns:
            An empty survey.

        """
        del root
        asked.append(check)
        return iter([])

    monkeypatch.setattr(check, "survey", survey)
    rank.main(["nemik", "--root", str(tmp_path)])
    assert asked == [False]
