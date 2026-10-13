"""nemik:W455: the image's test stage carries every repo path the Bazel test targets read.

Two gates run the same tests: Bazel (the commit gate) and the Containerfile's test stage (the image
build). Each lists its inputs on its own. When docs/positioning.md joined the Bazel data (W361) but not
the image, pytest stopped at collection inside the build (exit 2), so no image was pushed and the
cluster ran 60 commits behind for ~30 hours while every commit gate was green. This holds the lists equal.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _bazel_data_paths() -> set[str]:
    """Repo-relative paths named in the test targets' data (labels and @repos skipped)."""
    build = (ROOT / "BUILD.bazel").read_text()
    block = build[build.index("sh_test(") : build.index("for src in glob")]
    names = set(re.findall(r'"([A-Za-z.][^":@$]*)"', block))
    names |= set(re.findall(r'glob\(\["([^"*]+)', block))
    return {n for n in names if (ROOT / n.split("/")[0]).exists()}


def _image_copies() -> set[str]:
    """The sources the Containerfile copies into the test stage (and the base it builds on)."""
    text = (ROOT / "Containerfile").read_text()
    copied: set[str] = set()
    for line in text.splitlines():
        m = re.match(r"COPY (?!--from)(.+) \S+$", line.strip())
        if m:
            copied |= set(m[1].split())
    return copied


def test_every_bazel_test_input_is_in_the_image_test_stage() -> None:
    copies = _image_copies()
    missing = sorted(
        p
        for p in _bazel_data_paths()
        if p not in copies and p.split("/")[0] not in copies
    )
    assert not missing, (
        f"the image's test stage lacks {missing}: add a COPY to Containerfile"
    )


def test_the_check_reads_something() -> None:
    assert {"tests", "docs", "tools"} <= {p.split("/")[0] for p in _bazel_data_paths()}
