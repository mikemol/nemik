# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W330, W1006: nemik-work W<n>: mark W<n> working.

There is no limit on working cards (operator 2026-10-15, host 695f3e0a line 68086: requiring the
count to be one "is fragile and puts backpressure in some of the wrong places"). nemik-check warns
on none working while cards are ready, and the pre-commit hook refuses a code commit with none.
This marks W<n> working, clears its landed blockers, and demotes no other card, all through the one
writer, mikemol-paths-forward. It never edits the queue file itself.
"""

import sys
from pathlib import Path

from nemik._typing import TYPE_CHECKING
from nemik.say import say, warn
from nemik.spawn import FAILED, NO_LIMIT, Completed, capture
from nemik.tracker import DICT, LIST, NULL, STR, parse_tree

if TYPE_CHECKING:
    from nemik.tracker import Tree


def read_queue(state: Path) -> Tree:
    """Parse the queue file once, into a tree (nemik:W2125: Codon refuses json.loads here).

    Args:
        state: The queue file.

    Returns:
        The tree, its root the queue's object.

    """
    tree = parse_tree(state.read_text(encoding="utf-8"))
    _report_malformed(tree)
    return tree


def _is_card(tree: Tree, at: int) -> bool:
    """Say whether a value is an object with a string symbol, which the readers can use.

    Returns:
        True for a well-formed waypoint or residue entry.

    """
    return tree.kinds[at] == DICT and tree.kinds[tree.get(at, "symbol")] == STR


def _report_malformed(tree: Tree) -> None:
    """Say on stderr, once, which waypoints and residue entries the readers skip (nemik:W2125).

    The readers used to crash on an entry that is not an object or has no symbol and to stringify a
    symbol that is not a string. They skip such an entry instead, and this names each one, so the
    tolerance is never silent. An absent or null member is not malformed.
    """
    for key in ("waypoints", "residue"):
        held = tree.get(tree.root, key)
        if tree.kinds[held] == NULL:
            continue
        if tree.kinds[held] != LIST:
            warn(f"work: skipped malformed {key} (not an array)")
            continue
        for index, entry in enumerate(tree.kids[held]):
            if tree.kinds[entry] != DICT:
                warn(f"work: skipped malformed {key} element {index} (not an object)")
            elif tree.kinds[tree.get(entry, "symbol")] != STR:
                warn(
                    f"work: skipped malformed {key} element {index} (no string symbol)"
                )


def _objects(tree: Tree, at: int, key: str) -> list[int]:
    """Give the handles of the cards in an array member, none when it is not an array.

    Returns:
        One handle per well-formed entry (an object with a string symbol), in order.

    """
    held = tree.get(at, key)
    if tree.kinds[held] != LIST:
        return []
    return [h for h in tree.kids[held] if _is_card(tree, h)]


def _strings(tree: Tree, at: int, key: str, label: str) -> list[str]:
    """Give the string elements of an array member, none when it is not an array.

    A non-string element is dropped with one stderr line naming `label` (nemik:W2125).

    Returns:
        One string per string element, in order.

    """
    held = tree.get(at, key)
    if tree.kinds[held] != LIST:
        return []
    out: list[str] = []
    for item in tree.kids[held]:
        if tree.kinds[item] == STR:
            out.append(tree.texts[item])
        else:
            warn(f"work: dropped non-string element of {key} of {label}")
    return out


def working_cards(tree: Tree) -> list[str]:
    """Give the symbols of the cards currently working, read from the parsed queue.

    Returns:
        The symbols of the working cards.

    """
    return [
        tree.string(w, "symbol")
        for w in _objects(tree, tree.root, "waypoints")
        if tree.string(w, "status") == "working"
    ]


def working(state: Path) -> list[str]:
    """Give the symbols of the cards currently working, read from the queue file.

    Returns:
        The symbols of the working cards.

    """
    return working_cards(read_queue(state))


def blockers_of(tree: Tree, symbol: str) -> tuple[list[str], list[str]]:
    """(open, landed) entries of `symbol`'s blocked_on (nemik:W443), from the parsed queue.

    A local W<n> that is done, or dropped into residue, has landed. Anything else (a local card
    still open, another repo's card, free text) is open: this tool cannot see another repo's state,
    so it does not guess.

    Returns:
        The open entries, and the landed ones.

    """
    cards = {
        tree.string(w, "symbol"): w for w in _objects(tree, tree.root, "waypoints")
    }
    dropped = {tree.string(r, "symbol") for r in _objects(tree, tree.root, "residue")}
    entries = (
        _strings(tree, cards[symbol], "blocked_on", symbol) if symbol in cards else []
    )
    landed = [
        b
        for b in entries
        if b in dropped or (b in cards and tree.string(cards[b], "status") == "done")
    ]
    return [b for b in entries if b not in landed], landed


def blockers(state: Path, symbol: str) -> tuple[list[str], list[str]]:
    """(open, landed) entries of `symbol`'s blocked_on, read from the queue file (nemik:W443).

    Returns:
        The open entries, and the landed ones.

    """
    return blockers_of(read_queue(state), symbol)


class Env:
    """Where nemik-work finds its tools and makes its scratch directories (nemik:W2125).

    Both are given, never defaulted: the pinned Codon has no sys.executable and no tempfile, so the
    CPython shim builds this from the interpreter's directory and tempfile.gettempdir().
    """

    tool_dir: str
    temp_root: str

    def __init__(self, tool_dir: str, temp_root: str) -> None:
        """Hold the directory the mikemol tools are installed in and the scratch root."""
        self.tool_dir = tool_dir
        self.temp_root = temp_root


def run_writer(argv: list[str], env: Env) -> tuple[int, str]:
    """Run the one writer, mikemol-paths-forward, with the given arguments (nemik:W587).

    The single place nemik-work and nemik-ask start the writer, so neither edits a queue itself.

    Args:
        argv: The arguments after the writer's path, for example `--state PATH --update W1`.
        env: Where the writer is installed and where scratch directories go.

    Returns:
        The writer's exit status and its output (stderr when it failed, else stdout).

    """
    run = _spawn("mikemol-paths-forward", argv, NO_LIMIT, env)
    if run.returncode:
        return run.returncode, run.stderr.strip() or run.stdout.strip()
    return 0, run.stdout.strip()


COMMITTER_TIMEOUT = 20  # seconds the commit tool may take to answer a read-only mode
NOT_INSTALLED = 127


def _spawn(tool: str, argv: list[str], timeout: int, env: Env) -> Completed:
    """Run one of the tools installed in `env.tool_dir`, the only place nemik-work starts one.

    The directories are parameters because the pinned Codon has no sys.executable and no
    tempfile: the CLI shim (nemik.shims.work_cli) passes its interpreter's directory, as the code
    always looked, and the system temp root.
    A tool that is not installed, or that outlasts `timeout` seconds (NO_LIMIT, -1, waits as long as
    the tool takes), is a completed process with status 127 or 124 and no output. A tool that
    cannot be started is FAILED (71) with the error on stderr, and is never read as a timeout.

    Returns:
        The completed process.

    """
    path = Path(env.tool_dir) / tool
    if not path.is_file():
        return Completed([tool], NOT_INSTALLED, "", "")
    try:
        return capture([str(path), *argv], timeout, env.temp_root)
    except OSError as err:
        message = "nemik-work: could not run " + tool + ": " + str(err)
        return Completed([tool], FAILED, "", message)


def run_committer(argv: list[str], env: Env) -> tuple[int, str]:
    """Run mikemol-commit with the given arguments, as run_writer runs the writer (nemik:W682).

    For its read-only modes (`REPO --in-gate --json`); a missing tool or a hang is an exit status,
    never an exception, since the caller is a check that must not fail for it.

    Args:
        argv: The arguments after the tool's path.
        env: Where the tool is installed and where scratch directories go.

    Returns:
        The exit status and the standard output; 127 and nothing when the tool is not installed,
        124 and nothing after a timeout, FAILED (71) and a stderr line when it could not start.

    """
    run = _spawn("mikemol-commit", argv, COMMITTER_TIMEOUT, env)
    if run.returncode == FAILED:
        warn(run.stderr)
    return run.returncode, run.stdout


def named_waypoints(tree: Tree) -> set[str]:
    """Read the waypoints out of `mikemol-commit --in-gate --json` (a list of stack entries).

    Returns:
        Every waypoint any entry names; nothing for an answer that is not a list of entries.

    """
    named: set[str] = set()
    if tree.kinds[tree.root] != LIST:
        return named
    for row in tree.kids[tree.root]:
        if tree.kinds[row] == DICT:
            named.update(_strings(tree, row, "waypoints", "an in-gate entry"))
    return named


def in_gate(repo_dir: Path, env: Env) -> set[str]:
    """Name the waypoints a queued or gating commit stack of this repo carries (nemik:W682, W633).

    A card in the commit gate is being worked, however long the gate takes. The list comes from
    mikemol-commit's own public mode (`--in-gate --json`), never from its private files under
    .git/mtools. A missing tool, a failure or an unreadable answer names nothing.

    Args:
        repo_dir: The repository to ask about.
        env: Where mikemol-commit is installed and where scratch directories go.

    Returns:
        The waypoint symbols of the live stacks.

    """
    code, out = run_committer([str(repo_dir), "--in-gate", "--json"], env)
    if code != 0:
        return set()
    try:
        tree = parse_tree(out)
    except ValueError:
        return set()
    return named_waypoints(tree)


def plan(current: list[str], symbol: str) -> list[tuple[str, str]]:
    """(symbol, status) updates that mark `symbol` working and touch no other card.

    There is no one-working-card limit (operator 2026-10-15, host 695f3e0a line 68086): a round of
    cards being built, queued or gating are all working, so no working card is ever demoted.

    Returns:
        The (symbol, status) updates; none when the card is already working.

    """
    return [] if symbol in current else [(symbol, "working")]


USAGE = "usage: nemik-work [-h] [--state STATE] [--dry-run] [--force] symbol"
LONG_OPTIONS = ("--state", "--dry-run", "--force", "--help")
USAGE_ERROR = 2


class Options:
    """The parsed command line of nemik-work (nemik:W1187, W2126)."""

    symbol: str
    state: Path
    dry_run: bool
    force: bool

    def __init__(self) -> None:
        """Start with the defaults: no symbol, the queue file here, nothing forced."""
        self.symbol = ""
        self.state = Path(".claude/paths-forward.json")
        self.dry_run = False
        self.force = False


def _usage_error(message: str) -> int:
    # print the usage and the complaint on standard error, give the exit status of a usage error
    sys.stderr.write(f"{USAGE}\nnemik-work: error: {message}\n")
    return USAGE_ERROR


def _resolve(name: str) -> str:
    # a long option, or the one long option that `name` is a prefix of; "" for none or several
    if name in LONG_OPTIONS:
        return name
    found = [n for n in LONG_OPTIONS if n.startswith(name)]
    return found[0] if len(found) == 1 else ""


def _apply(out: Options, arg: str, argv: list[str], at: int) -> int:
    """Apply one option argument to `out`; `at` is the index after it in `argv`.

    Returns:
        The index of the next argument to read.

    Raises:
        SystemExit: 0 after the usage for -h, 2 for an unknown, ambiguous or malformed option.

    """
    name, has_value, value = arg.partition("=")
    long_name = _resolve(name) if arg.startswith("--") else ""
    resolved = "--help" if arg == "-h" else long_name
    if not resolved:
        raise SystemExit(_usage_error(f"unrecognized arguments: {arg}"))
    if resolved == "--help":
        sys.stdout.write(f"{USAGE}\n")
        raise SystemExit(0)
    if resolved == "--state":
        if has_value:
            out.state = Path(value)
            return at
        if at < len(argv) and (not argv[at].startswith("-") or argv[at] == "-"):
            out.state = Path(argv[at])
            return at + 1
        raise SystemExit(_usage_error("argument --state: expected one argument"))
    if has_value:
        raise SystemExit(
            _usage_error(f"argument {resolved}: ignored explicit argument {value!r}")
        )
    if resolved == "--dry-run":
        out.dry_run = True
    else:
        out.force = True
    return at


def parse(argv: list[str]) -> Options:
    """Read the command line of nemik-work without argparse (nemik:W2126).

    One positional (the waypoint) and --state PATH, --dry-run, --force and -h, as argparse took
    them: a long option may be given as a unique prefix or as --name=value, and a bare -- ends
    the options.

    Args:
        argv: The arguments after the program name.

    Returns:
        The parsed options.

    Raises:
        SystemExit: 0 after the usage for -h, 2 for a missing or extra argument or a bad option.

    """
    out = Options()
    positional: list[str] = []
    at = 0
    while at < len(argv):
        arg = argv[at]
        at += 1
        if arg == "--":
            positional.extend(argv[at:])
            break
        if not arg.startswith("-") or arg == "-":
            positional.append(arg)
        else:
            at = _apply(out, arg, argv, at)
    if not positional:
        raise SystemExit(_usage_error("the following arguments are required: symbol"))
    if len(positional) > 1:
        raise SystemExit(
            _usage_error(f"unrecognized arguments: {' '.join(positional[1:])}")
        )
    out.symbol = positional[0]
    return out


def main(argv: list[str], env: Env) -> int:
    """nemik-work: mark one card working and clear its landed blockers, touching no other card.

    Args:
        argv: The command line after the program name.
        env: Where the writer is installed and where scratch directories go.

    Returns:
        0 when done, 2 when the card is blocked, else the writer's nonzero code.

    """
    args = parse(argv)
    queue = read_queue(args.state)
    still, landed = blockers_of(queue, args.symbol)
    if still and not args.force:
        # nemik:W443: working a blocked card left it 'working' with a stale blocked_on (W441).
        warn(
            f"nemik-work: {args.symbol} is blocked on {', '.join(still)}; "
            "land or unblock those first, or pass --force"
        )
        return 2
    steps = plan(working_cards(queue), args.symbol)
    for symbol, status in steps:
        note = f" (cleared landed blocker(s): {', '.join(landed)})" if landed else ""
        say(f"{symbol} -> {status}{note}")
        if args.dry_run:
            continue
        cmd = ["--state", str(args.state), "--update", symbol, "--status", status]
        if landed:
            # keep only what is still open; with nothing open the list is emptied
            cmd += ["--blocked-on", *still]
        code, said = run_writer(cmd, env)
        if code:
            warn(said)
            return code
    return 0
