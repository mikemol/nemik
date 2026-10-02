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
