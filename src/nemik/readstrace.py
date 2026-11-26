# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W1016: what one traced test run touched, classed, read out of an strace file.

`strace -f -e trace=%file,execve -o <file>` run under bazel's `--run_under` (a test run through
bazel, never pytest outside it) logs every file the sandboxed test opened, probed or ran. This
reduces that log to repo-relative paths in classes the footprint audit decides on:

- `read`: a file opened for reading;
- `listed`: a directory opened (a listing: os.listdir, glob, rglob). A test whose behaviour depends
  on what is IN a directory reads a glob, and inputs are named, never globbed, so the audit must
  see it, never have it dropped;
- `absent`: a path probed and not there (ENOENT on an open, a stat or an access). A probe for an
  absent file is a dependency on its ABSENCE: a config that changes behaviour when it appears;
- `probed`: a path stat'ed or access-checked that exists;
- `exec`: a program the test ran.

A runfiles or execroot path maps to its repo-relative path (the part after the workspace marker),
a path under the repo root maps by its prefix, and anything else is not a repo file (an exec'd
program keeps its own path). A `.pyc` in `__pycache__` stands for the `.py` behind it; `.venv`,
`external`, `bazel-out`, site-packages and `__pycache__` leftovers are not the repo's own reads; the
build's installed `site-packages/nemik/x.py` stands for `src/nemik/x.py`. An open strace logged as
`<unfinished ...>` has its path but not its result; it counts as a read, so an audit over-declares
rather than misses one.

ONE TRACE IS ONE RUN'S PATH: an under-approximation of what the test can read. The arbiter of an
input is the operator's rule, not this trace: an input belongs iff the build fails without it
(input mutation). This names candidates; it does not decide.

