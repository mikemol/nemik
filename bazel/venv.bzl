# Vendored from mtools//:venv.bzl (Apache-2.0, Copyright (c) 2026 Mike Mol), unchanged but for this line;
# nemik:W96 builds its .venv the way every mtools distribution does.
"""A distribution's `.venv`, built as an artifact rather than left as host state.

⚑⚑⚑ THE OPERATOR DIRECTION THIS ANSWERS: *"All projects in this repo should be constructing
their .venv the same way -- as a build artifact. This should be a trivially-templatizable
thing."* Four distributions, one macro, one call each.

⚑⚑ AND IT DUPLICATES CONSTRUCTION rules_python ALREADY DOES, KNOWINGLY. `venv_runfiles.bzl`
builds `_<target>.venv/bin/python3` for every `py_test`/`py_binary` — that is what
`sys.executable` names inside an action, measured. The operator was shown this and ruled for a
whole-distribution venv anyway, because a PER-TARGET venv cannot be ACTIVATED, and this
repository has three non-bazel consumers that reach `<dist>/.venv/bin/...`: `.githooks/pre-commit`
(12 call sites), `preflight.sh` (6) — measured `grep -c .venv/bin/` at 35931c3, an earlier draft said 13/7 and had drifted — and the interactive dev loop. Those are the users; the
duplication is the price.

⚑ WHAT IS NOT DUPLICATED: no resolver, no installer, no network. The wheels arrive already
unpacked through `pip.parse`, which `MODULE.bazel` declares. This macro only ARRANGES staged
files into the layout a venv has.
"""

# ⚑⚑ MEASURED, NOT ASSUMED: `@<hub>//<pkg>:extracted_whl_files` is a plain `filegroup` carrying
# individual `File`s (checked with `cquery --output=files`, and its providers are
# DefaultInfo/FileProvider — no tree artifact, no custom provider to unwrap). Every path inside it
# is prefixed `site-packages/`, which is what makes the destination computable by stripping.
# ⚑ THE ADJACENT `whl_filegroup` RULE IS A DIFFERENT TARGET and does use `declare_directory`; its
# docstring points AT `extracted_whl_files` as a separate thing. Reading one for the other would
# have produced a rule built on a tree artifact that is not there.
_SITE = "site-packages/"

