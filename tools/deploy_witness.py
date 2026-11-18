# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""deploy_witness: the PromQL witness for a landed card that ships in the image (nemik:W2262).

A landed src card is done when the pods run an image that holds its commit. The image tag's leading
number is the build's epoch seconds, so the deploy witness is: the oldest image build epoch across
the pods is at or after the landing. It holds once every pod runs such an image and stays true
after later deploys.

WHICH MOMENT THE EPOCH IS (read at .forgejo/workflows/build.yml, a committed file): the checkout
step clones the trunk tip (`clone --depth 1`, no ref pinned), and the next step names the image
`$(date -u +%s)-<github.sha>`, so the shell expands the epoch when the build command STARTS: after
the clone, before the build runs and before the push. It is not the finish or push time. So an
image whose epoch is at or after the landing was cloned from a trunk that held the landing, EXCEPT
for a landing pushed inside the gap between that clone and the `date` call (the step switch plus a
`rev-parse` and a `log`, seconds): a build that cloned just before the landing could satisfy the
witness without holding it. The tag's sha is the event's commit, not the cloned tip, so it cannot
close that gap. A sound form would stamp the cloned tip's commit time into the tag (a change to
build.yml and to the tag pattern in deploy/image-automation.yaml): carded, not done here.

label_value is MetricsQL, not PromQL: the query runs only against VictoriaMetrics, which is where
nemik's `promql` witnesses are answered.

The hand-written form `input.git_ref["nemik@<sha>"].resolves == true` never holds: the git_ref
observer answers `exists` and `sha`, so `resolves` is undefined (nemik:W2263).

    python3 tools/deploy_witness.py W2251:20261117T135329Z [SYMBOL:LANDED_AT ...]

prints one writer command per card (`--update SYMBOL --witness QUERY --witness-lang promql`) for
the loop to run, one per call. Pure: standard library only, no queue, no network.
"""

import sys
from datetime import UTC, datetime

# the oldest image build across the nemik pods; label_value turns the extracted epoch into a number
IMAGE_EPOCH = (
    'min(label_value(label_replace(kube_pod_container_info{namespace="nemik"}, '
    '"epoch", "$1", "image", ".*:([0-9]+)-[0-9a-f]+$"), "epoch"))'
)
STAMP = "%Y%m%dT%H%M%SZ"
OK, USAGE = 0, 2


def landing_epoch(landed_at: str) -> int:
    """Read the writer's landed_at stamp (YYYYMMDDTHHMMSSZ, UTC) as epoch seconds.

    Returns:
        The seconds since the epoch.

    """
    return int(datetime.strptime(landed_at, STAMP).replace(tzinfo=UTC).timestamp())


def witness_for(landed_at: str) -> str:
    """Build the deploy witness for a card landed at `landed_at`.

    Returns:
        A PromQL expression that holds once every pod's image was built at or after the landing.

    """
    return f"{IMAGE_EPOCH} >= {landing_epoch(landed_at)}"


def command_for(symbol: str, landed_at: str) -> str:
    """Build the writer command that attaches the witness to a card.

    Returns:
        The `mikemol-paths-forward --update` words, the query quoted for a shell.

    """
    # double quotes with the four characters the shell still reads escaped: the loop's shell check
    # refuses a `$` inside single quotes (SC2016), so the printed command is one it will run
    query = witness_for(landed_at)
    for char in ("\\", '"', "$", "`"):
        query = query.replace(char, "\\" + char)
    return (
        f"mikemol-paths-forward --state .claude/paths-forward.json --update {symbol} "
        f'--witness "{query}" --witness-lang promql'
    )


def main(argv: list[str]) -> int:
    """Print the witness command for each SYMBOL:LANDED_AT argument.

    Returns:
        0, or 2 when no argument is given or one is not SYMBOL:LANDED_AT with a valid stamp.

    """
    if not argv:
        sys.stderr.write(
            "usage: deploy_witness.py SYMBOL:LANDED_AT [SYMBOL:LANDED_AT ...]\n"
        )
        return USAGE
    lines = []
    for spec in argv:
        symbol, _, landed_at = spec.partition(":")
        try:
            lines.append(command_for(symbol, landed_at))
        except ValueError:
            sys.stderr.write(
                f"deploy_witness: {spec!r} is not SYMBOL:YYYYMMDDTHHMMSSZ\n"
            )
            return USAGE
    sys.stdout.write("\n".join(lines) + "\n")
    return OK


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
