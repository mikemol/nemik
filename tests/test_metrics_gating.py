# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W355: the git-history families are computed only when asked for by name."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from rdflib import Graph

from nemik.check import Finding, survey
from nemik.metrics import main

FLEET = Path(__file__).parent / "fixtures" / "fleet"
HISTORY = (
    "nemik_cards_completed_24h",
    "nemik_commits_24h",
    "nemik_cards_reopened_24h",
    "nemik_manifest_drift",
    "nemik_umbrella_forecast_days",
    "nemik_unforecastable_cards",
)


def test_a_default_run_leaves_the_history_families_out(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """A plain run does no per-repo git walk, so it stays inside the relay's bound."""
    main(["--root", str(FLEET), "--spool", str(tmp_path / "none.jsonl")])
    out = capsys.readouterr().out
    assert not [name for name in HISTORY if name in out]


def test_naming_a_family_computes_it(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """Asked for by name, the family prints its TYPE line."""
    main(
        [
            "--root",
            str(FLEET),
            "--spool",
            str(tmp_path / "none.jsonl"),
            "--family",
            "nemik_commits_24h",
        ]
    )
    assert "# TYPE nemik_commits_24h gauge" in capsys.readouterr().out


def test_a_run_surveys_the_fleet_once(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """nemik:W632: a plain run paid SHACL twice because it surveyed twice (~275 s each, cold)."""
    calls = _count_surveys(monkeypatch)
    main(["--root", str(FLEET), "--spool", str(tmp_path / "none.jsonl")])
    capsys.readouterr()
    assert calls == [True]


def _count_surveys(monkeypatch: pytest.MonkeyPatch) -> list[bool]:
    """Replace the survey with one that records whether each call asked for the findings.

    Args:
        monkeypatch: The test's patcher.

    Returns:
        The list the calls append to: the `check` argument of each survey.

    """
    calls: list[bool] = []
    real = survey

    def counted(
        root: Path, *, check: bool = True
    ) -> Iterator[tuple[str, Graph | None, list[Finding]]]:
        calls.append(check)
        return real(root, check=check)

    monkeypatch.setattr("nemik.metrics.survey", counted)
    return calls


def _run(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, *families: str
) -> list[str]:
    """Run nemik-metrics over the fixture fleet, naming the families.

    Args:
        capsys: The test's output capture.
        tmp_path: Where the empty event spool is.
        *families: The families to ask for; none means a plain run.

    Returns:
        The output lines.

    """
    argv = ["--root", str(FLEET), "--spool", str(tmp_path / "none.jsonl")]
    for name in families:
        argv += ["--family", name]
    main(argv)
    return capsys.readouterr().out.splitlines()


def test_a_graph_family_alone_reads_the_queues_without_the_findings(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """nemik:W620: nemik_repo_tier needs the cards, not SHACL, so the survey is told to skip it."""
    calls = _count_surveys(monkeypatch)
    lines = _run(capsys, tmp_path, "nemik_repo_tier")
    assert calls == [False]
    assert any(line.startswith("nemik_repo_tier{") for line in lines)


def test_the_findings_family_still_gets_the_findings(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """Asking for nemik_findings keeps the check on."""
    calls = _count_surveys(monkeypatch)
    lines = _run(capsys, tmp_path, "nemik_findings")
    assert calls == [True]
    assert any(line.startswith("nemik_findings{") for line in lines)


def test_families_that_need_no_queue_do_not_survey_at_all(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """The spool and the ledgers are read from files, so no queue is parsed."""
    calls = _count_surveys(monkeypatch)
    lines = _run(capsys, tmp_path, "nemik_prompts_total", "nemik_ledger_lines")
    assert calls == []
    assert "# TYPE nemik_prompts_total counter" in lines


def test_a_one_family_run_prints_what_a_plain_run_prints_for_it(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """Skipping the work must not change the answer."""
    plain = _run(capsys, tmp_path)
    one = _run(capsys, tmp_path, "nemik_repo_tier")
    tier = [line for line in plain if line.startswith("nemik_repo_tier{")]
    assert tier
    assert [line for line in one if line.startswith("nemik_repo_tier{")] == tier
