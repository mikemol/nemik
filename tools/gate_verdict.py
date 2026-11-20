# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2345: the gate's git-fed judgments as bazel build actions that write JSON verdicts.

The three judgments of tools/hook_facts.py (named inputs, wheels, the working card) read git's
facts, which tools/gate_facts.sh writes from the STAGED tree into .gate-facts/. The gate hands
that directory to bazel as a repository (`--inject_repository=gate_facts=...`), so the facts are
named inputs whose CONTENT is the cache key: no environment variable, no stamp read from the
environment. Each judgment is one build action, `gate_verdict.py judge KIND OUT FILE...`.

A verdict is a CLOSED UNION, never a result that may or may not be there (the operator's ruling
of 2026-11-14, host line 170448): `Judged` (state ok or problems, the problems, and BOTH stamps,
the tree and the HEAD) or `CannotJudge` (why, and no stamp at all). In JSON:

    {"state": "ok" | "problems", "problems": [...], "tree": "<sha>", "head": "<sha>"}
    {"state": "cannot_judge", "why": [...]}

The one writer is `verdict_text` and the one reader is `parse_verdict`; both the gate
(`gate_verdict.py status`, exit 0, 1 or 7 from the state) and the aggregate bazel test read it
through that parser. Anything unreadable or of the wrong shape raises a `VerdictError` where it is
found, and the callers turn it into a `CannotJudge`: unparseable JSON, an unknown state, a field
missing or extra for its state, a state that contradicts its problems, a stamp that is no sha, a
missing file, and a verdict stamped for another tree or HEAD, never a pass. 1 means the gate
refused the tree; 7 means the tree was not judged.

    gate_verdict.py judge KIND OUT FILE...     write OUT (always exits 0)
    gate_verdict.py status DIR TREE HEAD       read DIR's verdicts; exit 0, 1 or 7
