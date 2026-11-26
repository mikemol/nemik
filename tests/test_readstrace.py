# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1016: readstrace reduces an strace file to the repo files a test run read."""

from nemik import readstrace

MARKERS = [".runfiles/_main/", "/execroot/_main/"]
RUN = "/sb/t.runfiles/_main"
ROOT = "/home/u/github/nemik"
PYC = "src/nemik/__pycache__/cones.cpython-314.pyc"

TRACE = f"""\
101 openat(AT_FDCWD, "{RUN}/src/nemik/cones.py", O_RDONLY|O_CLOEXEC) = 3
101 openat(AT_FDCWD, "{RUN}/src/nemik/data/shapes.ttl", O_RDONLY) = 4
102 openat(AT_FDCWD, "{RUN}/{PYC}", O_RDONLY) = 5
102 openat(AT_FDCWD, "{RUN}/src/nemik/gone.py", O_RDONLY) = -1 ENOENT (No such file)
102 openat(AT_FDCWD, "{RUN}/src/nemik", O_RDONLY|O_NONBLOCK|O_DIRECTORY) = 6
103 openat(AT_FDCWD, "{RUN}/.venv/lib/site-packages/rdflib/graph.py", O_RDONLY) = 7
103 openat(AT_FDCWD, "{RUN}/external/rules_python/x.py", O_RDONLY) = 8
103 openat(AT_FDCWD, "/usr/lib/python3.14/os.py", O_RDONLY) = 9
104 openat(AT_FDCWD, "{ROOT}/tests/test_cones.py", O_RDONLY) = 10
104 openat(AT_FDCWD, "{ROOT}/src/nemik/cones.py", O_RDONLY) = 11
105 openat(AT_FDCWD, "/x/execroot/_main/tests/flow_cases.py", O_RDONLY <unfinished ...>
105 +++ exited with 0 +++
106 openat(AT_FDCWD, "{RUN}/.venv/lib/python3.14/site-packages/nemik/_typing.py", O_RDONLY) = 12
106 openat(AT_FDCWD, "{RUN}/.venv/lib/python3.14/site-packages/nemik/data/s.ttl", O_RDONLY) = 13
106 openat(AT_FDCWD, "{RUN}/tests/__pycache__/t.cpython-314.pyc.1321", O_WRONLY|O_CREAT) = 14
106 openat(AT_FDCWD, "/e/execroot/_main/bazel-out/bin/t.runfiles/py/lib/os.py", O_RDONLY) = 15
"""


def test_the_repo_files_read_are_reduced_from_the_trace() -> None:
    """Failed opens, writes, directories, other trees and venv, external or bazel-out drop out.

    The build reads nemik's own modules from its .venv copy of the package, which stands for the
    repo's src/nemik (the 2026-11-26 trace of //:test_cones: 1340 opens, 7 repo reads).
    """
    assert readstrace.reads(TRACE, ROOT, MARKERS) == [
        "src/nemik/_typing.py",
        "src/nemik/cones.py",
        "src/nemik/data/s.ttl",
        "src/nemik/data/shapes.ttl",
        "tests/flow_cases.py",
        "tests/test_cones.py",
    ]


def test_a_pyc_stands_for_the_source_behind_it() -> None:
    """The .py behind a __pycache__ .pyc is the read; other paths are unchanged."""
    assert readstrace.source_of(PYC) == "src/nemik/cones.py"
    assert readstrace.source_of("src/nemik/cones.py") == "src/nemik/cones.py"
    assert readstrace.source_of("data/x.pyc") == "data/x.pyc"


def test_a_path_maps_by_marker_then_by_root_else_not_at_all() -> None:
    """A sandbox marker wins; a path under the root maps by prefix; others map to nothing."""
    path = "/h/execroot/_main/src/a.py"
    assert readstrace.repo_path(path, ROOT, MARKERS) == "src/a.py"
    assert readstrace.repo_path(f"{ROOT}/src/b.py", ROOT, MARKERS) == "src/b.py"
    assert not readstrace.repo_path("/usr/lib/os.py", ROOT, MARKERS)
    assert not readstrace.repo_path(f"{ROOT}/src/b.py", "", MARKERS)


def test_a_line_with_no_quoted_path_reads_nothing() -> None:
    """A resumed or exit line has no path to read."""
    assert not readstrace.quoted("105 +++ exited with 0 +++")
    assert not readstrace.quoted('x "only')
    assert readstrace.quoted('openat(AT_FDCWD, "a/b", O_RDONLY)') == "a/b"
    assert readstrace.reads("", ROOT, MARKERS) == []


# lines shaped like the real `strace -f -e trace=%file,execve` of //:test_cones (2026-11-26)
REAL_SHAPED = f"""\
16 execve("./test_cones", ["./test_cones", "tests/test_cones.py"], 0x7ffc /* 34 vars */) = 0
16 execve("/usr/bin/cat", ["cat", "x"], 0x7ffc /* 34 vars */) = 0
16 execve("/nope/tool", ["tool"], 0x7ffc /* 34 vars */) = -1 ENOENT (No such file)
17 newfstatat(AT_FDCWD, "{RUN}/tests/test_cones.py", {{st_mode=S_IFREG|0644}}, 0) = 0
17 newfstatat(AT_FDCWD, "{RUN}/conftest.py", 0x7ffe81f857e8, 0) = -1 ENOENT (No such file)
17 openat(AT_FDCWD, "{RUN}/tools", O_RDONLY|O_NONBLOCK|O_CLOEXEC|O_DIRECTORY) = 4
17 openat(AT_FDCWD, "{RUN}/.claude/pyvenv.cfg", O_RDONLY|O_CLOEXEC) = -1 ENOENT (No such file)
17 openat(AT_FDCWD, "{RUN}/secret.toml", O_RDONLY|O_CLOEXEC) = -1 EACCES (Permission denied)
17 openat(AT_FDCWD, "{RUN}/{PYC}", O_RDONLY|O_CLOEXEC) = -1 ENOENT (No such file)
17 statx(AT_FDCWD, "{RUN}/{PYC}", AT_STATX_SYNC_AS_STAT, STATX_ALL, 0x7ff) = -1 ENOENT (No file)
17 openat(AT_FDCWD, "{RUN}/pyproject.toml", O_RDONLY|O_CLOEXEC) = 4
"""


def test_each_class_of_touch_is_reported_not_dropped() -> None:
    """Listings, absent probes, probes and programs are classes of their own."""
    found = readstrace.classes(REAL_SHAPED, ROOT, MARKERS)
    assert found["read"] == ["pyproject.toml"]
    assert found["listed"] == ["tools"]
    assert found["absent"] == [".claude/pyvenv.cfg", "conftest.py"]
    assert found["probed"] == ["tests/test_cones.py"]
    assert found["exec"] == ["./test_cones", "/usr/bin/cat"]
    assert sorted(found) == sorted(readstrace.CLASSES)


def test_a_cache_miss_or_an_unreadable_file_is_no_dependency() -> None:
    """A missing .pyc is a cache lookup, EACCES is not absence, a failed exec is a PATH search."""
    found = readstrace.classes(REAL_SHAPED, ROOT, MARKERS)
    assert "src/nemik/cones.py" not in found["absent"]
    assert "secret.toml" not in found["absent"] + found["read"]
    assert "/nope/tool" not in found["exec"]
    assert readstrace.syscall_of('17 newfstatat(AT_FDCWD, "x", 0) = 0') == "newfstatat"
    assert not readstrace.syscall_of("17 +++ exited with 0 +++")
