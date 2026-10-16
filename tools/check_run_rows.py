# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W557/W558: how many rows of a run log (JSON lines) pass src/nemik/data/run-row.schema.json.

    check_run_rows.py LOG.jsonl [--last N]

Prints the failures grouped by their first reason, then the pass and fail counts. Exit 0 when
every row checked passes, 1 when any fails, 2 when the log cannot be read.
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import jsonschema

SCHEMA = Path(__file__).resolve().parents[1] / "src/nemik/data/run-row.schema.json"
UNREADABLE = 2


def main(argv: list[str] | None = None) -> int:
    """Validate the rows of one log against the run-row schema.

    Args:
        argv: The command line after the program name, or None for sys.argv.

    Returns:
        0 when every row passes, 1 when any fails, 2 when the log cannot be read.

    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument(
        "--last", type=int, default=0, help="check only the last N rows"
    )
    args = parser.parse_args(argv)
    try:
        lines = args.log.read_text(encoding="utf-8").splitlines()
    except OSError as err:
        sys.stderr.write(f"check_run_rows: cannot read {args.log}: {err}\n")
        return UNREADABLE
    if args.last:
        lines = lines[-args.last :]
    validator = jsonschema.Draft202012Validator(
        json.loads(SCHEMA.read_text(encoding="utf-8")),
        format_checker=jsonschema.FormatChecker(),
    )
    passed = 0
    reasons: Counter[str] = Counter()
    for line in lines:
        try:
            errors = list(validator.iter_errors(json.loads(line)))
        except ValueError:
            reasons["not JSON"] += 1
            continue
        if errors:
            reasons[errors[0].message[:120]] += 1
        else:
            passed += 1
    for reason, count in reasons.most_common():
        sys.stdout.write(f"{count:6d} rows: {reason}\n")
    sys.stdout.write(f"{passed} pass, {sum(reasons.values())} fail\n")
    return 1 if reasons else 0


if __name__ == "__main__":
    raise SystemExit(main())