Strings and lists only, so the Codon census compiles it.
"""

PYC_DIR = "__pycache__/"
PYC_SUFFIX = ".pyc"
DIRECTORY_FLAG = "O_DIRECTORY"
WRITE_FLAGS = ["O_WRONLY", "O_RDWR"]
FAILED = " = -1 "
MISSING = "ENOENT"
OPENS = ["open", "openat", "openat2"]
PROBES = [
    "access",
    "faccessat",
    "faccessat2",
    "stat",
    "lstat",
    "newfstatat",
    "statx",
    "readlink",
    "readlinkat",
]
EXECS = ["execve", "execveat"]
READ = "read"
LISTED = "listed"
ABSENT = "absent"
PROBED = "probed"
EXEC = "exec"
CLASSES = [READ, LISTED, ABSENT, PROBED, EXEC]
NOTHING = ("", "")  # classify's answer for a line that is none of the classes
# nemik's own modules are read from the build's .venv copy of the package (the venv is a build
# input), which stands for the repo's src/nemik
INSTALLED = "site-packages/nemik/"
SOURCE = "src/nemik/"
NOT_REPO = [".venv/", "external/", "site-packages/", "bazel-out/", "__pycache__/"]


def quoted(line: str) -> str:
    """Read the first double-quoted text of an strace line.

    Returns:
        The text between the first pair of double quotes, or "" when the line has none.

    """
    start = line.find('"')
    if start < 0:
        return ""
    end = line.find('"', start + 1)
    return line[start + 1 : end] if end > start else ""


def syscall_of(line: str) -> str:
    """Read the system call an strace line names.

    Returns:
        The word before the first "(" (after any pid prefix), or "" when there is none.

    """
    paren = line.find("(")
    if paren < 0:
        return ""
    words = line[:paren].split()
    return words[-1] if words else ""


def repo_path(path: str, root: str, markers: list[str]) -> str:
    """Map an opened path to its repo-relative path.

    Args:
        path: The path the test opened.
        root: The repo root directory, with no trailing slash, or "" for none.
        markers: The path parts that precede a repo path in a bazel sandbox, such as
            ".runfiles/_main/" and "/execroot/_main/".

    Returns:
        The part after the first marker found, else the part after `root` and a slash, else "".

    """
    for marker in markers:
        at = path.find(marker)
        if at >= 0:
            return path[at + len(marker) :]
    if root and path.startswith(root + "/"):
        return path[len(root) + 1 :]
    return ""


def package_source(path: str) -> str:
    """Map a read of the build's installed nemik package to the repo source it stands for.

    Returns:
        `src/nemik/<rest>` for a path through `site-packages/nemik/`, else the path itself.

    """
    at = path.find(INSTALLED)
    return SOURCE + path[at + len(INSTALLED) :] if at >= 0 else path


def source_of(path: str) -> str:
    """Name the source a path stands for: the `.py` behind a `.pyc`.

    Returns:
        The `.py` path for a `__pycache__/name.cpython-NNN.pyc` path, else the path itself.

    """
    at = path.find(PYC_DIR)
    if at < 0 or not path.endswith(PYC_SUFFIX):
        return path
    name = path[at + len(PYC_DIR) :]
    return path[:at] + name[: name.find(".")] + ".py"


def mapped(line: str, root: str, markers: list[str]) -> str:
    """Map the path of an strace line to a repo path worth reporting.

    Returns:
        The repo-relative path, or "" when the line has no path, the path is not in the repo, or it
        is a leftover (.venv, external, bazel-out, site-packages, __pycache__).

    """
    found = source_of(package_source(repo_path(quoted(line), root, markers)))
    if not found or any(part in found + "/" for part in NOT_REPO):
        return ""
    return found


def classify(line: str, root: str, markers: list[str]) -> tuple[str, str]:
    """Class one strace line.

    Args:
        line: One line of the strace file.
        root: The repo root directory, or "" when only the markers map paths.
        markers: The sandbox path parts that precede a repo path (see repo_path).

    Returns:
        (class, path): one of READ, LISTED, ABSENT, PROBED, EXEC with the repo-relative path (an
        exec'd program keeps its own path), or ("", "") for a line that is none of them: a write,
        a failed open that was not ENOENT, a failed exec, or a path outside the repo.

    """
    name = syscall_of(line)
    if name in EXECS:
        return _exec_class(line, root, markers)
    # a probe or a failed open of a .pyc is the interpreter's cache lookup, not a dependency on
    # the .py beside it
    cache_lookup = quoted(line).endswith(PYC_SUFFIX) and (
        FAILED in line or name in PROBES
    )
    path = "" if cache_lookup else mapped(line, root, markers)
    if not path:
        return NOTHING
    if name in PROBES:
        return _probe_class(path, line)
    if name in OPENS:
        return _open_class(path, line)
    return NOTHING


def _exec_class(line: str, root: str, markers: list[str]) -> tuple[str, str]:
    """Class an exec line: the program, repo-mapped when it is one; a failed exec is a PATH search.

    Returns:
        (EXEC, the program) or NOTHING.

    """
    if FAILED in line:
        return NOTHING
    return EXEC, mapped(line, root, markers) or quoted(line)


def _probe_class(path: str, line: str) -> tuple[str, str]:
    """Class a stat or access line: PROBED when it exists, ABSENT on ENOENT, else nothing.

    Returns:
        (PROBED or ABSENT, the path) or NOTHING.

    """
    if FAILED not in line:
        return PROBED, path
    return (ABSENT, path) if MISSING in line else NOTHING


def _open_class(path: str, line: str) -> tuple[str, str]:
    """Class an open line: ABSENT on ENOENT, nothing for a write, LISTED for a directory, else READ.

    Returns:
        (READ, LISTED or ABSENT, the path) or NOTHING.

    """
    if FAILED in line:
        return (ABSENT, path) if MISSING in line else NOTHING
    if any(flag in line for flag in WRITE_FLAGS):
        return NOTHING
    return (LISTED if DIRECTORY_FLAG in line else READ), path


def classes(trace: str, root: str, markers: list[str]) -> dict[str, list[str]]:
    """Reduce an strace file to its classes of touched paths.

    Args:
        trace: The strace -f -e trace=%file,execve output.
        root: The repo root directory, or "" when only the markers map paths.
        markers: The sandbox path parts that precede a repo path (see repo_path).

    Returns:
        For each of CLASSES, the sorted distinct paths (see classify); every class is present.

    """
    found: dict[str, set[str]] = {name: set() for name in CLASSES}
    for line in trace.splitlines():
        kind, path = classify(line, root, markers)
        if kind:
            found[kind].add(path)
    return {name: sorted(paths) for name, paths in found.items()}


def reads(trace: str, root: str, markers: list[str]) -> list[str]:
    """Reduce an strace file to the repo files the traced run read.

    Returns:
        The `read` class of `classes`: files opened for reading, not directories, not probes.

    """
    return classes(trace, root, markers)[READ]
