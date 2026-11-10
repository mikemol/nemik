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

Take option 3. It is the only one that can be built today, and the browser needs the core's JSON output, not
the core running inside the page.

## What this does not claim

- It does not claim the browser can run Codon-compiled code. It cannot, until option 1 or 2 changes.
- The 386,000-byte figure is a single measurement from 2026-10-16, not a tracked series, and the doc does not
  say the binary is built by the current tree.
- It does not decide how the browser asks the native binary for its JSON (a file, a request to the server, a
  build step). That belongs to nemik:W423.

## Revisit trigger

Look again at options 1 and 2 when either of these becomes true:

- Codon upstream ships a wasm32 target triple, or
- the host gains a WASI sysroot and wasm32 compiler-rt builtins.

Until then the native path stands.
