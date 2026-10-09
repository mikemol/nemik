"""nemik:W169: the static page and its scripts, with only relative links."""

import re

from nemik.serve import VENDOR, write_static


def test_page_and_vendor_written_with_relative_links(tmp_path) -> None:
    written = write_static(tmp_path)
    assert {p.relative_to(tmp_path).as_posix() for p in written} == {"index.html"} | {
        f"vendor/{v}" for v in VENDOR
    }
    html = (tmp_path / "index.html").read_text()
    for url in re.findall(r'(?:src|href)="([^"$]+)"', html) + re.findall(
        r'fetch\("([^"]+)"', html
    ):
        assert not url.startswith(("/", "http:", "https:")), url
    for f in re.findall(r'fetch\("([^"]+)"', html):
        # a file name a bucket can serve
        assert f.endswith((".json", "/")), f


def test_data_files_cover_what_the_page_fetches_and_are_manifested() -> None:
    from pathlib import Path

    from nemik.manifest import unmanifested
    from nemik.serve import Model, static_data

    docs = static_data(Model(Path(__file__).parent / "fixtures" / "fleet"))
    assert {"graph.json", "wake.json"} <= set(docs)
    assert any(k.startswith("goals/") for k in docs)
    assert not any(k.startswith("inbound/") for k in docs)  # the page never reads it
    wake = docs["wake.json"]
    assert isinstance(wake, dict)
    assert wake["liveness"] == "snapshot"  # no host path published
    for name, doc in docs.items():
        assert unmanifested(name, doc) == [], name


def test_static_page_has_no_tools_panel(tmp_path) -> None:
    write_static(tmp_path)
    html = (tmp_path / "index.html").read_text()
    assert 'id="tool"' not in html and "cmd/" not in html.split("<script>")[0]


def test_static_build_end_to_end(tmp_path) -> None:
    import json
    from pathlib import Path

    import pytest

    from nemik.serve import main

    fleet = Path(__file__).parent / "fixtures" / "fleet"
    out = tmp_path / "out"
    with pytest.raises(SystemExit) as e:  # no list: refused, nothing written
        main(
            [
                "--root",
                str(fleet),
                "--static",
                str(out),
                "--withheld",
                str(tmp_path / "missing.json"),
            ]
        )
    assert e.value.code == 2 and not out.exists()
    wl = tmp_path / "withheld.json"
    wl.write_text(json.dumps({"version": 1, "as_of": "x", "items": []}))
    main(["--root", str(fleet), "--static", str(out), "--withheld", str(wl)])
    names = {p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()}
    assert {"index.html", "graph.json", "wake.json"} <= names and any(
        n.startswith("goals/") for n in names
    )
    assert "withheld.json" not in names