"""

import json
import sys
from enum import Enum
from pathlib import Path
from typing import NamedTuple, cast

from hook_facts import (
    SHA,
    FactsError,
    named_inputs_problems,
    parse,
    parse_diff,
    wheel_problems,
    working_card_problems,
)

EXIT_OK = 0
EXIT_PROBLEMS = 1
EXIT_CANNOT_JUDGE = 7
USAGE = 2
KINDS = ("named_inputs", "wheels", "working_card")
JUDGE_ARGS = {"named_inputs": 3, "wheels": 2, "working_card": 2}
JUDGE_MIN = 4
STATUS_ARGS = 4
JUDGED_FIELDS = {"state", "problems", "tree", "head"}
CANNOT_FIELDS = {"state", "why"}


class State(Enum):
    """What a verdict says about the tree."""

    OK = "ok"
    PROBLEMS = "problems"
    CANNOT_JUDGE = "cannot_judge"


class VerdictError(ValueError):
    """A verdict or one of its inputs is unreadable or of the wrong shape."""


class Judged(NamedTuple):
    """A judgment that ran: ok or problems, with the tree and HEAD it judged."""

    state: State
    problems: list[str]
    tree: str
    head: str


class CannotJudge(NamedTuple):
    """A judgment that could not run: the reasons, and no stamp."""

    why: list[str]


Verdict = Judged | CannotJudge


def judged(problems: list[str], tree: str, head: str) -> Judged:
    """Make the verdict of a judgment that ran.

    Returns:
        ok when it found nothing, problems otherwise.

    """
    return Judged(State.PROBLEMS if problems else State.OK, problems, tree, head)


def _sha(value: str, what: str) -> str:
    if not SHA.fullmatch(value):
        msg = f"{what} is not a 40 hex sha ({value!r})"
        raise VerdictError(msg)
    return value


def _contradicts(state: State, problems: list[str]) -> bool:
    return (state is State.OK) == bool(problems)


def _name(state: State) -> str:
    # the wire name of a state, which is its member name in lower case (Enum.value is typed Any)
    return state.name.lower()


def verdict_text(verdict: Verdict) -> str:
    """Write a verdict: the one writer of the format.

    Args:
        verdict: A verdict of either kind.

    Returns:
        The JSON text.

    Raises:
        VerdictError: the verdict is not one parse_verdict would read back: a judged state of
            cannot_judge, a state that contradicts its problems, a stamp that is no sha, or a
            cannot_judge with no reason.

    """
    fields: dict[str, object]
    if isinstance(verdict, CannotJudge):
        if not verdict.why:
            msg = "a cannot_judge verdict needs a reason"
            raise VerdictError(msg)
        fields = {"state": _name(State.CANNOT_JUDGE), "why": verdict.why}
    else:
        if verdict.state is State.CANNOT_JUDGE:
            msg = "a judged verdict cannot be cannot_judge"
            raise VerdictError(msg)
        if _contradicts(verdict.state, verdict.problems):
            msg = f"state {_name(verdict.state)} contradicts its problems"
            raise VerdictError(msg)
        fields = {
            "state": _name(verdict.state),
            "problems": verdict.problems,
            "tree": _sha(verdict.tree, "the tree"),
            "head": _sha(verdict.head, "the head"),
        }
    return json.dumps(fields, indent=1) + "\n"


def _text(value: object, what: str) -> str:
    if not isinstance(value, str):
        msg = f"{what} is not text"
        raise VerdictError(msg)
    return value


def _texts(value: object, what: str) -> list[str]:
    if not isinstance(value, list):
        msg = f"{what} is not a list"
        raise VerdictError(msg)
    return [_text(item, what) for item in cast("list[object]", value)]


def _state(value: object) -> State:
    try:
        return State[_text(value, "the state").upper()]
    except KeyError as err:
        msg = f"the state {value!r} is not one of ok, problems, cannot_judge"
        raise VerdictError(msg) from err


def _decode(text: str) -> Verdict:
    try:
        parsed: object = json.loads(text)
    except ValueError as err:
        msg = "the verdict is not JSON"
        raise VerdictError(msg) from err
    if not isinstance(parsed, dict):
        msg = "the verdict is not a JSON object"
        raise VerdictError(msg)
    fields = cast("dict[str, object]", parsed)
    state = _state(fields.get("state"))
    expected = sorted(CANNOT_FIELDS if state is State.CANNOT_JUDGE else JUDGED_FIELDS)
    if sorted(fields) != expected:
        msg = f"the fields {sorted(fields)} are not {expected} for {_name(state)}"
        raise VerdictError(msg)
    if state is State.CANNOT_JUDGE:
        why = _texts(fields["why"], "why")
        if not why:
            msg = "a cannot_judge verdict needs a reason"
            raise VerdictError(msg)
        return CannotJudge(why)
    problems = _texts(fields["problems"], "problems")
    if _contradicts(state, problems):
        msg = f"state {_name(state)} contradicts its problems"
        raise VerdictError(msg)
    tree = _sha(_text(fields["tree"], "the tree"), "the tree")
    head = _sha(_text(fields["head"], "the head"), "the head")
    return Judged(state, problems, tree, head)


def parse_verdict(text: str) -> Verdict:
    """Read a verdict: the one reader of the format.

    Args:
        text: A verdict file's text.

    Returns:
        The verdict; anything unreadable or of the wrong shape is a CannotJudge saying why.

    """
    try:
        return _decode(text)
    except VerdictError as err:
        return CannotJudge([str(err)])


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as err:
        msg = f"{path.name} is missing or unreadable"
        raise VerdictError(msg) from err


def named_inputs_verdict(tracked: str, src_list: str, tests_list: str) -> Verdict:
    """Judge the named-inputs lists against the tracked paths.

    Returns:
        The verdict, stamped with the tracked facts' tree and HEAD.

    """
    try:
        facts = parse(tracked, "tracked.txt")
    except FactsError as err:
        return CannotJudge([str(err)])
    problems = named_inputs_problems(facts, src_list, tests_list)
    return judged(problems, facts.tree, facts.head)


def wheels_verdict(tracked: str, pyproject: str) -> Verdict:
    """Judge that every wheel the pyproject.toml names is tracked.

    Returns:
        The verdict, stamped with the tracked facts' tree and HEAD.

    """
    try:
        facts = parse(tracked, "tracked.txt")
    except FactsError as err:
        return CannotJudge([str(err)])
    return judged(wheel_problems(facts, pyproject), facts.tree, facts.head)


def working_card_verdict(changed: str, queue: str) -> Verdict:
    """Judge the working-card rule over the changed paths.

    Returns:
        The verdict, stamped with the diff's tree and HEAD.

    """
    try:
        diff = parse_diff(changed, "changed.txt")
    except FactsError as err:
        return CannotJudge([str(err)])
    return judged(working_card_problems(queue, diff), diff.tree, diff.head)


def _stale(verdict: Judged, tree: str, head: str) -> bool:
    return verdict.tree != tree or verdict.head != head


def exit_status(verdicts: list[Verdict], tree: str, head: str) -> tuple[int, list[str]]:
    """Map verdicts to the gate's status: 1 refused, 7 not judged, 0 held.

    A problems verdict is a definite refusal (1) even beside one that could not judge. An ok
    verdict counts only when it is stamped for THIS tree and THIS HEAD: a stale one is not judged.

    Args:
        verdicts: What the judgments wrote.
        tree: The staged tree the gate is judging.
        head: The HEAD the gate diffed against.

    Returns:
        The status, and the lines that say why it is not 0.

    """
    if not (SHA.fullmatch(tree) and SHA.fullmatch(head)):
        why = f"the gate named no tree or HEAD ({tree!r}, {head!r})"
        return EXIT_CANNOT_JUDGE, [why]
    refused: list[str] = []
    unjudged: list[str] = []
    for verdict in verdicts:
        if isinstance(verdict, CannotJudge):
            unjudged.extend(verdict.why)
        elif verdict.state is State.PROBLEMS:
            refused.extend(verdict.problems)
        elif _stale(verdict, tree, head):
            unjudged.append(
                f"stale verdict: it judged tree {verdict.tree} against head "
                f"{verdict.head}, and the gate judges tree {tree} against {head}"
            )
    if refused:
        return EXIT_PROBLEMS, refused
    if unjudged or not verdicts:
        return EXIT_CANNOT_JUDGE, unjudged or ["no verdict was read"]
    return EXIT_OK, []


def judge(kind: str, files: list[Path]) -> Verdict:
    """Run one judgment over its input files.

    Returns:
        The verdict; an unreadable input, an unknown kind or the wrong input count is a
        CannotJudge.

    """
    if kind not in JUDGE_ARGS or len(files) != JUDGE_ARGS[kind]:
        why = f"{kind}: no such judgment, or the wrong inputs ({len(files)})"
        return CannotJudge([why])
    try:
        first, *rest = (_read(path) for path in files)
    except VerdictError as err:
        return CannotJudge([f"{kind}: {err}"])
    if kind == "named_inputs":
        return named_inputs_verdict(first, rest[0], rest[1])
    if kind == "wheels":
        return wheels_verdict(first, rest[0])
    return working_card_verdict(first, rest[0])


def read_dir(directory: Path) -> list[Verdict]:
    """Read the verdict of every kind from a directory; a missing one is a CannotJudge.

    Returns:
        One verdict per kind, in KINDS order.

    """
    out: list[Verdict] = []
    for kind in KINDS:
        try:
            out.append(parse_verdict(_read(directory / f"{kind}.json")))
        except VerdictError as err:
            out.append(CannotJudge([f"{kind}: {err}"]))
    return out


def main(argv: list[str]) -> int:
    """Run `judge` (a build action) or `status` (the gate's mapping).

    Returns:
        0 for `judge`; for `status` the gate's exit status; 2 on a usage error.

    """
    if len(argv) >= JUDGE_MIN and argv[0] == "judge":
        verdict = judge(argv[1], [Path(name) for name in argv[3:]])
        Path(argv[2]).write_text(verdict_text(verdict), encoding="utf-8")
        return EXIT_OK
    if len(argv) == STATUS_ARGS and argv[0] == "status":
        status, lines = exit_status(read_dir(Path(argv[1])), argv[2], argv[3])
        sys.stderr.write("".join(f"gate verdict: {line}\n" for line in lines))
        return status
    sys.stderr.write(__doc__ or "")
    return USAGE


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
