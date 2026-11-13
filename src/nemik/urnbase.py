# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""The URN prefix of every waypoint node: `urn:nemik:<repo>/<symbol>` (nemik:W2147).

It lived in nemik.adapter, which reaches rdflib, urllib, hashlib and importlib.metadata, so a pure
module that only needed the prefix (nemik.pieces) carried all of those walls. Here it is a constant
and no import, so the Codon census can compile it; nemik.adapter imports it from here and keeps the
name `BASE`.
"""

BASE = "urn:nemik:"