def _venv_impl(ctx):
    outs = []

    # ⚑⚑⚑ THE INTERPRETER LINK IS ABSOLUTE — operator ruling 2026-09-19, REVERSING the relative
    # link this rule carried from its first draft. The earlier reasoning ("a venv whose `bin/python3`
    # is an ABSOLUTE symlink stops working the moment the interpreter moves") measured a true
    # thing and drew the wrong line: a RELATIVE link also dies when the interpreter moves, and it
    # additionally works at exactly ONE depth. `pyvenv.cfg`'s `home` remains INERT (rewriting it to
    # `/nonexistent/nowhere` changed nothing); the symlink is still the real dependency.
    #
    # ⚑⚑⚑ MEASURED, THE DEFECT THE RELATIVE LINK PRODUCED: `//ratchet:mutants` staged all 2,070
    # venv files into its runfiles tree, and `bin/python3` there carried the same six-`../` text it
    # has in `bazel-bin/ratchet/.venv/bin/` — from `<test>.runfiles/_main/ratchet/.venv/bin/`, six
    # up is `bazel-bin`, which has no `external/`, so the link dangled and `mutate_check.sh`
    # refused on `-x`, correctly. The previous draft's own comment named the two coordinate systems
    # (`path` = execroot, `short_path` = runfiles) and could only serve one of them with one
    # relative string. A runfiles-only second link (`ctx.runfiles(symlinks=…)`) was probed and
    # loses to `data=`'s file at the same short_path unless the built link leaves `files=`, which
    # breaks `bazel build //<dist>:.venv`. One absolute link serves both, and the sandbox too.
    #
    # ⚑ `declare_file` + `target_file`, NOT `declare_symlink` + a hand-built path: bazel writes the
    # resolved target itself, so no coordinate-system arithmetic is done here at all. That
    # arithmetic is where the first draft's `short_path` bug lived (an external file's short_path
    # begins `../`, and the common-prefix walk counted it as a segment).
    interpreter = ctx.toolchains["@rules_python//python:toolchain_type"].py3_runtime.interpreter
    python3 = ctx.actions.declare_file(ctx.attr.name + "/bin/python3")
    ctx.actions.symlink(output = python3, target_file = interpreter, is_executable = True)
    outs.append(python3)

    # ⚑ `pyvenv.cfg` IS WRITTEN BECAUSE A VENV IS DEFINED BY ITS PRESENCE. `home` does not decide
    # RELOCATABILITY — measured, rewriting it to `/nonexistent/nowhere` changed nothing about
    # whether the venv runs, because `bin/python3` is the real dependency.
    #
    # ⚑⚑ IT NOW NAMES THE INTERPRETER'S OWN DIRECTORY rather than `../bin`, which resolved to
    # `bazel-out/.../hooks/bin` — a directory the interpreter does not live in. Correct on its own
    # terms, and derived from the same File the symlink above points at rather than written out.
    #
    # ⚑⚑⚑ AND IT IS NOT THE FIX FOR THE `Could not find platform dependent libraries <exec_prefix>`
    # WARNING, WHICH IS WHAT I CHANGED IT FOR. FIVE hypotheses, four refuted before the fifth held:
    #
    #   H1 `home` names the wrong directory   corrected it — warning PERSISTS
    #   H2 no `lib-dynload` under the venv    the HOST venv has the identical
    #                                         `lib/python3.13/site-packages`-only shape and is QUIET
    #   H3 the toolchain binary warns         run directly, outside any venv: QUIET
    #   H4 the symlink-chain shape differs    built BOTH shapes over the same toolchain in a
    #                                         scratch tree: BOTH QUIET
    #   H5 the `bazel-bin` CONVENIENCE SYMLINK ✅ — the same venv, two paths, one variable:
    #        via bazel-bin   warns, prefix=/home/mikemol/github/mtools/bazel-bin/hooks/.venv
    #        via the real path  QUIET, prefix=.../execroot/_main/bazel-out/.../hooks/.venv
    #
    # ⚑ CPython resolves `sys.executable` WITHOUT following `bazel-bin`, computes `exec_prefix`
    # beneath it, and cannot find the platform libraries there. `sys.prefix`, `exec_prefix` and the
    # stdlib all still resolve — it is diagnostic noise on stderr, not breakage — and it is a
    # property of the PATH THE CALLER USED, which no change to this rule can remove. The tracked
    # launcher can, by naming the real path; recorded here so the next reader does not re-fix
    # `home` for it.
    #
    # ⚑⚑⚑ `home` IS NOT INERT ONCE THE LINK IS ABSOLUTE — the measurement above was taken where
    # the relative link already resolved on its own. With an absolute `bin/python3` invoked from a
    # runfiles tree, a `home` computed for bazel-bin's depth pointed nowhere and CPython died with
    # `Failed to import encodings module` (measured, `//ratchet:mutants`, 2026-09-19). So `home`
    # names the venv's OWN `bin/`: CPython follows the absolute symlink it finds there to the
    # toolchain, and the stdlib resolves from the real interpreter. MEASURED depth-independent
    # (a scratch venv four directories deeper, run from `/`): `stdlib = <toolchain>/lib/python3.13`,
    # scheme `venv`, no warning. No coordinate arithmetic remains in this rule.
    cfg = ctx.actions.declare_file(ctx.attr.name + "/pyvenv.cfg")
    ctx.actions.write(
        output = cfg,
        content = "home = bin\ninclude-system-site-packages = false\nversion = {}\n".format(
            ctx.attr.python_version,
        ),
    )
    outs.append(cfg)

    # ⚑⚑ THE CLOSURE COMES FROM `deps`, WHICH COMES FROM THE GRAPH -- NOT FROM A DIRECTORY SCAN.
    # MEASURED WHY: scanning `external/rules_python++pip+hooks_*` finds 39 directories, of which 2
    # have no `site-packages` at all (the hub aliases `hooks_deps`/`hooks_dev` themselves) and the
    # rest are DUPLICATE PAIRS -- a short alias and a long platform-tagged name resolving to the
    # same wheel. A hand-assembled probe survived that only because duplicate basenames collide
    # harmlessly. A rule must not rest on a coincidence.
    site = ctx.attr.name + "/lib/python" + ctx.attr.python_version_short + "/site-packages"
    seen = {}
    for dep in ctx.attr.deps:
        for f in dep[DefaultInfo].files.to_list():
            # ⚑ `path` HERE TOO, for one coordinate system throughout — though this use only
            # needs the `site-packages/` marker and its tail, which both views agree on.
            idx = f.path.find(_SITE)
            if idx < 0:
                continue  # the .whl itself, metadata.json, MODULE.bazel -- not venv content
            rel = f.path[idx + len(_SITE):]
            if rel in seen:
                continue  # the duplicate-hub pairs measured above resolve to identical files
            seen[rel] = True
            out = ctx.actions.declare_file(site + "/" + rel)
            ctx.actions.symlink(output = out, target_file = f)
            outs.append(out)

    # ⚑⚑⚑ THE DISTRIBUTION'S OWN SOURCE IS NOT A DEPENDENCY AND MUST STILL BE PRESENT. Measured:
    # the venv built from `deps` alone runs pytest and then dies on
    # `ModuleNotFoundError: No module named 'mikemol'` — CORRECT behaviour, not a defect. A venv
    # holds a project's dependencies; the project itself arrives by an EDITABLE INSTALL, which is
    # exactly the host-state step this rule exists to remove.
    # ⚑⚑ SO IT IS DECLARED RATHER THAN INFERRED. `srcs` names the package roots to expose, and a
    # distribution that names none gets a dependencies-only venv — which is a legitimate thing to
    # want and should not be silently "fixed" by a rule guessing at `src/`.
    for f in ctx.files.srcs:
        idx = f.path.find(ctx.attr.src_root + "/")
        if idx < 0:
            continue
        rel = f.path[idx + len(ctx.attr.src_root) + 1:]
        out = ctx.actions.declare_file(site + "/" + rel)
        ctx.actions.symlink(output = out, target_file = f)
        outs.append(out)

    # ⚑⚑⚑ CONSOLE SCRIPTS: NO SHEBANG CAN BE RIGHT, SO A `/bin/sh` PREAMBLE CHOOSES AT RUN TIME.
    # Three shebang shapes were measured, two working directories:
    #
    #     #!<abs>/python3          runs from ANY cwd, under the venv's own interpreter — but the
    #                              absolute path is the OUTPUT BASE's, which analysis cannot see,
    #                              which a sandbox or remote executor would bake in as its own, and
    #                              which a shared cache would then hand to every other host
    #     #!./python3              POSIX resolves `#!` against the CWD, not the script's
    #                              directory — ran the toolchain python directly from the bin
    #                              dir, and could not exec at all from elsewhere
    #     #!/usr/bin/env python3   ran, and ran the HOST mise python — the exact leak this
    #                              whole direction exists to remove
    #
    # ⚑⚑ AND NO SHEBANG AT ALL IS WORSE THAN ANY OF THEM: measured 2026-09-23, a direct run of a
    # shebang-less entry is handed to the SHELL, which reports `line 4: import: command not found`
    # and a syntax error on line 7. The preamble in `_CONSOLE_SCRIPT` does what the tracked
    # launchers already do — resolve the script's real path, then exec the `bin/python3` beside it —
    # and is a string literal to Python, so `python3 bin/<entry>` (the launchers' form) still works.
    for entry, target in ctx.attr.console_scripts.items():
        mod, _, fn = target.partition(":")
        script = ctx.actions.declare_file(ctx.attr.name + "/bin/" + entry)
        ctx.actions.write(
            output = script,
            is_executable = True,
            content = _CONSOLE_SCRIPT.format(module = mod, function = fn),
        )
        outs.append(script)

    # ⚑⚑ THE TOOLCHAIN'S OWN FILES ARE RUNFILES OF THE VENV. `bin/python3` names the interpreter,
    # but the interpreter needs its `lib/python3.13` beside it, and a sandbox stages only what is
    # DECLARED. MEASURED 2026-09-19: `//ratchet:mutants` with the link and `home` both correct
    # still died with `No module named 'encodings'` under linux-sandbox and PASSED (13 attempted,
    # 11 killed, 0 survived, 2 unreachable) under `--spawn_strategy=local` — one flag, one
    # variable, so the missing thing was a declaration and not a path.
    runtime = ctx.toolchains["@rules_python//python:toolchain_type"].py3_runtime

    # ⚑⚑⚑ AND UNDER A SANDBOX THE LINK IS NOT A LINK. Printed from a kept sandbox (`--sandbox_debug`,
    # 2026-09-19): bazel resolves a symlink artifact at staging and HARDLINKS the interpreter into
    # `.venv/bin/python3` (link count 5, a regular file). There is nothing for CPython to follow,
    # `home = bin` names itself, and the toolchain sits at `<runfiles>/<repo>/` where nothing
    # points. `PYTHONHOME=<runfiles>/<repo>` MEASURED in that sandbox: scheme `venv`, site-packages
    # under the venv, stdlib from the staged toolchain. The repo's runfiles-relative name is the
    # one fact the checker cannot derive, so it is written here for `mutate_check.sh` to read.
    # ⚑ `short_path` of an external file begins `../<repo>/…` — the exact shape the earlier draft
    # mis-walked; here only the first segment after `../` is taken, no prefix arithmetic.
    toolchain_repo = interpreter.short_path.removeprefix("../").split("/", 1)[0]
    home_note = ctx.actions.declare_file(ctx.attr.name + "/pythonhome.runfiles")
    ctx.actions.write(output = home_note, content = toolchain_repo + "\n")
    outs.append(home_note)

    return [DefaultInfo(
        files = depset(outs),
        runfiles = ctx.runfiles(files = outs, transitive_files = runtime.files),
    )]

