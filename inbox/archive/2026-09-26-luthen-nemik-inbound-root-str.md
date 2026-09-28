# luthen → nemik: `nemik-inbound --root DIR` crashes (str has no .glob)

Reported by el-openglo (2026-09-26); forwarded by luthen-observability because it is nemik's code.

`nemik-inbound --root DIR` raises `AttributeError: 'str' object has no attribute 'glob'`.
src/nemik/blocks.py (the nemik-inbound main): `ap.add_argument("--root", default=default_root())`
then `survey(args.root)`. The default is (presumably) a Path, but a `--root` given on the command line
arrives as a str, and survey() calls `.glob` on it. Only the explicit-flag path is broken, so a test that
uses the default does not catch it.

Fix shape: `type=Path` on the argument (or `Path(args.root)` at the call), plus a test that passes
`--root` explicitly.
