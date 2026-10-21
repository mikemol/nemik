# Python to Codon to wasm (nemik:W813, for the goal W812)

Operator, 2026-10-20: the page's JS that is being extracted is to be rewritten in Python, compiled
by Codon to wasm, as the way the web interface and the CLI tools share code, "since the rest of the
tooling is supposed to already be codon-ready". This is the spike: does the path exist, and what does
it need.

## It works

Three exported Python functions, built with the pinned Codon (the one `test_codon_pin` stages) and
called from node. Each ran and returned the right answer:

| Function | Uses | Result |
|---|---|---|
| `mix(a, b) = a*b + 1` | integers only | `mix(3, 4) = 13` |
| `total(n)`: sum of a list comprehension of squares | list allocation | `total(5) = 30` |
| `spread(n)`: a dict keyed by `"card-" + str(i % 7)`, sorted | str, dict, sorted | `spread(20) = 706` (7 keys, first of length 6) |

## The path

    codon build --release -o X.ll X.py          # @export keeps the function; IR, not a binary
    llc -mtriple=wasm64-unknown-unknown -mcpu=generic -filetype=obj -o X.o X.ll
    wasm-ld -mwasm64 --no-entry --export=FN --export=__heap_base --allow-undefined --gc-sections -o X.wasm X.o

- `@export` on a function keeps it in the IR; `--lib` writes a native shared object instead, so it is
  not used. Codon's IR carries x86 CPU attributes (`znver3` and a long feature list): `llc` ignores
  them with a warning per attribute, so its stderr is discarded.
- wasm64 (memory64), because Codon's lengths and pointers are 64-bit. Node 26 loads it with no flag.
  Integers cross the boundary as `BigInt`.
- `llc`, `clang` and `wasm-ld` are LLVM 23 under `/usr/lib/llvm/23/bin` on this host.

## The runtime the module imports

Everything the three programs needed from outside is this list, all `env.*`, all small:

| Import | What it does | Shim |
|---|---|---|
| `seq_alloc`, `seq_alloc_atomic` (size) | allocate | bump from `__heap_base`, 16-aligned, `memory.grow` as needed |
| `seq_realloc` (ptr, old, new) | grow a block | allocate and copy the smaller of the two |
| `memset`, `memcpy`, `bcmp` | libc | loops over the module's memory |
| `seq_alloc_exc`, `seq_throw` | raise a Python exception | allocate; throw a JS error |
| `seq_personality`, `seq_init` | unwinding, start-up | a stub returning 0; nothing, since no `main` runs |

There is no garbage collector: Codon's runtime uses Boehm and the shim is a bump allocator, so a
call that allocates leaks until the page resets the heap (set `top` back to `__heap_base` between
calls that return plain numbers, or copy the result out first).

## What the first real module taught (nemik:W820)

`core/chains.py` as `chains.wasm` (`tools/build_wasm.sh`, `wasm/chains_entry.codon`, loader
`src/nemik/web/wasm.js`) agrees with the page's JS and with native Python on the fixture fleet
(2025 cards, length 9, the same 21 on a longest chain, about 27 ms in node). Getting there found:

- `seq_realloc` is `(ptr, new size, old size)`; the IR says so with `allocsize(1)`. The spike's
  argument order was backwards and only worked on tiny lists.
- The runtime list grew: `seq_alloc_uncollectable`, `seq_alloc_atomic_uncollectable`, and the three
  `seq_locale_*` functions (C strings: decimal point, thousands separator, grouping), which
  number-to-string code asks for. wasm.js fails any other import by name when it is called.
- Codon sets up its globals in `main()`, which nothing calls in wasm; the loader calls it once, so
  `main` is exported.
- The shadow stack is 8 MiB (`-z stack-size`); the default 64 KiB overflows on a couple of thousand
  cards.
- **Codon's `--release` optimizer has a bug.** `d[k] = a[k] * b[k]` is rewritten into an in-place
  `d[k] *= ...` (`__dict_do_op_throws__`) that raises `KeyError` on the new key. It fails natively
  with `codon run --release` as well as in wasm, and `codon run` (no `--release`) hides it. The core
  assigns the product to a local first. Anything compiled for the page is built `--release`, so the
  census and the probes should be too (W824).
- The build is deterministic: separate temp directories give the same bytes, which is what makes the
  committed hash a check.

## Decided (nemik:W814)

1. **wasm64, no fallback.** wasm32 is not a retarget of this IR: the same dict/str program, linked
   with `llc -mtriple=wasm32` and `wasm-ld -mwasm32`, hangs, because Codon's IR carries x86_64's
   64-bit struct sizes as constants and wasm32 lays the structs out smaller. So the module is
   memory64. Operator, 2026-10-20: "Chrome and Firefox now, Safari later, no fallback." memory64 is
   in the finished WebAssembly 3.0 spec ([webassembly.org](https://webassembly.org/news/2025-09-17-wasm-3.0/));
   Chrome and Firefox ship it; Safari lists it in Technology Preview 251 and 252
   ([251](https://webkit.org/blog/18194/release-notes-for-safari-technology-preview-251/),
   [252](https://webkit.org/blog/18304/release-notes-for-safari-technology-preview-252/)) and not yet
   in stable, so the page's wasm computation does not run there until it does. A page that finds no
   memory64 says so; it does not carry a JS copy.
2. **The built `.wasm` is committed, with its hash.** The host's LLVM 23 (`llc`, `wasm-ld`) is not
   hermetic, so the gate does not build the module as a Bazel action. The `.wasm` sits beside its
   Python source with a sha256, as the vendored wheels do, and a rebuild check runs where the
   pinned Codon and the host's LLVM are present: it rebuilds from the Python and compares hashes, and
   says why it skipped where they are not. A Bazel-pinned LLVM replaces this when one is wanted.

## Not yet shown

3. Passing structured data (a list of cards with edges) in and out: flat arrays of integers and
   one string table are the likely shape, not Python objects.
4. Exceptions that are caught inside wasm (`seq_personality` is a stub), floats, and the cost of
   the module's size (the three above are small; `dict` and `str` pulled most of it).
5. What is pure enough to move: W815's inventory.
