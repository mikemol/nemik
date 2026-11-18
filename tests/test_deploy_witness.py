# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2262: tools/deploy_witness.py builds the PromQL deploy witness from a landing stamp."""

from deploy_witness import (
    IMAGE_EPOCH,
    USAGE,
    command_for,
    landing_epoch,
    main,
    witness_for,
)
from mikemol.procrun.proc import capture

LANDED = "20261117T135329Z"
LANDED_EPOCH = (
    1794923609  # the same instant as epoch seconds, read from the stamp by hand
)
PREFIX = (
    "mikemol-paths-forward --state .claude/paths-forward.json --update W2251 --witness "
)
SUFFIX = " --witness-lang promql"


def test_the_stamp_is_read_as_utc_epoch_seconds() -> None:
    """The writer's landed_at stamp (UTC, no separators) becomes epoch seconds."""
    assert landing_epoch(LANDED) == LANDED_EPOCH


def test_the_witness_holds_once_the_oldest_image_is_at_or_after_the_landing() -> None:
    """The query compares the pods' oldest image build epoch with the landing's."""
    assert witness_for(LANDED) == f"{IMAGE_EPOCH} >= {LANDED_EPOCH}"


def test_the_printed_command_reaches_the_writer_with_the_exact_query() -> None:
    """The shell reads the printed query back to the exact text, `$1` and quotes included."""
    command = command_for("W2251", LANDED)
    assert command.startswith(PREFIX)
    assert command.endswith(SUFFIX)
    quoted = command[len(PREFIX) : -len(SUFFIX)]
    read_back = capture(["sh", "-c", f"printf %s {quoted}"])
    assert read_back.stdout == witness_for(LANDED)


def test_a_bad_stamp_is_refused_with_the_usage_status() -> None:
    """Something that is not SYMBOL:YYYYMMDDTHHMMSSZ is refused, and no argument is too."""
    assert main(["W1:not-a-stamp"]) == USAGE
    assert main([]) == USAGE
