# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W531: nemik-metrics output parses as the Prometheus text format, strictly.

prometheus_client is not a dependency, so a strict reader of the text exposition format stands in
for it here: it accepts HELP and TYPE comment lines and samples with optional labels and
timestamp, and raises on anything else, so a malformed line fails a test instead of a scrape.
"""

import re
from pathlib import Path

import pytest

from nemik.metrics import main

FLEET = Path(__file__).parent / "fixtures" / "fleet"
NAME = r"[a-zA-Z_:][a-zA-Z0-9_:]*"
SAMPLE = re.compile(rf"^({NAME})(?:\{{(.*)\}})?\s+(\S+)(?:\s+(-?\d+))?$")
HELP = re.compile(rf"^# HELP ({NAME}) (.*)$")
TYPE = re.compile(rf"^# TYPE ({NAME}) (counter|gauge|histogram|summary|untyped)$")
LABELS = re.compile(rf'\s*({NAME})="((?:[^"\\]|\\.)*)"\s*(,|$)')

Sample = tuple[str, dict[str, str], float]


def _labels(text: str, number: int) -> dict[str, str]:
    """Read a sample's label set.

    Args:
        text: The text between the braces.
        number: The line number, for the error.

    Returns:
        name -> value, escapes left as written.

    Raises:
        ValueError: The text is not a comma-separated list of name="value".

    """
    out: dict[str, str] = {}
    position = 0
    while position < len(text):
        found = LABELS.match(text, position)
        if found is None:
            message = f"line {number}: bad label set {text!r}"
            raise ValueError(message)
        out[found.group(1)] = found.group(2)
        position = found.end()
    return out


def parse(text: str) -> tuple[dict[str, str], dict[str, str], list[Sample]]:
    """Parse a text exposition strictly.

    Args:
        text: The exposition.

    Returns:
        (HELP text by family, TYPE by family, every sample).

    Raises:
        ValueError: A line is not blank, a HELP or TYPE comment, a comment, or a sample; or a
            sample's value is not a float.

    """
    helps: dict[str, str] = {}
    types: dict[str, str] = {}
    samples: list[Sample] = []
    for number, line in enumerate(text.splitlines(), start=1):
        helped = HELP.match(line)
        typed = TYPE.match(line)
        sample = SAMPLE.match(line)
        if not line.strip():
            continue
        if helped:
            helps[helped.group(1)] = helped.group(2)
        elif typed:
            types[typed.group(1)] = typed.group(2)
        elif sample:
            labels = _labels(sample.group(2) or "", number)
            try:
                value = float(sample.group(3))
            except ValueError as err:
                message = f"line {number}: value {sample.group(3)!r} is not a number"
                raise ValueError(message) from err
            samples.append((sample.group(1), labels, value))
        elif not line.startswith("#") or line.startswith(("# HELP", "# TYPE")):
            message = f"line {number}: not a Prometheus text line: {line!r}"
            raise ValueError(message)
    return helps, types, samples


def test_the_parser_reads_help_type_and_labelled_samples() -> None:
    """A small exposition: the declared families and the samples with their labels."""
    text = (
        "# HELP a_total Things.\n"
        "# TYPE a_total counter\n"
        'a_total{repo="x",note="say \\"hi\\""} 3 1700000000\n'
        "b 1.5\n"
    )
    helps, types, samples = parse(text)
    assert helps == {"a_total": "Things."}
    assert types == {"a_total": "counter"}
    assert samples == [
        ("a_total", {"repo": "x", "note": 'say \\"hi\\"'}, 3.0),
        ("b", {}, 1.5),
    ]


@pytest.mark.parametrize(
    "line",
    ["not a metric line", "a{repo=x} 1", 'a{repo="x" 1', "a one", "# TYPE a bogus"],
)
def test_the_parser_refuses_a_malformed_line(line: str) -> None:
    """Each of these is something a scraper would reject."""
    with pytest.raises(ValueError, match="line 1"):
        parse(line + "\n")


def test_nemik_metrics_output_parses_and_every_family_is_declared(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """Every line parses; every sample belongs to a TYPE'd family; every TYPE has a HELP."""
    main(["--root", str(FLEET), "--spool", str(tmp_path / "none.jsonl")])
    helps, types, samples = parse(capsys.readouterr().out)
    assert samples
    assert not {name for name, _, _ in samples} - set(types)
    assert set(types) <= set(helps)
