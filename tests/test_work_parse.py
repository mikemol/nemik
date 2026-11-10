# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2126: the hand-written nemik-work parser gives what argparse gave, on a corpus of argv.

argparse is a Codon wall, so `nemik.work.parse` reads the command line by hand. The oracle is the
argparse parser it replaced, rebuilt here with the same arguments: for every argv below, the
parsed (symbol, state, dry_run, force) must be equal, or both must exit with the same status.
Messages are not compared.
"""

import argparse
from pathlib import Path

import pytest

from nemik.work import parse

DEFAULT = ".claude/paths-forward.json"
CORPUS = [
    ["W1"],
    ["W1", "--force"],
    ["--force", "W1"],
    ["W1", "--dry-run", "--force"],
    ["W1", "--state", "q.json"],
    ["--state", "q.json", "W1"],
    ["W1", "--state=q.json"],
    ["--state=q.json", "W1"],
    ["W1", "--state="],
    ["W1", "--dry"],
    ["W1", "--dr", "--fo"],
    ["W1", "--f"],
    ["W1", "--st", "x"],
    ["W1", "--s", "x"],
    ["W1", "--d"],
    ["W1", "--force", "--force"],
    ["W1", "--state", "a", "--state", "b"],
    ["W1", "--state", "-"],
    ["W1", "-"],
    ["-"],
    [],
    ["--force"],
    ["--state", "W1"],
    ["W1", "W2"],
    ["W1", "--state"],
    ["W1", "--state", "--force"],
    ["W1", "--bogus"],
    ["W1", "-x"],
    ["W1", "--dry-run=1"],
    ["W1", "--force=yes"],
    ["--", "W1"],
    ["--", "--force"],
    ["W1", "--", "--force"],
    ["--force", "--", "W1"],
    ["-h"],
    ["--help"],
    ["--he"],
    ["W1", "-h"],
    ["W1", "--help"],
]


class _Reference(argparse.Namespace):
    """The namespace argparse fills, typed so no attribute read is Any (the house mypy config)."""

    symbol: str
    state: Path
    dry_run: bool
    force: bool


def _reference(argv: list[str]) -> tuple[str, Path, bool, bool] | int:
    ap = argparse.ArgumentParser(prog="nemik-work")
    ap.add_argument("symbol")
    ap.add_argument("--state", type=Path, default=Path(DEFAULT))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    try:
        ns = ap.parse_args(argv, namespace=_Reference())
    except SystemExit as stop:
        return int(stop.code or 0)
    return ns.symbol, ns.state, ns.dry_run, ns.force


def _mine(argv: list[str]) -> tuple[str, Path, bool, bool] | int:
    try:
        out = parse(argv)
    except SystemExit as stop:
        return int(stop.code or 0)
    return out.symbol, out.state, out.dry_run, out.force


@pytest.mark.parametrize("argv", CORPUS, ids=[" ".join(a) or "empty" for a in CORPUS])
def test_the_hand_parser_gives_what_argparse_gave(argv: list[str]) -> None:
    """The same namespace, or the same exit status, as the argparse parser it replaced."""
    assert _mine(argv) == _reference(argv)


def test_the_defaults_are_the_old_defaults() -> None:
    """With only a symbol, the queue file is the one in this directory and nothing is forced."""
    out = parse(["W7"])
    assert (out.symbol, out.state, out.dry_run, out.force) == (
        "W7",
        Path(DEFAULT),
        False,
        False,
    )
