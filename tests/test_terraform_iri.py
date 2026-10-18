# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W461: a Terraform address is one reversible IRI segment, so resources can be nodes."""

import pytest

from nemik.adapter import resource_address, resource_uri, waypoint_uri

ADDRESSES = [
    "aws_instance.web",
    "module.net.module.subnet.aws_subnet.private[0]",
    'aws_s3_bucket.logs["eu-west-1"]',
    "module.a.b_c.d with space",
    "weird/slash#hash?query%percent",
]
SEPARATORS = set('/#? []"')


@pytest.mark.parametrize("address", ADDRESSES)
def test_an_address_round_trips(address: str) -> None:
    """The IRI gives back exactly the address that made it."""
    assert resource_address(str(resource_uri("luthen", address))) == address


@pytest.mark.parametrize("address", ADDRESSES)
def test_an_address_is_one_path_segment(address: str) -> None:
    """Nothing in the encoded part reads as another segment, a fragment or a query."""
    tail = str(resource_uri("luthen", address)).split("luthen/", 1)[1]
    assert not set(tail) & SEPARATORS


def test_distinct_addresses_get_distinct_iris() -> None:
    """The encoding is injective over the samples."""
    iris = {str(resource_uri("luthen", a)) for a in ADDRESSES}
    assert len(iris) == len(ADDRESSES)


def test_a_card_symbol_is_untouched() -> None:
    """W12 has nothing to encode, so a resource and a card share the scheme without clashing."""
    assert resource_uri("luthen", "W12") == waypoint_uri("luthen", "W12")