# ⚑⚑ NO BAKED INTERPRETER PATH IN THE TEMPLATE, AND THAT IS THE POINT. A baked absolute path would
# name this build's output base forever. The first three lines are a sh/Python polyglot: `/bin/sh`
# reads `'''exec'` as `exec` and runs the `python3` beside the script's RESOLVED path (the realpath
# is what keeps `bazel-bin`'s exec_prefix warning away, as in the launchers); Python reads the same
# lines as one string literal and skips them. So a direct run and `python3 bin/<entry>` — the form
# the tracked launchers use from `$CLAUDE_PROJECT_DIR` — both reach one interpreter.
# ⚑ The `sys.path` line makes the venv's own site-packages reachable when
# the script is run by an interpreter that is not this venv's, which is what lets one launcher
# serve a venv whose absolute location is only known at run time.
_CONSOLE_SCRIPT = """\
#!/bin/sh
'''exec' "$(dirname -- "$(readlink -f -- "$0")")/python3" "$(readlink -f -- "$0")" "$@"
' '''
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
# GENERATED by //:venv.bzl — do not edit. Declared in the distribution's pyproject.toml.
import sys
from pathlib import Path

_site = Path(__file__).parent.parent / "lib"
for _libdir in sorted(_site.glob("python*/site-packages")):
    if str(_libdir) not in sys.path:
        sys.path.insert(0, str(_libdir))

from {module} import {function}

if __name__ == "__main__":
    sys.exit({function}())
"""

