# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2280: a letter to a peer as a GitHub issue in the peer's private repo, off by default.

The courier send path (W1048) writes an outward message, so it is built in two halves that this
module keeps apart. `dry_run` prints the issue it would create (repo, title, body) and builds
nothing. `send_argv` builds the one `gh api` command that would create it, and only when the
OPERATOR's config says so: the flag is a line `courier_send = true` in text the caller reads
from the operator-owned config file, never an argument an agent passes. Without that line a
send raises.

This module is pure: no subprocess, no network, no credential, no file read. It cannot tell who
wrote the config text it is given, so the guarantee lives where the text is read: the caller
reads the operator's file and nothing else. The route is the host's `gh` login
(docs/courier-read-path.md), which nemik never reads; running the argv is a later step, and the
first real send is the operator's act (W2282), never a session's.

Plain strings and lists only, so the module compiles under the pinned Codon.
"""

REPO_SEP = "/"
FLAG = "courier_send"


class SendDisabledError(Exception):
    """The send was asked for while the operator's config does not enable it."""


class BadRepoError(Exception):
    """A repo that is not `owner/name`."""


def enabled(config: str) -> bool:
    """Say whether the operator's config enables the courier send.

    Returns:
        True when the last `courier_send` line of the config reads `true`; a missing line, any
        other value and a commented-out line are all off.

    """
    on = False
    for line in config.splitlines():
        key, sep, value = line.partition("=")
        if sep == "=" and key.strip() == FLAG:
            on = value.strip() == "true"
    return on


def _check_repo(repo: str) -> None:
    """Refuse a repo that is not exactly `owner/name` with no blanks.

    Raises:
        BadRepoError: When the owner or the name is empty, there is more than one slash, or the
            text holds a blank.

    """
    owner, sep, name = repo.partition(REPO_SEP)
    if sep != REPO_SEP or not owner or not name or REPO_SEP in name or " " in repo:
        raise BadRepoError(repo)


def dry_run(repo: str, title: str, body: str) -> str:
    """Print the issue a send would create, and send nothing.

    Returns:
        The repo, title and body, led by a line that says nothing was sent.

    """
    _check_repo(repo)
    return f"DRY RUN: nothing sent\nrepo: {repo}\ntitle: {title}\nbody:\n{body}\n"


def send_argv(repo: str, title: str, body: str, config: str) -> list[str]:
    """Build the `gh api` command for the issue, only when the operator's config enables it.

    Each of title and body is one argument, so no shell ever parses them.

    Returns:
        The argument vector, `gh api repos/<repo>/issues --method POST -f title=... -f body=...`.

    Raises:
        SendDisabledError: When the config does not enable the send (see `enabled`).

    """
    _check_repo(repo)
    if not enabled(config):
        raise SendDisabledError(repo)
    return [
        "gh",
        "api",
        f"repos/{repo}/issues",
        "--method",
        "POST",
        "-f",
        f"title={title}",
        "-f",
        f"body={body}",
    ]
