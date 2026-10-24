# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W948: nemik-hostroot --log-activities writes nemik's wait activities, or says why not."""

from pathlib import Path

from nemik.ask import quoted
from nemik.hostroot_cli import main
from nemik.waitlog import activity

FIRST = 1_700_000_000_000_000_000
SECOND = FIRST + 60_000_000_000


def _luthen(root: Path, body: str) -> None:
    """Put a luthen checkout under `root` whose vlogs_query runs `body`."""
    package = root / "luthen-observability" / "checks"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "vlogs_query.py").write_text(body, encoding="utf-8")


def _record(waiting: str, cite: str, blocker: str, at_ns: int, when: str) -> str:
    """Print one wait record the way VictoriaLogs does.

    Returns:
        One line of JSON.

    """
    message = activity(waiting, cite, 3, blocker, at_ns)
    return f'{{"_msg": {quoted(message)}, "_time": {quoted(when)}}}'


def test_the_activities_are_written_per_repo_oldest_first(tmp_path: Path) -> None:
    """Newest-first lines come out as one document: repos sorted, each repo's oldest first."""
    lines = "\n".join(
        [
            _record("beta", "beta:W5", "alpha:W1", SECOND, "2026-10-24T02:01:00Z"),
            _record("alpha", "alpha:W2", "beta:W9", FIRST, "2026-10-24T02:00:00Z"),
            _record("beta", "beta:W6", "alpha:W1", FIRST, "2026-10-24T02:00:00Z"),
        ]
    )
    _luthen(tmp_path, f"print({lines!r})\n")
    out = tmp_path / "log-activities.json"
    code = main(["--root", str(tmp_path), "--log-activities", "--out", str(out)])
    assert code == 0
    text = out.read_text(encoding="utf-8")
    assert text.index('"alpha": [') < text.index('"beta": [')
    assert text.index("beta:W6 has waited") < text.index("beta:W5 has waited")
    assert text.count('"type": "Update"') == len(lines.splitlines())
    assert '"as_of": "' in text


def test_an_answer_with_no_wait_activity_writes_nothing(tmp_path: Path) -> None:
    """With nothing readable, exit 1 and no file, so a stale document is not refreshed."""
    _luthen(tmp_path, 'print("not json")\n')
    out = tmp_path / "log-activities.json"
    code = main(["--root", str(tmp_path), "--log-activities", "--out", str(out)])
    assert code == 1
    assert not out.exists()