def _relative_path(from_file, to_file):
    """Path from `from_file`'s DIRECTORY to `to_file`, as `../` segments plus a tail."""
    from_parts = from_file.split("/")[:-1]  # drop the filename: we walk from its directory
    to_parts = to_file.split("/")
    common = 0
    for i in range(min(len(from_parts), len(to_parts) - 1)):
        if from_parts[i] != to_parts[i]:
            break
        common += 1
    return "/".join([".."] * (len(from_parts) - common) + to_parts[common:])

venv = rule(
    implementation = _venv_impl,
    doc = "Assembles a relocatable venv from wheels bazel has already staged.",
    attrs = {
        "deps": attr.label_list(
            doc = "`@<hub>//<pkg>:extracted_whl_files` targets to place in site-packages.",
            allow_files = True,
        ),
        "python_version": attr.string(mandatory = True, doc = "Full version, e.g. 3.13.13."),
        "python_version_short": attr.string(mandatory = True, doc = "Major.minor, e.g. 3.13."),
        "src_root": attr.string(
            default = "src",
            doc = "Directory under which `srcs` paths become site-packages-relative.",
        ),
        "srcs": attr.label_list(
            allow_files = True,
            doc = "The distribution's OWN sources, standing in for an editable install.",
        ),
        "console_scripts": attr.string_dict(
            doc = "`entry-name: module:function`, mirroring `[project.scripts]` in pyproject.toml.",
        ),
    },
    toolchains = ["@rules_python//python:toolchain_type"],
)

def venv_from_hub(
        name,
        hub_requirements,
        python_version,
        python_version_short,
        srcs = None,
        src_root = "src",
        console_scripts = None):
    """The templatizable form: one call per distribution, population taken from the hub.

    ⚑⚑⚑ THIS IS WHERE "TRIVIALLY TEMPLATIZABLE" LIVES. A distribution says its name, its hub's
    generated `all_requirements`, and its Python version. Everything else is derived.

    ⚑⚑ THE `:pkg` -> `:extracted_whl_files` REWRITE IS HERE RATHER THAN AT EACH CALL SITE, because
    `pip.parse` generates accessors for `pkg`/`whl`/`data`/`dist_info` and NONE for the extracted
    files -- measured by reading the generated `requirements.bzl`, after a first draft guessed a
    `_extracted` suffix that names nothing. Doing the rewrite once means a wrong guess is wrong in
    one place, not four.

    Args:
        name: the venv directory, conventionally `.venv`.
        hub_requirements: the hub's generated `all_requirements` list.
        python_version: full version string, e.g. `3.13.13`.
        python_version_short: major.minor, e.g. `3.13`.
        srcs: the distribution's own sources, standing in for an editable install.
        src_root: directory under which `srcs` paths become site-packages-relative.
        console_scripts: `entry-name: module:function`, mirroring `[project.scripts]`.
    """
    venv(
        name = name,
        console_scripts = console_scripts or {},
        deps = [r.removesuffix(":pkg") + ":extracted_whl_files" for r in hub_requirements],
        python_version = python_version,
        python_version_short = python_version_short,
        src_root = src_root,
        srcs = srcs or [],
    )
