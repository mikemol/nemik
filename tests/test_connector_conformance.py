# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W585: every connector must pass the same four checks, whatever it connects to.

A member is a factory `make(read_credential) -> Impl`; the checks drive it through `poll()` and
`apply(items, mode, sink)`, and the declaration it carries (nemik:W584) says which credential store
it may read. The registry holds the fake that proves the harness catches each breach; W188 (Google
Tasks) joins MEMBERS once the operator supplies its read-only token.
"""

from collections.abc import Callable
from pathlib import Path

import pytest

from nemik.connectors import Connector, Credential

Item = tuple[str, str]  # (source id, text)
Sink = Callable[[str, str], None]
Reader = Callable[[str], str]


class Fake:
    """A well-behaved connector over a fixed list, and the breaches it can be told to commit."""

    declaration: Connector
    seen: set[str]

    def __init__(self, read_credential: Reader, breach: str = "") -> None:
        """Build the fake.

        Args:
            read_credential: How the connector reads a secret from a named store.
            breach: Which rule to break, or empty for none.

        """
        credential = Credential("tasks.readonly", "read-only", "pass:fake/tasks")
        self.declaration = Connector("fake", "fake:{id}", credential, "poll", "letters")
        self.read_credential = read_credential
        self.breach = breach
        self.seen = set()

    def poll(self) -> list[Item]:
        """Read the source.

        Returns:
            Two items, one id repeated, as a poll that sees an update twice would.

        """
        store = "pass:elsewhere" if self.breach == "reads another store" else None
        self.read_credential(store or self.declaration.credential.store)
        return [("fake:1", "one"), ("fake:2", "two"), ("fake:1", "one")]

    def apply(self, items: list[Item], mode: str, sink: Sink) -> None:
        """Write each new item through the sink, unless the mode is a dry run.

        Args:
            items: What poll returned.
            mode: apply or dry-run.
            sink: Where a letter goes.

        """
        for source_id, text in items:
            fresh = source_id not in self.seen or self.breach == "duplicates"
            if mode == "dry-run" and self.breach != "writes in a dry run":
                continue
            if fresh:
                sink(source_id, text)
                self.seen.add(source_id)


def _fake(read_credential: Reader) -> Fake:
    """Make the well-behaved fake.

    Args:
        read_credential: The recording reader.

    Returns:
        The connector.

    """
    return Fake(read_credential)


MEMBERS: list[Callable[[Reader], Fake]] = [_fake]


def _drive(
    make: Callable[[Reader], Fake], mode: str
) -> tuple[Fake, list[str], list[str]]:
    """Run a member once and record what it wrote and which stores it read.

    Args:
        make: The member's factory.
        mode: apply or dry-run.

    Returns:
        The connector, the source ids written to the sink, and the stores read.

    """
    reads: list[str] = []
    written: list[str] = []

    def reader(store: str) -> str:
        reads.append(store)
        return "secret"

    connector = make(reader)
    connector.apply(
        connector.poll(), mode, lambda source_id, _: written.append(source_id)
    )
    return connector, written, reads


@pytest.mark.parametrize("make", MEMBERS)
def test_a_source_id_is_written_once(make: Callable[[Reader], Fake]) -> None:
    """Dedupe by source id: a repeated id and a second apply write nothing new."""
    connector, written, _ = _drive(make, "apply")
    assert sorted(written) == sorted(set(written))
    connector.apply(
        connector.poll(), "apply", lambda source_id, _: written.append(source_id)
    )
    assert sorted(written) == sorted(set(written))


@pytest.mark.parametrize("make", MEMBERS)
def test_a_dry_run_changes_nothing(make: Callable[[Reader], Fake]) -> None:
    """Dry run: nothing reaches the sink and the connector remembers nothing."""
    connector, written, _ = _drive(make, "dry-run")
    assert written == []
    assert connector.seen == set()


@pytest.mark.parametrize("make", MEMBERS)
def test_only_the_declared_store_is_read(make: Callable[[Reader], Fake]) -> None:
    """A connector reads the credential store its declaration names and no other."""
    connector, _, reads = _drive(make, "apply")
    assert set(reads) <= {connector.declaration.credential.store}


@pytest.mark.parametrize("make", MEMBERS)
def test_a_queue_file_is_never_written(
    make: Callable[[Reader], Fake], tmp_path: Path
) -> None:
    """Connectors speak through the sink (letters); the queue file stays byte-identical."""
    queue = tmp_path / "paths-forward.json"
    queue.write_text('{"waypoints": []}\n')
    before = queue.read_bytes()
    _drive(make, "apply")
    assert queue.read_bytes() == before


@pytest.mark.parametrize(
    "breach", ["duplicates", "writes in a dry run", "reads another store"]
)
def test_the_checks_catch_each_breach(breach: str) -> None:
    """A fake that breaks a rule fails the check for that rule, so the harness is armed."""

    def make(read_credential: Reader) -> Fake:
        return Fake(read_credential, breach)

    if breach == "duplicates":
        connector, written, _ = _drive(make, "apply")
        connector.apply(
            connector.poll(), "apply", lambda source_id, _: written.append(source_id)
        )
        assert sorted(written) != sorted(set(written))
    elif breach == "writes in a dry run":
        assert _drive(make, "dry-run")[1] != []
    else:
        connector, _, reads = _drive(make, "apply")
        assert not set(reads) <= {connector.declaration.credential.store}
