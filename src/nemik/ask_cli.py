# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W587: nemik-ask, file an ask: mint the filer's waypoint, then write the entry citing it.

    nemik-ask --filer life --to mtools --slug ask-x-does-y --claim "x does not do y"     (dry run)
    nemik-ask --filer life --to mtools --slug ask-x-does-y --claim "..." --apply

The waypoint is minted in the FILER's queue through the one writer (`mikemol-paths-forward --add`,
then blocked on the owner), never by editing the file. Only then is the entry written to the floor
inbox with `waypoint = {<filer>:W<n>}`, because summit's place_intake refuses a pointer to a card
that is absent. The result is checked: the entry must be on the floor after writing.

nemik:W943: after filing, the same ask is printed as an ActivityStreams Offer addressed to the
owner (nemik.ask.offer), so a peer outside summit's tooling can read it. Nothing else is written:
summit's inbox takes bib letters only.

nemik:W2164 (codon paydown): the command line is read by hand and the tools' location is an Env, as
nemik.work does (W2125, W2126): argparse and the CPython-only shim's tempfile were the two walls
this module reached. The CPython entry that fills the Env is nemik.shims.ask_cli.
"""

import sys
from pathlib import Path

from nemik.ask import blocked_on, braces_balanced, entry, offer, slug_ok, title
from nemik.work import Env, run_writer

DEFAULT_FLOOR = Path.home() / "github" / "summit" / "floor" / "inbox"
USAGE = (
    "usage: nemik-ask [-h] --filer FILER --to TO --slug SLUG --claim CLAIM "
    "[--owner-card OWNER_CARD] [--state STATE] [--floor FLOOR] [--apply]"
)
VALUE_OPTIONS = (
    "--filer",
    "--to",
    "--slug",
    "--claim",
    "--owner-card",
    "--state",
    "--floor",
)
LONG_OPTIONS = (*VALUE_OPTIONS, "--apply", "--help")
REQUIRED = ("--filer", "--to", "--slug", "--claim")
USAGE_ERROR = 2


class Options:
    """The parsed command line of nemik-ask (nemik:W2164)."""

    filer: str
    to: str
    slug: str
    claim: str
    owner_card: str
    state: Path
    floor: Path
    apply: bool

    def __init__(self) -> None:
        """Start with the defaults: nothing given, the queue file here, the summit floor."""
        self.filer = ""
        self.to = ""
        self.slug = ""
        self.claim = ""
        self.owner_card = ""
        self.state = Path(".claude/paths-forward.json")
        self.floor = DEFAULT_FLOOR
        self.apply = False


def _usage_error(message: str) -> int:
    # print the usage and the complaint on standard error, give the exit status of a usage error
    sys.stderr.write(f"{USAGE}\nnemik-ask: error: {message}\n")
    return USAGE_ERROR


def _resolve(name: str) -> str:
    # a long option, or the one long option that `name` is a prefix of; "" for none or several
    if name in LONG_OPTIONS:
        return name
    found = [n for n in LONG_OPTIONS if n.startswith(name)]
    return found[0] if len(found) == 1 else ""


def _set(out: Options, option: str, value: str) -> None:
    # store one option's value on `out`
    if option == "--filer":
        out.filer = value
    elif option == "--to":
        out.to = value
    elif option == "--slug":
        out.slug = value
    elif option == "--claim":
        out.claim = value
    elif option == "--owner-card":
        out.owner_card = value
    elif option == "--state":
        out.state = Path(value)
    else:
        out.floor = Path(value)


def _apply(out: Options, arg: str, argv: list[str], at: int, seen: list[str]) -> int:
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
    if resolved == "--apply":
        if has_value:
            raise SystemExit(
                _usage_error(f"argument --apply: ignored explicit argument {value!r}")
            )
        out.apply = True
        return at
    seen.append(resolved)
    if has_value:
        _set(out, resolved, value)
        return at
    if at < len(argv) and (not argv[at].startswith("-") or argv[at] == "-"):
        _set(out, resolved, argv[at])
        return at + 1
    raise SystemExit(_usage_error(f"argument {resolved}: expected one argument"))


def parse(argv: list[str]) -> Options:
    """Read the command line of nemik-ask without argparse (nemik:W2164).

    The four required options (--filer, --to, --slug, --claim), --owner-card, --state, --floor,
    --apply and -h, as argparse took them: a long option may be given as a unique prefix or as
    --name=value. A bare -- is refused with whatever follows it: there is no positional for it to
    release (argparse of Python 3.14 reports it as unrecognized).

    Args:
        argv: The arguments after the program name.

    Returns:
        The parsed options.

    Raises:
        SystemExit: 0 after the usage for -h, 2 for a missing option, an extra argument or a bad
            option.

    """
    out = Options()
    seen: list[str] = []
    extra: list[str] = []
    at = 0
    while at < len(argv):
        arg = argv[at]
        at += 1
        if arg == "--":
            extra.append(arg)
            extra.extend(argv[at:])
            break
        if not arg.startswith("-") or arg == "-":
            extra.append(arg)
        else:
            at = _apply(out, arg, argv, at, seen)
    missing = [name for name in REQUIRED if name not in seen]
    if missing:
        raise SystemExit(
            _usage_error(f"the following arguments are required: {', '.join(missing)}")
        )
    if extra:
        raise SystemExit(_usage_error(f"unrecognized arguments: {' '.join(extra)}"))
    return out


def _refusal(slug: str, claim: str, target: Path) -> str:
    """Say what is wrong with the request, or nothing.

    Args:
        slug: The proposed key.
        claim: The ask's text.
        target: The floor file it would be written to.

    Returns:
        A one-line reason, empty when the request is fine.

    """
    if not slug_ok(slug):
        return f"slug {slug!r} must be lowercase letters, digits and hyphens"
    if not claim.strip():
        return "the claim is empty"
    if not braces_balanced(claim):
        return "the claim's braces do not balance, so it cannot sit in a BibTeX field"
    if target.exists():
        return (
            f"{target} already exists: pick another slug, never overwrite a filed ask"
        )
    return ""


def _mint(state: Path, card_title: str, wait: str, env: Env) -> tuple[int, str]:
    """Mint the filer's waypoint through the writer and block it on the owner.

    Args:
        state: The filer's queue file.
        card_title: The waypoint's title.
        wait: What it waits on.
        env: Where the writer is installed and where scratch directories go.

    Returns:
        (0, the new symbol) on success, else (a non-zero status, why).

    """
    code, said = run_writer(["--state", str(state), "--add", card_title], env)
    symbol = said.split()[0] if said.split() else ""
    if code or not symbol.startswith("W"):
        return code or 1, f"the writer did not mint a card: {said}"
    block = ["--state", str(state), "--update", symbol, "--status", "blocked"]
    code, said = run_writer(
        [*block, "--blocked-on", wait, "--blocked-kind", "agent"], env
    )
    if code:
        return code, f"{symbol} was minted but not blocked: {said}"
    return 0, symbol


def main(argv: list[str], env: Env) -> int:
    """File an ask: mint the filer's waypoint, then write the floor entry.

    Args:
        argv: The arguments after the program name.
        env: Where the writer is installed and where scratch directories go.

    Returns:
        0 on success (or a dry run), 2 on a refused request, the writer's status if it failed.

    """
    args = parse(argv)
    target = args.floor / f"{args.slug}.bib"
    reason = _refusal(args.slug, args.claim, target)
    if reason:
        sys.stderr.write(f"nemik-ask: {reason}\n")
        return 2
    wait = blocked_on(args.to, args.owner_card)
    if not args.apply:
        sys.stdout.write(
            f"would mint in {args.state}: {title(args.to, args.claim)!r}, blocked on {wait}\n"
            f"would write {target}:\n{entry(args.slug, args.filer, args.to, args.claim, 'W?')}"
        )
        return 0
    code, symbol = _mint(args.state, title(args.to, args.claim), wait, env)
    if code:
        sys.stderr.write(f"nemik-ask: {symbol}\n")
        return code
    target.write_text(
        entry(args.slug, args.filer, args.to, args.claim, symbol), encoding="utf-8"
    )
    if not target.exists():
        sys.stderr.write(f"nemik-ask: {target} is not there after writing\n")
        return 1
    sys.stdout.write(f"filed {args.filer}:{symbol} blocked on {wait}; entry {target}\n")
    sys.stdout.write(offer(args.slug, args.filer, args.to, args.claim, symbol))
    return 0
