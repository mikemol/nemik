# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W528: a TZID in the output is defined by a VTIMEZONE (RFC 5545 3.2.19)."""

from typing import Any

from nemik.vtodo import calendar, timezones, vtodos

ZONE = "America/New_York"
ASK: dict[str, Any] = {
    "ref": "life:W21",
    "title": "Resume, approve",
    "category": "needs-you",
    "ask": "operator: decide approve it",
    "waiting": [],
    "same_ask": [],
    "dtstart": f"TZID={ZONE}:20261001T163000",
    "due": f"TZID={ZONE}:20261002T163000",
}


def test_a_tzid_gets_its_vtimezone_before_the_todos() -> None:
    """The zone is defined once, ahead of the first VTODO that names it."""
    text = calendar(vtodos([ASK], {"life"}))
    assert text.count("BEGIN:VTIMEZONE") == 1
    assert f"TZID:{ZONE}" in text
    assert text.index("BEGIN:VTIMEZONE") < text.index("BEGIN:VTODO")
    assert f"DTSTART;TZID={ZONE}:20261001T163000" in text


def test_no_tzid_means_no_vtimezone() -> None:
    """A feed with only UTC and date values defines no zone."""
    plain = {k: v for k, v in ASK.items() if k not in {"dtstart", "due"}}
    assert "VTIMEZONE" not in calendar(vtodos([plain], {"life"}))


def test_one_vtimezone_per_zone_however_many_values_use_it() -> None:
    """Two values in one zone, a year apart, share one block that spans both."""
    lines = [
        f"DTSTART;TZID={ZONE}:20261001T163000",
        f"DUE;TZID={ZONE}:20271002T163000",
    ]
    block = timezones(lines)
    assert block.count("BEGIN:VTIMEZONE") == 1
    assert any("2025" in line or "2026" in line for line in block)
