"""nemik:W169: the static page and its scripts, with only relative links."""

import re

from nemik.serve import VENDOR, write_static


def test_page_and_vendor_written_with_relative_links(tmp_path) -> None:
    written = write_static(tmp_path)
    assert {p.relative_to(tmp_path).as_posix() for p in written} == {"index.html"} | {f"vendor/{v}" for v in VENDOR}
    html = (tmp_path / "index.html").read_text()
    for url in re.findall(r'(?:src|href)="([^"$]+)"', html) + re.findall(r'fetch\("([^"]+)"', html):
        assert not url.startswith(("/", "http:", "https:")), url
    for f in re.findall(r'fetch\("([^"]+)"', html):
        assert f.endswith(".json") or f.endswith("/"), f  # a file name a bucket can serve


def test_data_files_cover_what_the_page_fetches_and_are_manifested() -> None:
    from pathlib import Path

    from nemik.manifest import unmanifested
    from nemik.serve import Model, static_data

    docs = static_data(Model(Path(__file__).parent / "fixtures" / "fleet"))
    assert {"graph.json", "wake.json"} <= set(docs)
    assert any(k.startswith("goals/") for k in docs)
    assert not any(k.startswith("inbound/") for k in docs)  # the page never reads it
    assert docs["wake.json"]["liveness"] == "snapshot"  # no host path published
    for name, doc in docs.items():
        assert unmanifested(name, doc) == [], name
