# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W414: hashes.json names every published data file with the sha256 of its bytes."""

import hashlib
import json
from pathlib import Path

from nemik.serve import build_static
from nemik.tracker import parse_tree

FLEET = Path(__file__).parent / "fixtures" / "fleet"


def test_every_data_file_is_hashed_and_nothing_else(tmp_path: Path) -> None:
    """hashes.json names each published data file, and no other."""
    withheld = tmp_path / "withheld.json"
    body: dict[str, object] = {"version": 1, "as_of": "x", "items": []}
    withheld.write_text(json.dumps(body))
    out = tmp_path / "out"
    build_static(FLEET, out, withheld)
    hashes = parse_tree((out / "hashes.json").read_text())
    # the JSON documents, (W449) each repo's TRS feed in Turtle and (W354) its ForgeFed outbox
    data = {
        str(p.relative_to(out))
        for pattern in ("*.json", "*.ttl", "*.jsonld")
        for p in out.rglob(pattern)
        if p.name != "hashes.json"
    }
    assert set(hashes.names[hashes.root]) == data
    for name in data:
        digest = hashes.string(hashes.root, name)
        assert hashlib.sha256((out / name).read_bytes()).hexdigest() == digest
