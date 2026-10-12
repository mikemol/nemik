"""nemik:W414: hashes.json names every published data file with the sha256 of its bytes."""

import hashlib
import json
from pathlib import Path

from nemik.serve import build_static

FLEET = Path(__file__).parent / "fixtures" / "fleet"


def test_every_data_file_is_hashed_and_nothing_else(tmp_path: Path) -> None:
    withheld = tmp_path / "withheld.json"
    withheld.write_text(json.dumps({"version": 1, "as_of": "x", "items": []}))
    out = tmp_path / "out"
    build_static(FLEET, out, withheld)
    hashes = json.loads((out / "hashes.json").read_text())
    data = {
        str(p.relative_to(out)) for p in out.rglob("*.json") if p.name != "hashes.json"
    }
    assert set(hashes) == data
    for name, digest in hashes.items():
        assert hashlib.sha256((out / name).read_bytes()).hexdigest() == digest
