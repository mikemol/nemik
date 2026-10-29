# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1264: an 'operator: act' ask naming a root-shaped command is flagged."""

import pytest

from nemik.blocks import sudo_shaped


def test_an_act_ask_naming_sudo_is_shaped() -> None:
    """The case the host retro R96 caught: an act ask relaying sudo install -d."""
    assert sudo_shaped("operator: act sudo install -d /srv/x")


@pytest.mark.parametrize(
    "ask",
    [
        "operator: act chown the share to the service user",
        "operator: act run install -d on the host",
        "operator: act systemctl --system restart the unit",
        "operator: act mkfs the volume",
        "operator: act mount the disk",
        "operator: act become root and edit it",
    ],
)
def test_each_root_shaped_word_counts(ask: str) -> None:
    """Every word the host named is a flag in an act ask."""
    assert sudo_shaped(ask)


def test_a_decide_ask_naming_mount_is_not_shaped() -> None:
    """Only an act ask is the apply loop's to carry; a decision is the operator's."""
    assert not sudo_shaped("operator: decide whether to mount the disk read-only")


def test_a_word_inside_a_longer_word_is_not_shaped() -> None:
    """Word boundaries: rootless and mounting are not root or mount."""
    assert not sudo_shaped(
        "operator: act review the rootless build and its mounting notes"
    )


def test_the_second_of_several_asks_counts() -> None:
    """The ask text joins a card's blocked_on values with ' | '; any act segment counts."""
    assert sudo_shaped("operator: decide the colour | operator: act sudo mkdir /x")
