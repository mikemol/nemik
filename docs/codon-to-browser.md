# How the typed core reaches the browser

nemik's typed core is Python that the pinned Codon compiler turns into a native binary. The browser view needs
the same core's output. This note names the three ways to get from one to the other, says which one is
buildable today, and says what would make us look again. It answers nemik:W564 and unblocks nemik:W423.

## The three options

1. **Ask for or wait for a wasm32 output from Codon itself.** Codon 0.20.3's build options set no wasm target
   triple, so this is not in our hands and has no date.
2. **Port Codon's runtime to wasm32.** The compiled program needs Codon's runtime (libcodonrt, which carries the
   Boehm garbage collector). Running it in a browser would need that runtime built for wasm32. On 2026-10-16 the host
   had clang, llc and wasm-ld, but no WASI sysroot (a search of /usr and /opt found only cmake platform files and
   Go's wasip1 sources) and no wasm32 compiler-rt builtins under /usr/lib/llvm/23. So the host packages are
   missing first, and after them comes a port of the runtime that we have not seen done anywhere.
3. **Run the typed core natively and let the browser read its JSON.** Measured on 2026-10-16: a 386,000-byte
   native binary reads and writes the same JSON the browser would. This is buildable now.

## Decision

One Codon source, two compile targets, for two different jobs (github-00's ruling, 2026-11-22). They are
not rivals, and no function is spelled twice.

- **Native, a PRODUCER at publish time (option 3).** The native binary replaces the Python producer of the
  static pieces, `hashes.json` and `graph/*.json`. The page reads them exactly as it does today
  (`sourceGraph` in `src/nemik/web/panels.js`); nothing in the request path changes. This is the transport
  choice nemik:W423 left open: a static file, the build step's output, not a request to a server.
- **core.wasm, COMPUTE in the page at view time (option 2, now built).** Pure functions over pieces the page
  has already loaded run as wasm, for example `combine` once nemik:W1028 ports it
  (`docs/core-combine-schema.md` is its contract).

The rule that places a function: if it needs only data the page already has and runs per view, it is wasm; if
it makes the data, it is native at publish time.

What changed since 2026-10-16: the tree gained a `core.wasm` build, and the gate builds it by Codon's label
and refuses when the tool is absent (nemik:W2379, `tools/build_wasm.sh`, `tools/gate_wasm.sh`); nemik:W1028
is the first port that calls a function through it. So options 1 and 2 are no longer only a revisit trigger.

## What this does not claim

- It does not claim every function can run as wasm: only the ones the tree has compiled (W1028's list grows
  one function at a time).
- The 386,000-byte figure is a single measurement from 2026-10-16, not a tracked series, and the doc does not
  say the binary is built by the current tree.
- It does not name the native binary's output directory or how the static build invokes it. That is
  nemik:W2148's build, and `graphText` in `panels.js` (the combiner of several sources, called once by
  `load`) is deleted there only if nothing in the page still calls it.

## Revisit trigger

Look again at the native producer when `core.wasm` can run the whole pieces build in the page, which needs
Codon upstream to ship a wasm32 target triple or the host to gain a WASI sysroot and wasm32 compiler-rt
builtins for the runtime the pieces build needs.
